"""Synthetic finished-goods scenarios; all effects share the business transaction."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_postgres_material_order_links import body as order_body
from test_postgres_materials import create_material


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def stock(pg, material):
    return ok(pg.api.request("GET", f"/api/v1/inventory/{material['id']}"))


def opening(pg, material, quantity="100", **extra):
    return ok(
        pg.api.command(
            f"/api/v1/inventory/{material['id']}/open",
            {
                "quantity": quantity,
                "business_date": "2026-10-24",
                **extra,
            },
        )
    )


def receipt(pg, material, quantity="10", **extra):
    return ok(
        pg.api.command(
            f"/api/v1/inventory/{material['id']}/receipts",
            {
                "quantity": quantity,
                "business_date": "2026-10-20",
                **extra,
            },
        )
    )


def make_order(pg, materials, units=None, quantity="100"):
    body = order_body(pg, f"SYN-IV-{uuid4().hex[:12]}")
    body["lines"] = [
        body["lines"][0] | {"quantity": quantity, "unit": unit}
        for unit in (units or ["PCS"] * len(materials))
    ]
    body["material_choices"] = [
        {
            "line_number": i + 1,
            "material_id": material["id"],
            "expected_material_version": material["version"],
        }
        for i, material in enumerate(materials)
        if material is not None
    ]
    result = ok(pg.api.command("/api/v1/orders", body))
    return ok(pg.api.request("GET", f"/api/v1/orders/{result['order_id']}"))


def shipment(pg, order, quantities=None, **extra):
    current = ok(pg.api.request("GET", f"/api/v1/orders/{order['id']}"))
    return {
        "order_id": current["id"],
        "customer_id": pg.customer_id,
        "revision_id": current["revision_id"],
        "expected_version": current["version"],
        "delivery_date": "2026-10-24",
        "lines": [
            {"order_line_id": line["id"], "quantity": qty}
            for line, qty in zip(
                current["lines"], quantities or ["30"] * len(current["lines"]), strict=True
            )
        ],
        **extra,
    }


def send(pg, order, quantities=None, **extra):
    return ok(pg.api.command("/api/v1/deliveries", shipment(pg, order, quantities, **extra)))


def void_delivery(pg, delivery):
    return ok(
        pg.api.command(
            f"/api/v1/deliveries/{delivery['id']}/void",
            {
                "expected_version": 1,
                "reason": "Synthetic correction",
            },
        )
    )


def inventory_rows(pg):
    with pg.owner.connect() as conn:
        return tuple(
            conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in ("inventory_accounts", "inventory_ledger")
        )


def test_iv01_iv03_unmanaged_delivery_and_later_opening_do_not_retroactively_count(pg):
    material = create_material(pg)
    order = make_order(pg, [material, None])
    delivery = send(pg, order, ["30", "20"])
    assert [line["inventory"]["state"] for line in delivery["lines"]] == ["unmanaged", "unlinked"]
    assert inventory_rows(pg) == (0, 0)
    assert stock(pg, material)["account"] is None
    opening(pg, material, "70")
    void_delivery(pg, delivery)
    assert stock(pg, material)["account"]["balance"] == "70"
    assert inventory_rows(pg) == (1, 1)


def test_iv04_iv08_tracked_mixed_delivery_has_fixed_snapshots_and_exact_reverse(pg):
    managed, unmanaged = create_material(pg), create_material(pg)
    opening(pg, managed)
    order = make_order(pg, [managed, unmanaged, None])
    delivery = send(pg, order, ["30", "20", "10"])
    assert [line["inventory"]["state"] for line in delivery["lines"]] == [
        "tracked",
        "unmanaged",
        "unlinked",
    ]
    assert stock(pg, managed)["account"]["balance"] == "70"
    movement = delivery["lines"][0]["inventory"]["movement_id"]
    assert movement and all(
        line["inventory"]["movement_id"] is None for line in delivery["lines"][1:]
    )
    voided = void_delivery(pg, delivery)
    assert voided["lines"] == delivery["lines"]
    detail = stock(pg, managed)
    assert detail["account"]["balance"] == "100"
    assert detail["entries"][0]["reverses_id"] == movement


def test_iv05_negative_stock_requires_confirmation_and_partial_receipts_are_exact(pg):
    material = create_material(pg)
    opening(pg, material, "0")
    order = make_order(pg, [material])
    body = shipment(pg, order, ["20"])
    denied = pg.api.command("/api/v1/deliveries", body)
    assert denied.status_code == 409 and denied.json()["code"] == "INVENTORY_SHORTAGE"
    assert stock(pg, material)["account"]["balance"] == "0"
    sent = ok(pg.api.command("/api/v1/deliveries", body | {"confirm_inventory_shortage": True}))
    assert sent["lines"][0]["inventory"]["shortage_confirmed"] is True
    assert stock(pg, material)["account"]["balance"] == "-20"
    assert stock(pg, material)["account"]["negative_balance"] is True
    receipt(pg, material, "10")
    assert stock(pg, material)["account"]["balance"] == "-10"
    receipt(pg, material, "40")
    assert stock(pg, material)["account"]["balance"] == "30"


def test_iv06_iv07_iv13_skip_is_not_cleared_by_receipt_or_void_but_current_count_clears(pg):
    material = create_material(pg)
    opening(pg, material)
    order = make_order(pg, [material])
    skipped = send(pg, order, inventory_mode="skip")
    assert skipped["lines"][0]["inventory"]["state"] == "skipped"
    assert stock(pg, material)["account"]["balance"] == "100"
    assert stock(pg, material)["account"]["has_skipped"] is True
    receipt(pg, material)
    void_delivery(pg, skipped)
    account = stock(pg, material)["account"]
    assert account["balance"] == "110" and account["has_skipped"]
    count = ok(
        pg.api.command(
            f"/api/v1/inventory/{material['id']}/counts",
            {
                "quantity": "80",
                "business_date": "2026-10-24",
                "reason": "Synthetic physical count",
                "expected_version": account["version"],
            },
        )
    )
    assert count["account"]["balance"] == "80" and not count["account"]["needs_review"]
    assert count["entry"]["delta"] == "-30"
    assert {entry["kind"] for entry in stock(pg, material)["entries"]} == {
        "opening",
        "receipt",
        "skip",
        "count",
    }


def test_iv09_same_material_lines_are_checked_as_one_total(pg):
    material = create_material(pg)
    opening(pg, material, "10")
    order = make_order(pg, [material, material])
    response = pg.api.command("/api/v1/deliveries", shipment(pg, order, ["6", "6"]))
    assert response.status_code == 409 and response.json()["code"] == "INVENTORY_SHORTAGE"
    assert stock(pg, material)["account"]["balance"] == "10"
    send(pg, order, ["6", "6"], confirm_inventory_shortage=True)
    assert stock(pg, material)["account"]["balance"] == "-2"


@pytest.mark.parametrize("source_unit", ["PCS", None, "unknown"])
def test_iv10_unknown_or_incompatible_units_require_explicit_skip(pg, source_unit):
    material = create_material(pg, unit="KG")
    opening(pg, material, "10")
    order = make_order(pg, [material], [source_unit])
    response = pg.api.command("/api/v1/deliveries", shipment(pg, order, ["1"]))
    assert response.status_code == 409 and response.json()["code"] == "INVENTORY_UNIT_MISMATCH"
    send(pg, order, ["1"], inventory_mode="skip")
    account = stock(pg, material)["account"]
    assert account["balance"] == "10" and account["has_skipped"]


def test_iv14_receipt_void_cannot_make_stock_negative_or_reverse_twice(pg):
    material = create_material(pg)
    opening(pg, material, "0")
    received = receipt(pg, material)
    order = make_order(pg, [material])
    delivery = send(pg, order, ["8"])
    path = f"/api/v1/inventory/entries/{received['entry']['id']}/void"
    body = {"reason": "Synthetic wrong receipt"}
    denied = pg.api.command(path, body)
    assert denied.status_code == 409 and denied.json()["code"] == "INVENTORY_RECEIPT_IN_USE"
    void_delivery(pg, delivery)
    key = uuid4()
    reversed_receipt = ok(pg.api.command(path, body, key))
    assert reversed_receipt["account"]["balance"] == "0"
    assert ok(pg.api.command(path, body, key)) == reversed_receipt
    assert pg.api.command(path, body).status_code == 409


def test_iv15_stale_count_cannot_overwrite_delivery_and_zero_delta_count_is_evidence(pg):
    material = create_material(pg)
    opened = opening(pg, material)
    order = make_order(pg, [material])
    send(pg, order)
    body = {
        "quantity": "70",
        "business_date": "2026-10-24",
        "reason": "Synthetic count",
        "expected_version": opened["account"]["version"],
    }
    path = f"/api/v1/inventory/{material['id']}/counts"
    assert pg.api.command(path, body).json()["code"] == "VERSION_CONFLICT"
    current = stock(pg, material)["account"]
    result = ok(pg.api.command(path, body | {"expected_version": current["version"]}))
    assert result["account"]["version"] == current["version"] + 1
    assert Decimal(result["entry"]["delta"]) == 0


def test_iv16_replay_precedes_opening_and_choice_changes_conflict(pg):
    material = create_material(pg)
    order = make_order(pg, [material])
    body, key = shipment(pg, order), uuid4()
    original = ok(pg.api.command("/api/v1/deliveries", body, key))
    opening(pg, material, "70")
    assert (
        ok(
            pg.api.command(
                "/api/v1/deliveries",
                body
                | {
                    "inventory_mode": "sync",
                    "confirm_inventory_shortage": False,
                },
                key,
            )
        )
        == original
    )
    for change in ({"inventory_mode": "skip"}, {"confirm_inventory_shortage": True}):
        assert pg.api.command("/api/v1/deliveries", body | change, key).json()["code"] == (
            "IDEMPOTENCY_CONFLICT"
        )
    assert stock(pg, material)["account"]["balance"] == "70"


def test_inventory_commands_replay_original_account_snapshots_after_later_changes(pg):
    material = create_material(pg, unit="KG")
    commands = []
    for operation, quantity, extra in (
        ("open", "1.125", {}),
        ("receipts", "2.500", {}),
        ("counts", "1.000", {"expected_version": 2}),
    ):
        path = f"/api/v1/inventory/{material['id']}/{operation}"
        body = {"quantity": quantity, "business_date": "2026-10-24", "reason": "Synthetic", **extra}
        key = uuid4()
        commands.append((path, body, key, ok(pg.api.command(path, body, key))))
    current = stock(pg, material)
    ok(
        pg.api.command(
            f"/api/v1/materials/{material['id']}",
            {
                "name": material["name"],
                "own_code": material["own_code"],
                "specification": material["specification"],
                "unit": "KG",
                "active": False,
                "expected_version": 1,
                "reason": "Synthetic pause",
            },
        )
    )
    for path, body, key, original in commands:
        assert ok(pg.api.command(path, body, key)) == original
        assert (
            pg.api.command(path, body | {"quantity": "9"}, key).json()["code"]
            == "IDEMPOTENCY_CONFLICT"
        )
    refreshed = stock(pg, material)
    assert refreshed["account"] == current["account"]
    assert refreshed["entries"] == current["entries"]
