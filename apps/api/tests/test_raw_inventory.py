"""PR01/03/09–15: raw inventory uses one ledger with explicit business ownership."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_inventory import ok
from test_postgres_material_order_links import body as order_body
from test_postgres_materials import create_material


def raw(pg, **extra):
    return create_material(pg, kind="raw", name="Synthetic raw stock", unit="KG", **extra)


def position(pg, material):
    return ok(pg.api.request("GET", f"/api/v1/raw-inventory/{material['id']}"))


def movement(pg, material, action, quantity, **extra):
    return pg.api.command(
        f"/api/v1/raw-inventory/{material['id']}/{action}",
        {"quantity": quantity, "business_date": "2026-10-26", "reason": "Synthetic use", **extra},
    )


def test_pr01_material_categories_and_separate_inventory_entrances(pg):
    material = raw(pg)
    assert material["kind"] == "raw"
    assert position(pg, material)["account"] is None
    denied = pg.api.command(
        f"/api/v1/inventory/{material['id']}/open",
        {"quantity": "10", "business_date": "2026-10-26"},
    )
    assert denied.status_code == 409 and denied.json()["code"] == "MATERIAL_KIND_MISMATCH"
    ok(movement(pg, material, "open", "10"))
    assert position(pg, material)["account"]["balance"] == "10"
    assert not ok(pg.api.request("GET", "/api/v1/inventory"))["items"]
    assert [
        item["material"]["id"]
        for item in ok(pg.api.request("GET", "/api/v1/raw-inventory"))["items"]
    ] == [material["id"]]
    assert not ok(pg.api.request("GET", "/api/v1/materials"))["items"]
    assert (
        ok(pg.api.request("GET", "/api/v1/materials?kind=raw"))["items"][0]["id"] == material["id"]
    )


def test_pr09_pr10_issue_partial_returns_and_replay(pg):
    material = raw(pg)
    ok(movement(pg, material, "open", "10.5"))
    issued = ok(movement(pg, material, "issues", "10"))
    assert issued["account"]["balance"] == "0.5"
    assert movement(pg, material, "issues", "0.6").json()["code"] == "RAW_INVENTORY_INSUFFICIENT"
    path = f"/api/v1/raw-inventory/entries/{issued['entry']['id']}/returns"
    key, payload = (
        uuid4(),
        {"quantity": "3", "business_date": "2026-10-26", "reason": "Synthetic unused return"},
    )
    first = ok(pg.api.command(path, payload, key))
    assert first["entry"]["returns_issue_id"] == issued["entry"]["id"]
    assert first["account"]["balance"] == "3.5"
    ok(pg.api.command(path, payload | {"quantity": "2"}))
    assert (
        pg.api.command(path, payload | {"quantity": "6"}).json()["code"]
        == "RAW_RETURN_EXCEEDS_ISSUED"
    )
    assert ok(pg.api.command(path, payload, key)) == first
    assert (
        pg.api.command(path, payload | {"quantity": "1"}, key).json()["code"]
        == "IDEMPOTENCY_CONFLICT"
    )
    assert position(pg, material)["account"]["balance"] == "5.5"


def test_pr01_raw_cannot_be_customer_order_identity_or_change_kind(pg):
    material = raw(pg)
    body = order_body(pg, "SYN-RAW-REJECT")
    body["material_choices"] = [
        {"line_number": 1, "material_id": material["id"], "expected_material_version": 1}
    ]
    rejected = pg.api.command("/api/v1/orders", body)
    assert rejected.status_code == 409 and rejected.json()["code"] == "MATERIAL_KIND_MISMATCH"
    changed = pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            "name": material["name"],
            "own_code": material["own_code"],
            "unit": "KG",
            "specification": material["specification"],
            "kind": "finished",
            "active": True,
            "expected_version": 1,
            "reason": "Synthetic category change",
        },
    )
    assert changed.status_code == 409
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("UPDATE materials SET kind='finished' WHERE id=:id"), {"id": material["id"]}
        )


@pytest.mark.parametrize("action", ["issues", "returns"])
def test_pr14_concurrent_issues_and_returns_never_overdraw(pg, action):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    issue_id = None
    if action == "returns":
        issue_id = ok(movement(pg, material, "issues", "10"))["entry"]["id"]

    def execute(_):
        from factoryflow.kernel.contracts import BusinessError

        try:
            if issue_id:
                pg.runtime.raw_inventory.return_issue(
                    pg.actor,
                    uuid4(),
                    issue_id,
                    {
                        "quantity": "6",
                        "business_date": "2026-10-26",
                        "reason": "Synthetic competing return",
                    },
                )
            else:
                pg.runtime.raw_inventory.issue(
                    pg.actor,
                    uuid4(),
                    material["id"],
                    {
                        "quantity": "6",
                        "business_date": "2026-10-26",
                        "reason": "Synthetic competing issue",
                    },
                )
            return True
        except BusinessError:
            return False

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(execute, range(2))) == [False, True]
    assert position(pg, material)["account"]["balance"] == ("6" if issue_id else "4")
