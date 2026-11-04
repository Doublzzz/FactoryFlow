"""PD01–12: production connects real orders and the existing stock ledger."""

from dataclasses import replace
from uuid import uuid4

import pytest
from factoryflow.kernel.contracts import BusinessError
from test_postgres_inventory import make_order, ok, opening, send, stock
from test_postgres_material_order_links import body as order_body
from test_postgres_material_order_links import link
from test_postgres_materials import create_material
from test_raw_inventory import movement, position, raw

DAY = "2026-10-27"
BASE = "/api/v1/production-orders"


def fixture(pg, *, open_finished=True):
    finished = create_material(pg, name="Synthetic production output", unit="PCS")
    material = raw(pg)
    ok(movement(pg, material, "open", "100"))
    if open_finished:
        opening(pg, finished, "10")
    order = make_order(pg, [finished], quantity="100")
    payload = {
        "order_id": order["id"],
        "revision_id": order["revision_id"],
        "order_line_id": order["lines"][0]["id"],
        "expected_order_version": order["version"],
        "planned_quantity": "100",
        "business_date": DAY,
    }
    production = ok(pg.api.command(BASE, payload))
    return finished, material, order, production, payload


def detail(pg, production):
    return ok(pg.api.request("GET", f"{BASE}/{production['id']}"))


def issue(pg, production, material, quantity="30", key=None):
    return pg.api.command(
        f"{BASE}/{production['id']}/issues",
        {
            "material_id": material["id"],
            "quantity": quantity,
            "business_date": DAY,
            "reason": "Synthetic production use",
        },
        key,
    )


def finish(pg, production, quantity="40", scrap="0", key=None):
    return pg.api.command(
        f"{BASE}/{production['id']}/completions",
        {"quantity": quantity, "scrap_quantity": scrap, "business_date": DAY},
        key,
    )


def void(pg, production, completion, key=None):
    return pg.api.command(
        f"{BASE}/{production['id']}/completions/{completion['id']}/void",
        {"expected_version": completion["version"], "reason": "Synthetic correction"},
        key,
    )


def test_pd_small_production_loop_preserves_order_delivery_and_tracks_returns(pg):
    finished, material, order, production, _ = fixture(pg)
    assert production["completed_quantity"] == "0"
    assert production["source_current"] is True
    key = uuid4()
    issued = ok(issue(pg, production, material, key=key))
    assert ok(issue(pg, production, material, key=key)) == issued
    assert issue(pg, production, material, "31", key).json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert position(pg, material)["account"]["balance"] == "70"
    returned = ok(
        pg.api.command(
            f"{BASE}/{production['id']}/issues/{issued['entry_id']}/returns",
            {"quantity": "5", "business_date": DAY, "reason": "Unused material"},
        )
    )
    assert returned["production_order_id"] == production["id"]
    # Existing raw-stock return entrance must retain the same production source.
    result = ok(
        pg.api.command(
            f"/api/v1/raw-inventory/entries/{issued['entry_id']}/returns",
            {"quantity": "3", "business_date": DAY, "reason": "Further unused material"},
        )
    )
    assert result["entry"]["production_order_id"] == production["id"]
    assert position(pg, material)["account"]["balance"] == "78"
    issues = ok(pg.api.request("GET", f"{BASE}/{production['id']}/issues"))
    assert issues["items"][0]["returned_quantity"] == "8"
    assert issues["items"][0]["outstanding_quantity"] == "22"
    first = ok(finish(pg, production, "40", "2"))
    assert stock(pg, finished)["account"]["balance"] == "50"
    ok(finish(pg, production, "60"))
    assert detail(pg, production)["completed_quantity"] == "100"
    assert detail(pg, production)["scrap_quantity"] == "2"
    assert detail(pg, production)["remaining_quantity"] == "0"
    assert finish(pg, production, "1").json()["code"] == "PRODUCTION_EXCEEDS_PLAN"
    current = ok(pg.api.request("GET", f"/api/v1/orders/{order['id']}"))
    assert current == order
    key = uuid4()
    reversed_first = ok(void(pg, production, first, key))
    assert ok(void(pg, production, first, key)) == reversed_first
    assert detail(pg, production)["completed_quantity"] == "60"
    assert detail(pg, production)["scrap_quantity"] == "0"
    assert stock(pg, finished)["account"]["balance"] == "70"


