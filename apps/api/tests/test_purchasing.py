"""Real PostgreSQL/API evidence for PR02, PR04–08, PR13–14."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from conftest import API
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

DAY = "2026-10-26"


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def fixture(pg, count=1):
    supplier = ok(pg.api.command("/api/v1/suppliers", {"full_name": "Synthetic Supplier"}))
    materials = []
    for index in range(count):
        material = ok(
            pg.api.command(
                "/api/v1/materials", {"name": f"Synthetic Raw {index}", "unit": "KG", "kind": "raw"}
            )
        )
        ok(
            pg.api.command(
                f"/api/v1/raw-inventory/{material['id']}/open",
                {"quantity": "0", "business_date": DAY},
            )
        )
        materials.append(material)
    order = ok(
        pg.api.command(
            "/api/v1/purchase-orders",
            {
                "supplier_id": supplier["id"],
                "business_date": DAY,
                "lines": [{"material_id": m["id"], "quantity": "10"} for m in materials],
            },
        )
    )
    return supplier, materials, order


def receipt(pg, supplier, order, quantities, key=None):
    body = {
        "supplier_id": supplier["id"],
        "business_date": DAY,
        "purchase_order_id": order["id"],
        "lines": [
            {"purchase_line_id": line["id"], "quantity": qty}
            for line, qty in zip(order["lines"], quantities, strict=True)
        ],
    }
    return pg.api.command("/api/v1/purchase-receipts", body, key)


def detail(pg, identifier):
    return ok(pg.api.request("GET", f"/api/v1/purchase-orders/{identifier}"))


def test_supplier_creation_endpoint_is_available(pg):
    result = ok(pg.api.command("/api/v1/suppliers", {"full_name": "Synthetic Supplier"}))
    assert result["full_name"] == "Synthetic Supplier"
    assert result["active"] and result["version"] == 1
    assert ok(pg.api.request("GET", "/api/v1/suppliers?q=Synthetic"))["total"] == 1


def test_batches_exact_remaining_reject_over_receipt_and_replay(pg):
    supplier, materials, order = fixture(pg)
    key = uuid4()
    first = ok(receipt(pg, supplier, order, ["4"], key))
    assert detail(pg, order["id"])["lines"][0]["remaining_quantity"] == "6"
    second = ok(receipt(pg, supplier, order, ["6"]))
    assert detail(pg, order["id"])["lines"][0]["received_quantity"] == "10"
    assert receipt(pg, supplier, order, ["1"]).status_code == 409
    assert ok(receipt(pg, supplier, order, ["4"], key)) == first
    assert receipt(pg, supplier, order, ["5"], key).status_code == 409
    assert first["id"] != second["id"]
    stock = ok(pg.api.request("GET", f"/api/v1/raw-inventory/{materials[0]['id']}"))
    assert stock["account"]["balance"] == "10"


def test_direct_receipt_and_explicit_opening_required(pg):
    supplier = ok(pg.api.command("/api/v1/suppliers", {"full_name": "Synthetic Direct Supplier"}))
    raw = ok(
        pg.api.command("/api/v1/materials", {"name": "Synthetic Raw", "unit": "KG", "kind": "raw"})
    )
    body = {
        "supplier_id": supplier["id"],
        "business_date": DAY,
        "lines": [{"material_id": raw["id"], "quantity": "3"}],
    }
    assert pg.api.command("/api/v1/purchase-receipts", body).status_code == 409
    assert ok(pg.api.request("GET", "/api/v1/purchase-receipts"))["total"] == 0
    ok(
        pg.api.command(
            f"/api/v1/raw-inventory/{raw['id']}/open", {"quantity": "0", "business_date": DAY}
        )
    )
    result = ok(pg.api.command("/api/v1/purchase-receipts", body))
    assert result["purchase_order_id"] is None
    assert result["lines"][0]["purchase_line_id"] is None
    assert result["lines"][0]["quantity"] == "3"


def test_close_and_void_does_not_reopen_and_snapshot_replay(pg):
    supplier, _, order = fixture(pg)
    first = ok(receipt(pg, supplier, order, ["4"]))
    closed = ok(
        pg.api.command(
            f"/api/v1/purchase-orders/{order['id']}/close",
            {"expected_version": 1, "reason": "Synthetic close"},
        )
    )
    assert closed["status"] == "closed"
    assert receipt(pg, supplier, order, ["1"]).status_code == 409
    key = uuid4()
    body = {"expected_version": 1, "reason": "Synthetic wrong receipt"}
    void = ok(pg.api.command(f"/api/v1/purchase-receipts/{first['id']}/void", body, key))
    assert void["status"] == "void"
    assert ok(pg.api.command(f"/api/v1/purchase-receipts/{first['id']}/void", body, key)) == void
    after = detail(pg, order["id"])
    assert after["status"] == "closed"
    assert after["lines"][0]["received_quantity"] == "0"
    assert receipt(pg, supplier, order, ["1"]).status_code == 409


def test_multiline_void_insufficient_balance_rolls_back_every_line(pg):
    supplier, materials, order = fixture(pg, 2)
    first = ok(receipt(pg, supplier, order, ["4", "6"]))
    ok(
        pg.api.command(
            f"/api/v1/raw-inventory/{materials[1]['id']}/issues",
            {"quantity": "1", "business_date": DAY, "reason": "Synthetic use"},
        )
    )
    response = pg.api.command(
        f"/api/v1/purchase-receipts/{first['id']}/void",
        {"expected_version": 1, "reason": "Synthetic wrong receipt"},
    )
    assert response.status_code == 409
    assert (
        ok(pg.api.request("GET", f"/api/v1/purchase-receipts/{first['id']}"))["status"] == "active"
    )
    assert [line["received_quantity"] for line in detail(pg, order["id"])["lines"]] == ["4", "6"]
    for material, expected in zip(materials, ["4", "5"], strict=True):
        result = ok(pg.api.request("GET", f"/api/v1/raw-inventory/{material['id']}"))
        assert result["account"]["balance"] == expected


def test_supplier_deactivation_version_and_historical_name(pg):
    supplier, _, order = fixture(pg)
    body = {"full_name": "Synthetic Renamed", "active": False, "expected_version": 1}
    updated = ok(pg.api.command(f"/api/v1/suppliers/{supplier['id']}", body))
    assert updated["version"] == 2
    assert pg.api.command(f"/api/v1/suppliers/{supplier['id']}", body).status_code == 409
    assert detail(pg, order["id"])["supplier_name"] == "Synthetic Supplier"
    assert receipt(pg, supplier, order, ["1"]).status_code == 409


def test_duplicate_purchase_line_rejected(pg):
    supplier, _, order = fixture(pg)
    line = {"purchase_line_id": order["lines"][0]["id"], "quantity": "6"}
    result = pg.api.command(
        "/api/v1/purchase-receipts",
        {
            "supplier_id": supplier["id"],
            "purchase_order_id": order["id"],
            "business_date": DAY,
            "lines": [line, line],
        },
    )
    assert result.status_code == 422
    assert result.json()["code"] == "PURCHASE_LINE_DUPLICATE"


def test_concurrent_six_plus_six_cannot_exceed_ten(pg):
    supplier, _, order = fixture(pg)

    def receive(_):
        api = API(pg.app)
        api.login()
        return api.command(
            "/api/v1/purchase-receipts",
            {
                "supplier_id": supplier["id"],
                "purchase_order_id": order["id"],
                "business_date": DAY,
                "lines": [{"purchase_line_id": order["lines"][0]["id"], "quantity": "6"}],
            },
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(receive, range(2)))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert detail(pg, order["id"])["lines"][0]["received_quantity"] == "6"


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE purchase_order_lines SET ordered_quantity=11 WHERE order_id=:id",
        "UPDATE purchase_orders SET status='open' WHERE id=:id",
        "DELETE FROM purchase_orders WHERE id=:id",
        "INSERT INTO purchase_order_lines "
        "SELECT organization_id,:new,order_id,2,material_id,own_code,material_name,"
        "specification,canonical_unit,ordered_quantity "
        "FROM purchase_order_lines WHERE order_id=:id",
    ],
)
def test_runtime_cannot_rewrite_or_append_sealed_purchase_evidence(pg, statement):
    _, _, order = fixture(pg)
    with pytest.raises(DBAPIError):
        with pg.runtime.engine.begin() as conn:
            conn.execute(text(statement), {"id": order["id"], "new": uuid4()})


def test_runtime_cannot_void_header_without_stock_reversal(pg):
    supplier, _, order = fixture(pg)
    first = ok(receipt(pg, supplier, order, ["4"]))
    with pytest.raises(DBAPIError):
        with pg.runtime.engine.begin() as conn:
            conn.execute(
                text("""UPDATE purchase_receipts SET status='void',version=version+1,
                void_by=created_by,void_at=clock_timestamp(),void_reason='Synthetic SQL'
                WHERE id=:id"""),
                {"id": first["id"]},
            )
            conn.execute(
                text("""INSERT INTO audit_events
                (id,organization_id,actor_id,command_type,entity_id)
                VALUES (:event,:org,:actor,'purchase_receipt.void',:entity)"""),
                {
                    "event": uuid4(),
                    "org": pg.actor.organization_id,
                    "actor": pg.actor.user_id,
                    "entity": first["id"],
                },
            )
    assert detail(pg, order["id"])["lines"][0]["received_quantity"] == "4"


def test_organization_ownership_hides_suppliers_orders_and_receipts(pg):
    supplier, materials, order = fixture(pg)
    first = ok(receipt(pg, supplier, order, ["4"]))
    other_org = uuid4()
    with pg.owner.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations(id,name) VALUES (:id,:name)"),
            {"id": other_org, "name": "Synthetic Other Factory"},
        )
        conn.execute(
            text("""INSERT INTO users
            (id,organization_id,username,password_hash,role)
            SELECT :id,:org,'synthetic-other',password_hash,'admin'
            FROM users WHERE id=:source"""),
            {"id": uuid4(), "org": other_org, "source": pg.actor.user_id},
        )
    other = API(pg.app)
    other.login("synthetic-other")
    assert ok(other.request("GET", "/api/v1/suppliers"))["total"] == 0
    assert other.request("GET", f"/api/v1/purchase-orders/{order['id']}").status_code == 404
    assert other.request("GET", f"/api/v1/purchase-receipts/{first['id']}").status_code == 404
    assert (
        other.command(
            "/api/v1/purchase-orders",
            {
                "supplier_id": supplier["id"],
                "business_date": DAY,
                "lines": [{"material_id": materials[0]["id"], "quantity": "1"}],
            },
        ).status_code
        == 404
    )
    assert (
        other.command(
            f"/api/v1/suppliers/{supplier['id']}",
            {"full_name": "Synthetic changed", "active": False, "expected_version": 1},
        ).status_code
        == 404
    )


def purchasing_effects(pg):
    with pg.owner.connect() as conn:
        return {
            table: conn.execute(text(f"SELECT row_to_json(x)::text FROM {table} x ORDER BY 1"))
            .scalars()
            .all()
            for table in [
                "suppliers",
                "purchase_orders",
                "purchase_order_lines",
                "purchase_receipts",
                "purchase_receipt_lines",
                "inventory_accounts",
                "inventory_ledger",
                "audit_events",
                "command_results",
            ]
        }


@pytest.mark.parametrize("table", ["inventory_ledger", "audit_events", "command_results"])
def test_receiving_and_void_rollback_when_participant_fails(pg, table):
    supplier, _, order = fixture(pg)
    first = ok(receipt(pg, supplier, order, ["4"]))
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_purchasing_participant() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic purchasing failure'; END; $$;
            CREATE TRIGGER fail_purchasing_participant BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION fail_purchasing_participant();""")
        )
    before = purchasing_effects(pg)
    receive_key, void_key = uuid4(), uuid4()
    assert receipt(pg, supplier, order, ["2"], receive_key).status_code == 503
    assert purchasing_effects(pg) == before
    body = {"expected_version": 1, "reason": "Synthetic incorrect receipt"}
    assert (
        pg.api.command(f"/api/v1/purchase-receipts/{first['id']}/void", body, void_key).status_code
        == 503
    )
    assert purchasing_effects(pg) == before
    with pg.owner.begin() as conn:
        conn.execute(text(f"DROP TRIGGER fail_purchasing_participant ON {table}"))
    ok(receipt(pg, supplier, order, ["2"], receive_key))
    ok(pg.api.command(f"/api/v1/purchase-receipts/{first['id']}/void", body, void_key))
    assert detail(pg, order["id"])["lines"][0]["received_quantity"] == "2"


