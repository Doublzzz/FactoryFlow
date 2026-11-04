"""Real transaction, source ownership and direct SQL purchase-document safeguards."""

from uuid import uuid4

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.modules.purchasing.adapters.repository import PurchasingRepository
from factoryflow.platform.database import Journal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_orders import order_body
from test_purchase_documents import BASE, effects, inputs, ok, source
from test_purchase_spreadsheet import workbook

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def direct_insert(pg, supplier, raw, header=None, money=None):
    with pg.runtime.engine.begin() as conn:
        result = PurchasingRepository(conn).insert_document(
            pg.actor,
            "purchase_orders",
            {
                "supplier_id": supplier["id"],
                "supplier_name": supplier["full_name"],
                "business_date": "2026-10-27",
                "number": None,
                "note": None,
                "currency": "CNY",
                "buyer_name": None,
                "source_id": None,
                "extraction_id": None,
                **(header or {}),
            },
            [
                {
                    "id": uuid4(),
                    "material_id": raw["id"],
                    "own_code": raw["own_code"],
                    "material_name": raw["name"],
                    "specification": raw["specification"],
                    "canonical_unit": "KG",
                    "quantity": "3",
                    "source_unit_price": None,
                    "source_amount": None,
                    **(money or {}),
                }
            ],
        )
        Journal(conn).audit(pg.actor, "purchase_order.create", result["id"])
        return result


def test_direct_insert_money_checks_and_currency_trigger_rollback_header(pg):
    supplier, raw, _ = inputs(pg)
    before = effects(pg)
    for column in ("source_unit_price", "source_amount"):
        for invalid in ("-1", "NaN", "1e2", "1.0000001", "9" * 19, ""):
            with pytest.raises(DBAPIError) as caught:
                direct_insert(pg, supplier, raw, money={column: invalid})
            assert column in caught.value.orig.diag.constraint_name
            assert effects(pg) == before
    with pytest.raises(DBAPIError, match="purchase currency required"):
        direct_insert(pg, supplier, raw, header={"currency": None}, money={"source_amount": "0"})
    assert effects(pg) == before
    result = direct_insert(
        pg, supplier, raw, money={"source_unit_price": "2.50", "source_amount": "7.50"}
    )
    assert result["total_amount"] == "7.50"


def test_direct_sql_source_purpose_run_pair_and_sales_reverse_guard(pg, monkeypatch):
    supplier, raw, body = inputs(pg)
    sales = source(pg, monkeypatch, "sales_order")
    first = source(pg, monkeypatch)
    second = source(pg, monkeypatch, suffix=b"second")
    before = effects(pg)
    with pytest.raises(DBAPIError, match="wrong source purpose"):
        direct_insert(pg, supplier, raw, header={"source_id": sales["source_id"]})
    for header, constraint in (
        (
            {"source_id": first["source_id"], "extraction_id": second["extraction_id"]},
            "purchase_order_extraction_fk",
        ),
        ({"extraction_id": first["extraction_id"]}, "purchase_order_extraction_source"),
    ):
        with pytest.raises(DBAPIError) as caught:
            direct_insert(pg, supplier, raw, header=header)
        assert caught.value.orig.diag.constraint_name == constraint
    assert effects(pg) == before
    order = ok(pg.api.command("/api/v1/orders", order_body(pg)))
    with pytest.raises(DBAPIError, match="wrong source purpose"):
        with pg.runtime.engine.begin() as conn:
            conn.execute(
                text("""INSERT INTO source_imports
                (organization_id,source_id,extraction_id,revision_id,order_id)
                VALUES(:org,:source,:run,:revision,:order)"""),
                {
                    "org": pg.actor.organization_id,
                    "source": first["source_id"],
                    "run": first["extraction_id"],
                    "revision": order["revision_id"],
                    "order": order["order_id"],
                },
            )
    ok(pg.api.command(BASE, {**body, "source_id": first["source_id"]}))
    with pytest.raises(DBAPIError) as caught:
        direct_insert(pg, supplier, raw, header={"source_id": first["source_id"]})
    assert caught.value.orig.diag.constraint_name == "purchase_order_source_unique"