def test_pd_missing_inventory_does_not_create_account_and_scrap_is_not_stock(pg):
    finished, _, _, production, _ = fixture(pg, open_finished=False)
    assert finish(pg, production).json()["code"] == "INVENTORY_NOT_MANAGED"
    assert stock(pg, finished)["account"] is None
    assert detail(pg, production)["completed_quantity"] == "0"
    scrap = ok(finish(pg, production, "0", "3"))
    assert detail(pg, production)["scrap_quantity"] == "3"
    assert stock(pg, finished)["account"] is None
    ok(void(pg, production, scrap))
    assert detail(pg, production)["scrap_quantity"] == "0"
    assert finish(pg, production, "0").status_code == 422
    assert finish(pg, production, "0.5").json()["code"] == "UNIT_REQUIRES_INTEGER_QUANTITY"


def test_pd_close_keeps_actual_stock_and_allows_return_and_correction(pg):
    finished, material, _, production, _ = fixture(pg)
    issued = ok(issue(pg, production, material))
    completed = ok(finish(pg, production))
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/close",
            {
                "expected_version": detail(pg, production)["version"],
                "reason": "Stop remaining plan",
            },
        )
    )
    assert issue(pg, production, material).json()["code"] == "PRODUCTION_CLOSED"
    assert finish(pg, production).json()["code"] == "PRODUCTION_CLOSED"
    assert stock(pg, finished)["account"]["balance"] == "50"
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/issues/{issued['entry_id']}/returns",
            {
                "quantity": "30",
                "business_date": DAY,
                "reason": "Unused material after close",
            },
        )
    )
    ok(void(pg, production, completed))
    assert detail(pg, production)["status"] == "closed"
    assert stock(pg, finished)["account"]["balance"] == "10"
    assert position(pg, material)["account"]["balance"] == "100"


def test_pd_manual_void_cannot_bypass_production_and_balance_guards(pg):
    finished, _, _, production, _ = fixture(pg)
    completed = ok(finish(pg, production))
    entry = next(x for x in stock(pg, finished)["entries"] if x["kind"] == "production_receipt")
    denied = pg.api.command(
        f"/api/v1/inventory/entries/{entry['id']}/void",
        {
            "reason": "Wrong entrance",
        },
    )
    assert denied.status_code == 409
    current = stock(pg, finished)["account"]
    ok(
        pg.api.command(
            f"/api/v1/inventory/{finished['id']}/counts",
            {
                "quantity": "2",
                "expected_version": current["version"],
                "business_date": DAY,
                "reason": "Synthetic physical count",
            },
        )
    )
    assert void(pg, production, completed).json()["code"] == "PRODUCTION_RECEIPT_IN_USE"
    assert detail(pg, production)["completed_quantity"] == "40"


@pytest.mark.parametrize("change", ["revision", "rebind", "delete"])
def test_pd_changed_source_preserves_snapshot_and_allows_reverse_actions(pg, change):
    finished, material, order, production, _ = fixture(pg)
    issued = ok(issue(pg, production, material))
    key = uuid4()
    completed = ok(finish(pg, production, key=key))
    if change == "revision":
        body = order_body(pg, order["order_number"])
        body["lines"][0]["quantity"] = "200"
        ok(
            pg.api.command(
                f"/api/v1/orders/{order['id']}/revisions",
                {
                    "order": body,
                    "expected_version": order["version"],
                    "reason": "Synthetic source revision",
                },
            )
        )
    elif change == "rebind":
        other = create_material(pg, name="Synthetic different product", unit="PCS")
        ok(link(pg, order, other, reason="Synthetic product correction"))
    else:
        ok(
            pg.api.command(
                f"/api/v1/orders/{order['id']}/delete",
                {
                    "expected_version": order["version"],
                    "reason": "Synthetic delete",
                },
            )
        )
    after = detail(pg, production)
    assert after["source_current"] is False
    for field in (
        "order_id",
        "source_revision_id",
        "order_line_id",
        "material_id",
        "source_quantity",
    ):
        assert after[field] == production[field]
    assert issue(pg, production, material).json()["code"] == "PRODUCTION_SOURCE_CHANGED"
    assert finish(pg, production, "1").json()["code"] == "PRODUCTION_SOURCE_CHANGED"
    assert ok(finish(pg, production, key=key)) == completed
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/issues/{issued['entry_id']}/returns",
            {
                "quantity": "2",
                "business_date": DAY,
                "reason": "Synthetic source changed return",
            },
        )
    )
    ok(void(pg, production, completed))
    assert stock(pg, finished)["account"]["balance"] == "10"
    if change == "delete":
        ok(
            pg.api.command(
                f"/api/v1/orders/{order['id']}/restore",
                {
                    "expected_version": order["version"] + 1,
                    "reason": "Synthetic restore",
                },
            )
        )
        assert detail(pg, production)["source_current"] is True
        ok(finish(pg, production, "1"))


