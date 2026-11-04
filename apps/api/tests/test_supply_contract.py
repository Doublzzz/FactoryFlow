"""User-visible errors and permission/quantity edges of the supply contract."""

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from test_purchasing import DAY, fixture, ok, purchasing_effects


def test_duplicate_purchase_and_receipt_numbers_report_a_recoverable_error(pg):
    supplier, materials, _ = fixture(pg)
    body = {
        "supplier_id": supplier["id"],
        "business_date": DAY,
        "number": "SYN-DUPLICATE",
        "lines": [{"material_id": materials[0]["id"], "quantity": "1"}],
    }
    for path in ("/purchase-orders", "/purchase-receipts"):
        ok(pg.api.command("/api/v1" + path, body))
        before = purchasing_effects(pg)
        rejected = pg.api.command("/api/v1" + path, body)
        assert rejected.status_code == 409
        assert rejected.json()["code"] == "PURCHASE_NUMBER_EXISTS"
        assert purchasing_effects(pg) == before


@pytest.mark.parametrize("quantity", ["0", "-1", "0.0001", "9223372036854775.808", 1.5])
def test_purchase_quantity_boundary_failures_leave_no_facts(pg, quantity):
    supplier, materials, _ = fixture(pg)
    before = purchasing_effects(pg)
    rejected = pg.api.command(
        "/api/v1/purchase-orders",
        {
            "supplier_id": supplier["id"],
            "business_date": DAY,
            "lines": [{"material_id": materials[0]["id"], "quantity": quantity}],
        },
    )
    assert rejected.status_code in {400, 422}
    assert purchasing_effects(pg) == before


def test_viewer_reads_supply_but_cannot_create_any_supply_fact(pg):
    supplier, materials, order = fixture(pg)
    pg.runtime.identity.add_user(pg.actor, "synthetic-supply-viewer", SYNTHETIC_PASSWORD, "viewer")
    viewer = API(pg.app)
    viewer.login("synthetic-supply-viewer")
    assert ok(viewer.request("GET", "/api/v1/suppliers"))["total"] == 1
    assert ok(viewer.request("GET", "/api/v1/raw-inventory"))["items"]
    before = purchasing_effects(pg)
    body = {
        "supplier_id": supplier["id"],
        "business_date": DAY,
        "lines": [{"material_id": materials[0]["id"], "quantity": "1"}],
    }
    commands = [
        ("/suppliers", {"full_name": "Synthetic unauthorized supplier"}),
        ("/purchase-orders", body),
        ("/purchase-receipts", body),
        (f"/purchase-orders/{order['id']}/close", {"expected_version": 1, "reason": "Synthetic"}),
        (
            f"/raw-inventory/{materials[0]['id']}/issues",
            {"quantity": "1", "business_date": DAY, "reason": "Synthetic"},
        ),
    ]
    for path, payload in commands:
        rejected = viewer.command("/api/v1" + path, payload)
        assert rejected.status_code == 403 and rejected.json()["code"] == "WRITE_FORBIDDEN"
    assert purchasing_effects(pg) == before