def test_audit_failure_rolls_back_purchase_and_releases_source_for_same_key(pg, monkeypatch):
    _, _, body = inputs(pg)
    uploaded = source(pg, monkeypatch)
    body |= {key: uploaded[key] for key in ("source_id", "extraction_id")}
    before = effects(pg)
    original = Journal.audit

    def fail(self, actor, command, entity):
        if command == "purchase_order.create":
            raise RuntimeError("Synthetic required audit failure")
        return original(self, actor, command, entity)

    key = uuid4()
    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic required audit failure"):
        pg.runtime.purchasing.create_order(pg.actor, key, body)
    assert effects(pg) == before
    monkeypatch.setattr(Journal, "audit", original)
    saved = pg.runtime.purchasing.create_order(pg.actor, key, body)
    assert saved["source_id"] == uploaded["source_id"]
    assert pg.runtime.purchasing.create_order(pg.actor, key, body) == saved


def test_viewer_can_read_print_but_cannot_create_or_upload(pg):
    _, _, body = inputs(pg)
    order = ok(pg.api.command(BASE, body))
    pg.runtime.identity.add_user(pg.actor, "synthetic-viewer", SYNTHETIC_PASSWORD, "viewer")
    viewer = API(pg.app)
    viewer.login("synthetic-viewer")
    assert viewer.request("GET", f"{BASE}/{order['id']}/print").status_code == 200
    before = effects(pg)
    assert viewer.command(BASE, body).status_code == 403
    assert (
        viewer.request(
            "POST",
            "/api/v1/sources?purpose=purchase_order",
            content=workbook(),
            headers={
                "Idempotency-Key": str(uuid4()),
                "X-Filename": "synthetic.xlsx",
                "Content-Type": MIME,
            },
        ).status_code
        == 403
    )
    assert effects(pg) == before


def upload_sheet(pg, content):
    upload = ok(
        pg.api.request(
            "POST",
            "/api/v1/sources?purpose=purchase_order",
            content=content,
            headers={
                "Idempotency-Key": str(uuid4()),
                "X-Filename": "synthetic.xlsx",
                "Content-Type": MIME,
            },
        )
    )
    extraction = ok(pg.api.command(f"/api/v1/sources/{upload['source_id']}/extractions", {}))
    return upload, ok(pg.api.request("GET", f"/api/v1/extractions/{extraction['extraction_id']}"))


def test_xlsx_http_full_evidence_mapping_download_and_sales_archive_exclusion(pg, monkeypatch):
    sales = source(pg, monkeypatch, "sales_order")
    content = workbook()
    uploaded, detail = upload_sheet(pg, content)
    assert (
        detail["purpose"] == "purchase_order"
        and detail["spreadsheet"]["sheet_name"] == "Synthetic Purchase"
    )
    assert detail["candidate"]["lines"][0]["source_amount"] == "7.50"
    download = pg.api.request("GET", f"/api/v1/sources/{uploaded['source_id']}/download")
    assert download.content == content and ".xlsx" in download.headers["content-disposition"]
    mapped = ok(
        pg.api.command(
            f"/api/v1/extractions/{detail['extraction_id']}/purchase-preview",
            detail["spreadsheet"]["suggested_mapping"],
        )
    )
    assert mapped == detail["candidate"]
    catalog = ok(pg.api.request("GET", "/api/v1/archive-sources?kind=source"))
    assert [item["key"] for item in catalog["items"]] == ["source:" + sales["source_id"]]
    _, _, body = inputs(pg)
    body |= {
        "source_id": uploaded["source_id"],
        "extraction_id": detail["extraction_id"],
        "currency": "USD",
    }
    body["lines"][0] |= {"source_unit_price": "2.50", "source_amount": "7.50"}
    assert ok(pg.api.command(BASE, body))["total_amount"] == "7.50"


@pytest.mark.parametrize(
    "case,code",
    [("merged", "PURCHASE_SHEET_MERGED_DETAIL"), ("overflow", "PURCHASE_IMPORT_TOO_MANY_LINES")],
)
def test_unsupported_detail_cannot_be_claimed_or_previewed_as_complete_purchase(pg, case, code):
    content = (
        workbook(rows=201)
        if case == "overflow"
        else workbook(change=lambda _, sheet: sheet.merge_cells("B4:C4"))
    )
    upload, detail = upload_sheet(pg, content)
    assert detail["error_code"] == code
    _, _, body = inputs(pg)
    before = effects(pg)
    body["source_id"] = upload["source_id"]
    assert pg.api.command(BASE, body).json()["code"] == "PURCHASE_EXTRACTION_REQUIRED"
    body["extraction_id"] = detail["extraction_id"]
    assert pg.api.command(BASE, body).json()["code"] == code
    mapping = detail["spreadsheet"]["suggested_mapping"] | {"last_row": 4}
    assert (
        pg.api.command(
            f"/api/v1/extractions/{detail['extraction_id']}/purchase-preview", mapping
        ).json()["code"]
        == code
    )
    assert effects(pg) == before