@pytest.mark.parametrize("quantity", ["1", "7"])
def test_runtime_sql_cannot_commit_missing_stock_or_over_receive(pg, quantity):
    supplier, _, order = fixture(pg)
    first = ok(receipt(pg, supplier, order, ["4"]))
    before = purchasing_effects(pg)
    identifier = uuid4()
    with pytest.raises(DBAPIError):
        with pg.runtime.engine.begin() as conn:
            conn.execute(
                text("""INSERT INTO purchase_receipts
                (organization_id,id,supplier_id,purchase_order_id,number,business_date,
                 supplier_name,note,created_by)
                SELECT organization_id,:new,supplier_id,purchase_order_id,:number,
                 business_date,supplier_name,note,created_by
                FROM purchase_receipts WHERE id=:source"""),
                {
                    "new": identifier,
                    "number": "Synthetic-SQL-" + uuid4().hex,
                    "source": first["id"],
                },
            )
            conn.execute(
                text("""INSERT INTO purchase_receipt_lines
                (organization_id,id,receipt_id,line_number,purchase_line_id,material_id,
                 own_code,material_name,specification,canonical_unit,quantity)
                SELECT organization_id,:new,:receipt,line_number,purchase_line_id,material_id,
                 own_code,material_name,specification,canonical_unit,:quantity
                FROM purchase_receipt_lines WHERE receipt_id=:source"""),
                {
                    "new": uuid4(),
                    "receipt": identifier,
                    "quantity": quantity,
                    "source": first["id"],
                },
            )
            conn.execute(
                text("""INSERT INTO audit_events
                (id,organization_id,actor_id,command_type,entity_id)
                VALUES (:event,:org,:actor,'purchase_receipt.create',:entity)"""),
                {
                    "event": uuid4(),
                    "org": pg.actor.organization_id,
                    "actor": pg.actor.user_id,
                    "entity": identifier,
                },
            )
            conn.execute(text("SET CONSTRAINTS purchase_receipt_lines_complete IMMEDIATE"))
    assert purchasing_effects(pg) == before
