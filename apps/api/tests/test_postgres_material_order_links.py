"""Late catalog links cannot change the source order, delivery or reconciliation."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text
from test_postgres_materials import create_material
from test_postgres_statement_lifecycle import approve, reserve, settle, setup_statement


def body(pg, number="SYN-M1-001"):
    return {
        "customer_id": pg.customer_id,
        "order_number": number,
        "business_date": "2026-10-22",
        "currency": "CNY",
        "lines": [
            {
                "item_code": "A-017",
                "item_name": "Synthetic bracket",
                "specification": "S-1",
                "description": "Synthetic bracket S-1",
                "quantity": "100",
                "unit": "PCS",
            }
        ],
    }


def confirm(pg, number="SYN-M1-001"):
    response = pg.api.command("/api/v1/orders", body(pg, number))
    assert response.status_code == 200, response.text
    return response.json(), pg.api.request(
        "GET", f"/api/v1/orders/{response.json()['order_id']}"
    ).json()


def test_collect_after_delivery_keeps_evidence_and_quantities_and_remembers_code(pg):
    confirmed, order = confirm(pg)
    evidence = pg.api.request(
        "GET", f"/api/v1/documents/{confirmed['revision_id']}/download"
    ).content
    delivery = pg.api.command(
        "/api/v1/deliveries",
        {
            "order_id": order["id"],
            "customer_id": pg.customer_id,
            "revision_id": confirmed["revision_id"],
            "expected_version": 1,
            "delivery_date": "2026-10-22",
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "30"}],
        },
    )
    assert delivery.status_code == 200, delivery.text
    request = {
        "expected_version": 2,
        "lines": [
            {
                "line_id": order["lines"][0]["id"],
                "new_material": {
                    "name": "Synthetic bracket",
                    "specification": "S-1",
                    "unit": "PCS",
                },
                "remember_code": True,
                "customer_code": "A-017",
            }
        ],
    }
    key = uuid4()
    result = pg.api.command(f"/api/v1/orders/{order['id']}/material-links", request, key)
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 3
    assert (
        pg.api.command(f"/api/v1/orders/{order['id']}/material-links", request, key).json()
        == result.json()
    )
    linked = pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()
    line = linked["lines"][0]
    assert (line["quantity"], line["delivered_quantity"], line["remaining_quantity"]) == (
        "100",
        "30",
        "70",
    )
    assert line["material_id"] and line["material"]["own_code"].startswith("WL")
    assert linked["revision_id"] == confirmed["revision_id"]
    assert (
        pg.api.request("GET", f"/api/v1/documents/{confirmed['revision_id']}/download").content
        == evidence
    )
    preview = pg.api.command("/api/v1/orders/preview", body(pg, "SYN-M1-002"))
    assert preview.status_code == 200, preview.text
    suggestion = preview.json()["material_suggestions"][0]
    assert suggestion["automatic"] is True
    new_order = body(pg, "SYN-M1-002") | {
        "material_choices": [
            {
                "line_number": 1,
                "material_id": line["material_id"],
                "expected_material_version": 1,
                "mapping": suggestion["mapping"],
            }
        ]
    }
    accepted = pg.api.command("/api/v1/orders", new_order)
    assert accepted.status_code == 200, accepted.text
    assert (
        pg.api.request("GET", f"/api/v1/orders/{accepted.json()['order_id']}").json()["lines"][0][
            "material_id"
        ]
        == line["material_id"]
    )
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM materials")).scalar_one() == 1


def test_changed_master_rejects_stale_selection_but_no_selection_still_works(pg):
    material = create_material(pg)
    selection = {"line_number": 1, "material_id": material["id"], "expected_material_version": 1}
    changed = pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            "name": "Synthetic renamed",
            "own_code": material["own_code"],
            "unit": "PCS",
            "specification": "S-1",
            "active": True,
            "expected_version": 1,
            "reason": "Synthetic name correction",
        },
    )
    assert changed.status_code == 200, changed.text
    result = pg.api.command("/api/v1/orders", body(pg) | {"material_choices": [selection]})
    assert result.status_code == 409, result.text
    assert result.json()["code"] == "MATERIAL_VERSION_CONFLICT"
    assert pg.api.command("/api/v1/orders", body(pg)).status_code == 200


def link(pg, order, material, **extra):
    return pg.api.command(
        f"/api/v1/orders/{order['id']}/material-links",
        {
            "expected_version": order["version"],
            "lines": [
                {
                    "line_id": order["lines"][0]["id"],
                    "material_id": material["id"],
                    "expected_material_version": material["version"],
                }
            ],
            **extra,
        },
    )


def test_completed_delivery_and_statement_exports_unchanged_by_late_link(pg):
    statement, source, sent, feedback = setup_statement(pg)
    approval = approve(pg, statement, source, sent, feedback, quantity="100")
    reserve(pg, statement, approval, "100")
    assert settle(pg, statement)["status"] == "confirmed"
    delivery = pg.api.request("GET", f"/api/v1/deliveries/{source['delivery_id']}").json()
    order = pg.api.request("GET", f"/api/v1/orders/{delivery['order_id']}").json()
    before_statement = pg.api.request("GET", f"/api/v1/statements/{statement['id']}").json()
    export_id = sent["export_id"]
    original_excel = pg.runtime.statement_exports.download(pg.actor, export_id, historical=True)[0]
    material = create_material(pg)
    result = link(pg, order, material)
    assert result.status_code == 200, result.text
    after = pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()
    assert after["lines"][0]["remaining_quantity"] == "0"
    assert pg.api.request("GET", f"/api/v1/statements/{statement['id']}").json() == before_statement
    assert pg.api.request("GET", f"/api/v1/deliveries/{source['delivery_id']}").json() == delivery
    assert (
        pg.runtime.statement_exports.download(pg.actor, export_id, historical=True)[0]
        == original_excel
    )


def test_revision_reorder_does_not_copy_links_and_old_lines_reject_rebinding(pg):
    confirmed, order = confirm(pg)
    material = create_material(pg)
    assert link(pg, order, material).status_code == 200
    revised_body = body(pg)
    revised_body["lines"] = [
        revised_body["lines"][0] | {"item_code": "SECOND"},
        revised_body["lines"][0],
    ]
    revised = pg.api.command(
        f"/api/v1/orders/{order['id']}/revisions",
        {
            "expected_version": 2,
            "reason": "Synthetic reordered",
            "order": revised_body
            | {
                "material_choices": [
                    {
                        "line_number": 2,
                        "material_id": material["id"],
                        "expected_material_version": 1,
                    }
                ]
            },
        },
    )
    assert revised.status_code == 200, revised.text
    current = pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()
    assert [line["material_id"] for line in current["lines"]] == [None, material["id"]]
    wrong = link(pg, order | {"version": 3}, material)
    assert wrong.status_code == 409 and wrong.json()["code"] == "MATERIAL_LINE_NOT_CURRENT"
    with pg.owner.connect() as conn:
        assert (
            str(
                conn.execute(
                    text("SELECT material_id FROM order_lines WHERE id=:id"),
                    {"id": order["lines"][0]["id"]},
                ).scalar_one()
            )
            == material["id"]
        )
    assert confirmed["revision_id"] != current["revision_id"]


@pytest.mark.parametrize(
    "table",
    ["materials", "customer_material_codes", "order_lines", "audit_events", "command_results"],
)
def test_new_material_code_and_order_link_roll_back_together(pg, table):
    _, order = confirm(pg)
    with pg.owner.begin() as conn:
        predicate = (
            "TRUE"
            if table in {"materials", "customer_material_codes", "order_lines"}
            else "NEW.command_type='order.material_links'"
        )
        operation = "UPDATE OF material_id" if table == "order_lines" else "INSERT"
        conn.execute(
            text(f"""CREATE FUNCTION fail_m1() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN IF {predicate} THEN RAISE EXCEPTION 'synthetic failure'; END IF;
            RETURN NEW; END; $$;
            CREATE TRIGGER fail_m1 BEFORE {operation} ON {table}
            FOR EACH ROW EXECUTE FUNCTION fail_m1();""")
        )
    result = pg.api.command(
        f"/api/v1/orders/{order['id']}/material-links",
        {
            "expected_version": 1,
            "lines": [
                {
                    "line_id": order["lines"][0]["id"],
                    "new_material": {"name": "Synthetic rollback"},
                    "remember_code": True,
                    "customer_code": "A-017",
                }
            ],
        },
    )
    assert result.status_code == 503, result.text
    with pg.owner.connect() as conn:
        for name in ("materials", "customer_material_codes"):
            assert conn.execute(text(f"SELECT count(*) FROM {name}")).scalar_one() == 0
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM command_results WHERE command_type='order.material_links'"
                )
            ).scalar_one()
            == 0
        )
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_events WHERE command_type='order.material_links'")
            ).scalar_one()
            == 0
        )
    assert pg.api.request("GET", f"/api/v1/orders/{order['id']}").json() == order


def test_unlink_correction_requires_reason_and_does_not_erase_customer_mapping(pg):
    _, order = confirm(pg)
    material = create_material(pg)
    assert (
        link(
            pg,
            order,
            material,
            lines=[
                {
                    "line_id": order["lines"][0]["id"],
                    "material_id": material["id"],
                    "expected_material_version": 1,
                    "remember_code": True,
                    "customer_code": "A-017",
                }
            ],
        ).status_code
        == 200
    )
    mapping = pg.api.request("GET", f"/api/v1/material-codes?customer_id={pg.customer_id}").json()
    assert len(mapping["items"]) == 1
    path = f"/api/v1/orders/{order['id']}/material-links"
    request = {"expected_version": 2, "lines": [{"line_id": order["lines"][0]["id"]}]}
    assert pg.api.command(path, request).status_code == 422
    result = pg.api.command(path, request | {"reason": "Wrong association"})
    assert result.status_code == 200, result.text
    assert result.json()["changes"][0]["before"]["id"] == material["id"]
    assert result.json()["changes"][0]["after"] is None
    assert (
        pg.api.request("GET", f"/api/v1/material-codes?customer_id={pg.customer_id}").json()
        == mapping
    )
    assert (
        pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()["lines"][0]["material_id"]
        is None
    )
    viewer = type(pg.actor)(pg.actor.organization_id, pg.actor.user_id, pg.actor.username, "viewer")
    with pytest.raises(BusinessError, match="WRITE_FORBIDDEN"):
        pg.runtime.orders.material_links(viewer, uuid4(), order["id"], request)


def remember(pg, material, customer_id=None):
    result = pg.api.command(
        "/api/v1/material-codes",
        {
            "customer_id": customer_id or pg.customer_id,
            "customer_code": "A-017",
            "material_id": material["id"],
            "expected_material_version": material["version"],
            "item_name": "Synthetic bracket",
            "specification": "S-1",
            "unit": "PCS",
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def test_changed_mapping_rejects_old_preview_and_keeps_historical_binding(pg):
    first, second = create_material(pg), create_material(pg)
    remember(pg, first)
    suggestion = pg.api.command("/api/v1/orders/preview", body(pg)).json()["material_suggestions"][
        0
    ]
    selected = {
        "line_number": 1,
        "material_id": first["id"],
        "expected_material_version": 1,
        "mapping": suggestion["mapping"],
    }
    key = uuid4()
    request = body(pg) | {"material_choices": [selected]}
    original = pg.api.command("/api/v1/orders", request, key)
    assert original.status_code == 200, original.text
    changed = pg.api.command(
        "/api/v1/material-codes",
        {
            "customer_id": pg.customer_id,
            "customer_code": "A-017",
            "material_id": second["id"],
            "expected_material_version": 1,
            "expected_mapping_version": 1,
            "item_name": "Synthetic bracket",
            "specification": "S-1",
            "unit": "PCS",
            "reason": "Synthetic target correction",
        },
    )
    assert changed.status_code == 200, changed.text
    stale = pg.api.command("/api/v1/orders", request | {"order_number": "SYN-M1-STALE"})
    assert stale.status_code == 409 and stale.json()["code"] == "MATERIAL_MAPPING_CONFLICT"
    historical = pg.api.request("GET", f"/api/v1/orders/{original.json()['order_id']}").json()
    assert historical["lines"][0]["material_id"] == first["id"]
    evidence_path = f"/api/v1/documents/{original.json()['revision_id']}/download"
    evidence = pg.api.request("GET", evidence_path).content
    renamed = pg.api.command(
        f"/api/v1/materials/{first['id']}",
        {
            "own_code": "000128-RENAMED",
            "name": first["name"],
            "specification": "S-1",
            "unit": "PCS",
            "active": True,
            "expected_version": 1,
            "reason": "Synthetic own code correction",
        },
    )
    assert renamed.status_code == 200 and renamed.json()["id"] == first["id"]
    assert pg.api.request("GET", evidence_path).content == evidence
    assert (
        pg.api.request("GET", f"/api/v1/orders/{original.json()['order_id']}").json()["lines"][0][
            "material_id"
        ]
        == first["id"]
    )
    assert pg.api.command("/api/v1/orders", request, key).json() == original.json()
    altered = request | {"material_choices": [selected | {"material_id": second["id"]}]}
    conflict = pg.api.command("/api/v1/orders", altered, key)
    assert conflict.status_code == 409 and conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    new_suggestion = pg.api.command("/api/v1/orders/preview", body(pg)).json()[
        "material_suggestions"
    ][0]
    assert new_suggestion["material"]["id"] == second["id"] and new_suggestion["automatic"]


def test_same_code_for_different_customers_cannot_substitute_mapping(pg):
    first, second = create_material(pg), create_material(pg)
    other = pg.api.command("/api/v1/customers", {"full_name": "Synthetic Other Customer"}).json()
    remember(pg, first)
    remember(pg, second, other["id"])
    first_preview = pg.api.command("/api/v1/orders/preview", body(pg)).json()[
        "material_suggestions"
    ][0]
    second_preview = pg.api.command(
        "/api/v1/orders/preview", body(pg) | {"customer_id": other["id"]}
    ).json()["material_suggestions"][0]
    assert first_preview["material"]["id"] == first["id"]
    assert second_preview["material"]["id"] == second["id"]
    wrong = pg.api.command(
        "/api/v1/orders",
        body(pg)
        | {
            "material_choices": [
                {
                    "line_number": 1,
                    "material_id": second["id"],
                    "expected_material_version": 1,
                    "mapping": second_preview["mapping"],
                }
            ]
        },
    )
    assert wrong.status_code == 409 and wrong.json()["code"] == "MATERIAL_MAPPING_CONFLICT"


def test_changed_source_or_inactive_material_never_auto_adopts(pg):
    material = create_material(pg)
    remember(pg, material)
    for changes in ({"specification": "S-2"}, {"unit": "unknown-unit"}, {"unit": "KG"}):
        request = body(pg)
        request["lines"][0].update(changes)
        preview = pg.api.command("/api/v1/orders/preview", request)
        assert preview.status_code == 200, preview.text
        assert preview.json()["material_suggestions"][0]["automatic"] is False
    _, existing = confirm(pg)
    assert link(pg, existing, material).status_code == 200
    deactivated = pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            "own_code": material["own_code"],
            "name": material["name"],
            "specification": "S-1",
            "unit": "PCS",
            "expected_version": 1,
            "active": False,
            "reason": "Synthetic unused catalog entry",
        },
    )
    assert deactivated.status_code == 200, deactivated.text
    preview = pg.api.command("/api/v1/orders/preview", body(pg, "SYN-INACTIVE"))
    assert preview.json()["material_suggestions"][0]["automatic"] is False
    rejected = pg.api.command(
        "/api/v1/orders",
        body(pg, "SYN-INACTIVE")
        | {
            "material_choices": [
                {
                    "line_number": 1,
                    "material_id": material["id"],
                    "expected_material_version": 2,
                }
            ]
        },
    )
    assert rejected.status_code == 409 and rejected.json()["code"] == "MATERIAL_INACTIVE"
    assert pg.api.command("/api/v1/orders", body(pg, "SYN-INACTIVE")).status_code == 200
    assert (
        pg.api.request("GET", f"/api/v1/orders/{existing['id']}").json()["lines"][0]["material_id"]
        == material["id"]
    )


def test_concurrent_links_one_version_wins_and_foreign_or_deleted_order_rejects(pg):
    _, order = confirm(pg)
    material = create_material(pg)
    payload = {
        "expected_version": 1,
        "lines": [
            {
                "line_id": order["lines"][0]["id"],
                "material_id": material["id"],
                "expected_material_version": 1,
            }
        ],
    }
    foreign = replace(pg.actor, organization_id=uuid4())
    with pytest.raises(BusinessError, match="ORDER_NOT_FOUND"):
        pg.runtime.orders.material_links(foreign, uuid4(), order["id"], payload)

    def save(_):
        try:
            return pg.runtime.orders.material_links(pg.actor, uuid4(), order["id"], payload)[
                "version"
            ]
        except BusinessError as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, range(2)))
    assert results.count(2) == results.count("VERSION_CONFLICT") == 1
    deleted = pg.api.command(
        f"/api/v1/orders/{order['id']}/delete",
        {"expected_version": 2, "reason": "Synthetic delete"},
    )
    assert deleted.status_code == 200, deleted.text
    rejected = pg.api.command(
        f"/api/v1/orders/{order['id']}/material-links", payload | {"expected_version": 3}
    )
    assert rejected.status_code == 409 and rejected.json()["code"] == "ORDER_NOT_ACTIVE"
