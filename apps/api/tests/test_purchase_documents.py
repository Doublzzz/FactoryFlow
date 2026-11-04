"""PI01–04, PI07–13: purchase evidence, money and print on real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from conftest import API
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_extraction import PNG
from test_postgres_orders import order_body

DAY = "2026-10-27"
BASE = "/api/v1/purchase-orders"


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def inputs(pg):
    supplier = ok(pg.api.command("/api/v1/suppliers", {"full_name": "Synthetic Purchase Supplier"}))
    raw = ok(
        pg.api.command("/api/v1/materials", {"kind": "raw", "name": "Synthetic Raw", "unit": "KG"})
    )
    return (
        supplier,
        raw,
        {
            "supplier_id": supplier["id"],
            "business_date": DAY,
            "lines": [{"material_id": raw["id"], "quantity": "3"}],
        },
    )


def source(pg, monkeypatch, purpose="purchase_order", suffix=b"", extract=True):
    monkeypatch.setattr(
        pg.runtime.extraction.extractor,
        "extract",
        lambda *_: {"status": "ready", "error_code": None, "pages": [], "engine": "synthetic"},
    )
    uploaded = pg.runtime.extraction.upload(
        pg.actor, uuid4(), "synthetic-purchase.png", "image/png", PNG + suffix, purpose=purpose
    )
    if extract:
        run = pg.runtime.extraction.extract(pg.actor, uuid4(), UUID(uploaded["source_id"]))
        uploaded["extraction_id"] = run["extraction_id"]
    return uploaded


def effects(pg):
    with pg.owner.connect() as conn:
        return {
            table: list(
                conn.execute(
                    text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1")
                ).scalars()
            )
            for table in (
                "purchase_orders",
                "purchase_order_lines",
                "purchase_receipts",
                "inventory_accounts",
                "inventory_ledger",
                "orders",
                "order_lines",
                "production_orders",
                "production_completions",
                "command_results",
                "audit_events",
            )
        }


def test_manual_purchase_money_snapshot_print_and_no_stock_precondition(pg):
    supplier, raw, body = inputs(pg)
    body |= {"currency": "USD", "buyer_name": "Synthetic Buyer <script>bad()</script>"}
    body["lines"] *= 2
    body["lines"] = [
        {**line, "source_unit_price": "2.50", "source_amount": "7.50" if i == 0 else None}
        for i, line in enumerate(body["lines"])
    ]
    before = effects(pg)
    key = uuid4()
    result = ok(pg.api.command(BASE, body, key))
    assert result["currency"] == "USD" and result["total_amount"] is None
    assert result["lines"][0]["source_unit_price"] == "2.50"
    assert result["lines"][0]["source_amount"] == "7.50"
    assert result["lines"][1]["source_amount"] is None
    assert len(result["lines"]) == 2  # Same material on distinct source rows stays distinct.
    assert ok(pg.api.command(BASE, body, key)) == result
    assert pg.api.command(BASE, {**body, "buyer_name": "changed"}, key).status_code == 409
    after = effects(pg)
    for table in (
        "inventory_accounts",
        "inventory_ledger",
        "orders",
        "order_lines",
        "production_orders",
        "production_completions",
        "purchase_receipts",
    ):
        assert after[table] == before[table]
    printed = pg.api.request("GET", f"{BASE}/{result['id']}/print?locale=en")
    assert printed.status_code == 200
    assert "Purchase Order" in printed.text and "USD" in printed.text
    assert "2.50" in printed.text and "7.50" in printed.text
    assert "&lt;script&gt;bad()&lt;/script&gt;" in printed.text
    assert "<script>bad()" not in printed.text
    assert "Some amounts are not specified" in printed.text
    ok(
        pg.api.command(
            f"/api/v1/suppliers/{supplier['id']}",
            {
                "full_name": "Synthetic Renamed Supplier",
                "active": True,
                "expected_version": 1,
            },
        )
    )
    ok(
        pg.api.command(
            f"/api/v1/materials/{raw['id']}",
            {
                "kind": "raw",
                "name": "Synthetic Renamed Raw",
                "own_code": raw["own_code"],
                "unit": "KG",
                "active": True,
                "expected_version": raw["version"],
                "reason": "Synthetic edit",
            },
        )
    )
    assert pg.api.request("GET", f"{BASE}/{result['id']}/print?locale=en").text == printed.text


def test_zero_is_known_and_total_uses_saved_amounts_without_recalculation(pg):
    _, _, body = inputs(pg)
    body["currency"] = "CNY"
    body["lines"] = [
        {**body["lines"][0], "source_unit_price": "0", "source_amount": "0.00"},
        {**body["lines"][0], "source_unit_price": "2.50", "source_amount": "7.49"},
    ]
    result = ok(pg.api.command(BASE, body))
    assert result["total_amount"] == "7.49"
    assert result["lines"][0]["source_unit_price"] == "0"
    assert result["lines"][1]["source_amount"] == "7.49"


@pytest.mark.parametrize("value", ["", "-1", "NaN", "1e3", "1,000", "1.0000001", "1" * 19, 1.25])
def test_invalid_source_money_is_rejected_atomically(pg, value):
    _, _, body = inputs(pg)
    body["currency"] = "CNY"
    body["lines"][0]["source_unit_price"] = value
    before = effects(pg)
    assert pg.api.command(BASE, body).status_code == 422
    assert effects(pg) == before


def test_money_needs_explicit_currency_but_quantity_only_purchase_does_not(pg):
    _, _, body = inputs(pg)
    result = ok(pg.api.command(BASE, body))
    assert result["currency"] is None and result["total_amount"] is None
    body["lines"][0]["source_unit_price"] = "2.50"
    assert pg.api.command(BASE, body).json()["code"] == "CURRENCY_REQUIRED"


def test_same_file_purpose_isolation_old_sales_claim_and_archive_remain_separate(pg, monkeypatch):
    sales = source(pg, monkeypatch, "sales_order")
    purchase = source(pg, monkeypatch)
    duplicate = source(pg, monkeypatch)
    assert sales["source_id"] != purchase["source_id"] == duplicate["source_id"]
    listed = ok(pg.api.request("GET", "/api/v1/sources"))["items"]
    assert [s["source_id"] for s in listed] == [sales["source_id"]]
    listed = ok(pg.api.request("GET", "/api/v1/sources?purpose=purchase_order"))["items"]
    assert [s["source_id"] for s in listed] == [purchase["source_id"]]
    _, _, body = inputs(pg)
    bad = pg.api.command(
        BASE, {**body, "source_id": sales["source_id"], "extraction_id": sales["extraction_id"]}
    )
    assert bad.json()["code"] == "SOURCE_PURPOSE_MISMATCH"
    sales_body = order_body(pg) | {"extraction_id": purchase["extraction_id"]}
    assert pg.api.command("/api/v1/orders", sales_body).json()["code"] == "SOURCE_PURPOSE_MISMATCH"
    good = ok(
        pg.api.command(
            BASE,
            {
                **body,
                "source_id": purchase["source_id"],
                "extraction_id": purchase["extraction_id"],
            },
        )
    )
    assert good["source_id"] == purchase["source_id"]
    assert (
        ok(pg.api.request("GET", f"{BASE}/by-source/{purchase['source_id']}"))["id"] == good["id"]
    )


def test_same_purchase_source_concurrency_replay_and_run_matching(pg, monkeypatch):
    _, _, body = inputs(pg)
    first = source(pg, monkeypatch)
    second = source(pg, monkeypatch, suffix=b"other")
    wrong = {**body, "source_id": first["source_id"], "extraction_id": second["extraction_id"]}
    before = effects(pg)
    assert pg.api.command(BASE, wrong).json()["code"] == "SOURCE_RUN_MISMATCH"
    assert effects(pg) == before
    body |= {"source_id": first["source_id"], "extraction_id": first["extraction_id"]}
    keys = [uuid4(), uuid4()]

    def send(key):
        client = API(pg.app)
        client.login()
        return client.command(BASE, body, key)

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(send, keys))
    assert sorted(r.status_code for r in result) == [200, 409]
    index = next(i for i, r in enumerate(result) if r.status_code == 200)
    assert ok(pg.api.command(BASE, body, keys[index])) == result[index].json()
    assert ok(pg.api.request("GET", BASE))["total"] == 1


def test_source_only_manual_input_and_evidence_corruption_do_not_create_partial_order(
    pg, monkeypatch
):
    _, _, body = inputs(pg)
    uploaded = source(pg, monkeypatch, extract=False)
    body["source_id"] = uploaded["source_id"]
    with pg.owner.connect() as conn:
        blob = conn.execute(
            text("SELECT blob_hash FROM source_files WHERE id=:id"), {"id": uploaded["source_id"]}
        ).scalar_one()
    path = pg.objects / f"{blob}.json"
    original = path.read_bytes()
    path.write_bytes(b"synthetic corruption")
    before = effects(pg)
    failed = pg.api.command(BASE, body)
    assert failed.status_code == 503
    assert effects(pg) == before
    path.write_bytes(original)
    result = ok(pg.api.command(BASE, body))
    assert result["source_id"] == uploaded["source_id"] and result["extraction_id"] is None


@pytest.mark.parametrize("column,value", [("source_unit_price", "-1"), ("source_amount", "NaN")])
def test_runtime_database_rejects_invalid_money_and_currency(pg, column, value):
    _, _, body = inputs(pg)
    order = ok(pg.api.command(BASE, body))
    with pytest.raises(DBAPIError):
        with pg.runtime.engine.begin() as conn:
            conn.execute(
                text(f"UPDATE purchase_order_lines SET {column}=:value WHERE order_id=:id"),
                {"id": order["id"], "value": value},
            )


def test_print_read_requires_identity_and_write_is_forbidden_to_viewer(pg):
    _, _, body = inputs(pg)
    order = ok(pg.api.command(BASE, body))
    outsider = API(pg.app)
    assert outsider.request("GET", f"{BASE}/{order['id']}/print").status_code == 401
    with pytest.raises(BusinessError):
        pg.runtime.purchasing.create_order(
            type(pg.actor)(uuid4(), pg.actor.user_id, pg.actor.username, "operator"), uuid4(), body
        )