def test_pd_delivery_version_change_does_not_disable_production_or_change_delivery(pg):
    finished, material, order, production, _ = fixture(pg)
    send(pg, order, ["5"])
    assert detail(pg, production)["source_current"] is True
    ok(issue(pg, production, material))
    ok(finish(pg, production, "10"))
    current = ok(pg.api.request("GET", f"/api/v1/orders/{order['id']}"))
    assert current["lines"][0]["delivered_quantity"] == "5"
    assert stock(pg, finished)["account"]["balance"] == "15"


def test_pd_creation_requires_current_linked_exact_unit_and_stale_version_is_rejected(pg):
    _, _, order, production, request = fixture(pg)
    key = uuid4()
    created = ok(pg.api.command(BASE, request, key))
    assert ok(pg.api.command(BASE, request, key)) == created
    assert (
        pg.api.command(BASE, request | {"planned_quantity": "1"}, key).json()["code"]
        == "IDEMPOTENCY_CONFLICT"
    )
    assert (
        pg.api.command(BASE, request | {"expected_order_version": 999}).json()["code"]
        == "VERSION_CONFLICT"
    )
    assert (
        pg.api.command(BASE, request | {"order_line_id": str(uuid4())}).json()["code"]
        == "PRODUCTION_SOURCE_CHANGED"
    )
    for bad in ("0", "0.1", "-1", "1.0001", "1e2", "9223372036854775.808"):
        assert pg.api.command(BASE, request | {"planned_quantity": bad}).status_code == 422
    unlinked = make_order(pg, [None])
    assert (
        pg.api.command(
            BASE,
            request
            | {
                "order_id": unlinked["id"],
                "revision_id": unlinked["revision_id"],
                "order_line_id": unlinked["lines"][0]["id"],
            },
        ).json()["code"]
        == "PRODUCTION_MATERIAL_REQUIRED"
    )
    page = ok(pg.api.request("GET", BASE, params={"order_id": order["id"], "limit": 1}))
    assert page["total"] == 2 and len(page["items"]) == 1
    assert page["items"][0]["id"] == created["id"]
    assert ok(pg.api.request("GET", BASE, params={"order_id": str(uuid4())}))["total"] == 0
    assert production["id"] != created["id"]  # Explicitly separate plans, no inferred reservation.


def test_pd_movement_source_permission_and_organization_boundaries(pg):
    _, material, _, production, request = fixture(pg)
    other = ok(pg.api.command(BASE, request))
    issued = ok(issue(pg, production, material))
    path = f"{BASE}/{other['id']}/issues/{issued['entry_id']}/returns"
    assert (
        pg.api.command(
            path, {"quantity": "1", "business_date": DAY, "reason": "Wrong plan"}
        ).json()["code"]
        == "PRODUCTION_ISSUE_MISMATCH"
    )
    viewer = replace(pg.actor, role="viewer")
    foreign = replace(pg.actor, organization_id=uuid4())
    service = pg.runtime.production
    for action in (
        lambda: service.create(viewer, uuid4(), request),
        lambda: service.issue(
            viewer,
            uuid4(),
            production["id"],
            {
                "material_id": material["id"],
                "quantity": "1",
                "business_date": DAY,
                "reason": "No write",
            },
        ),
        lambda: service.complete(
            viewer, uuid4(), production["id"], {"quantity": "1", "business_date": DAY}
        ),
    ):
        with pytest.raises(BusinessError) as error:
            action()
        assert error.value.code == "WRITE_FORBIDDEN"
    assert service.list(foreign)["total"] == 0
    for action in (service.get, service.issues, service.completions):
        with pytest.raises(BusinessError) as error:
            action(foreign, production["id"])
        assert error.value.code == "PRODUCTION_NOT_FOUND"


def test_pd_decimal_output_does_not_convert_or_consume_raw_material(pg):
    finished = create_material(pg, name="Synthetic kilogram output", unit="KG")
    material = create_material(pg, name="Synthetic gram raw material", kind="raw", unit="G")
    ok(movement(pg, material, "open", "1000.125"))
    opening(pg, finished, "0")
    order = make_order(pg, [finished], units=["KG"], quantity="3.125")
    production = ok(
        pg.api.command(
            BASE,
            {
                "order_id": order["id"],
                "revision_id": order["revision_id"],
                "order_line_id": order["lines"][0]["id"],
                "expected_order_version": order["version"],
                "planned_quantity": "2.125",
                "business_date": DAY,
            },
        )
    )
    ok(issue(pg, production, material, "250.125"))
    ok(finish(pg, production, "1.125", "0.125"))
    ok(finish(pg, production, "1"))
    assert detail(pg, production)["completed_quantity"] == "2.125"
    assert stock(pg, finished)["account"]["balance"] == "2.125"
    assert position(pg, material)["account"]["balance"] == "750"
