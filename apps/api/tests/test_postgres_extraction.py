import hashlib
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.database import Journal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_orders import counts, order_body

PNG = b"\x89PNG\r\n\x1a\nsynthetic-stub"


def extracted(pg, monkeypatch):
    def stub(content, media_type):
        return {"status": "ready", "error_code": None, "pages": [], "engine": "synthetic-test"}

    monkeypatch.setattr(pg.runtime.extraction.extractor, "extract", stub)
    source = pg.runtime.extraction.upload(pg.actor, uuid4(), "synthetic.png", "image/png", PNG)
    run = pg.runtime.extraction.extract(pg.actor, uuid4(), UUID(source["source_id"]))
    return source, run


def test_source_confirm_preserves_trace_and_human_correction_restart_and_revision(pg, monkeypatch):
    source, run = extracted(pg, monkeypatch)
    body = order_body(pg, "SYN-HUMAN-CORRECTED") | {"extraction_id": run["extraction_id"]}
    key = uuid4()
    first = pg.api.command("/api/v1/orders", body, key)
    assert first.status_code == 200, first.text
    assert pg.api.command("/api/v1/orders", body, key).json() == first.json()
    evidence = pg.api.request("GET", f"/api/v1/documents/{first.json()['revision_id']}/download")
    assert hashlib.sha256(evidence.content).hexdigest() == first.json()["sha256"]
    assert evidence.json()["schema_version"] == 2
    assert evidence.json()["source"]["source_id"] == source["source_id"]
    assert evidence.json()["order"]["order_number"] == "SYN-HUMAN-CORRECTED"
    assert (
        pg.api.request("GET", "/api/v1/sources").json()["items"][0]["order_id"]
        == first.json()["order_id"]
    )
    original = pg.api.request("GET", f"/api/v1/sources/{source['source_id']}/download")
    assert original.content == PNG
    detail = pg.api.request("GET", f"/api/v1/extractions/{run['extraction_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["candidate"]["lines"] == []
    revised = pg.api.command(
        f"/api/v1/orders/{first.json()['order_id']}/revisions",
        {
            "expected_version": 1,
            "reason": "Synthetic correction",
            "order": order_body(pg, "SYN-HUMAN-CORRECTED"),
        },
    )
    assert revised.status_code == 200, revised.text
    new_evidence = pg.api.request(
        "GET", f"/api/v1/documents/{revised.json()['revision_id']}/download"
    )
    assert new_evidence.json()["source"] == evidence.json()["source"]


def test_source_duplicate_upload_and_same_key_conflict(pg, monkeypatch):
    source, run = extracted(pg, monkeypatch)
    duplicate = pg.runtime.extraction.upload(pg.actor, uuid4(), "renamed.png", "image/png", PNG)
    assert duplicate == source
    key = uuid4()
    assert pg.runtime.extraction.extract(
        pg.actor, key, UUID(source["source_id"])
    ) == pg.runtime.extraction.extract(pg.actor, key, UUID(source["source_id"]))
    other = pg.runtime.extraction.upload(pg.actor, uuid4(), "other.png", "image/png", PNG + b"x")
    with pytest.raises(BusinessError, match="IDEMPOTENCY_CONFLICT"):
        pg.runtime.extraction.extract(pg.actor, key, UUID(other["source_id"]))
    body = order_body(pg) | {"extraction_id": run["extraction_id"]}
    first = pg.api.command("/api/v1/orders", body)
    assert first.status_code == 200, first.text
    body["order_number"] = "SYN-OTHER"
    assert pg.api.command("/api/v1/orders", body).json()["code"] == "SOURCE_ALREADY_IMPORTED"


def test_header_table_candidate_reaches_api_and_keeps_legacy_retry_fingerprint(pg, monkeypatch):
    from test_table_candidate import page

    layout = page(
        [
            [(40, 80, "产品名称"), (300, 40, "单位"), (500, 40, "数量"), (700, 40, "金额")],
            [(40, 120, "合成材料"), (300, 30, "KG"), (500, 30, "12"), (700, 60, "144.00")],
        ]
    ) | {"number": 1, "width": 900, "height": 200, "text": "synthetic table"}
    monkeypatch.setattr(
        pg.runtime.extraction.extractor,
        "extract",
        lambda *_: {
            "status": "ready",
            "error_code": None,
            "pages": [layout],
            "engine": "synthetic-test",
        },
    )
    source = pg.runtime.extraction.upload(pg.actor, uuid4(), "synthetic.png", "image/png", PNG)
    source_id = UUID(source["source_id"])
    before = counts(pg)
    key = uuid4()
    first = pg.runtime.extraction.extract(pg.actor, key, source_id)
    detail = pg.api.request("GET", f"/api/v1/extractions/{first['extraction_id']}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["candidate"]["lines"] == [
        {
            "description": "合成材料",
            "item_code": None,
            "item_name": None,
            "specification": None,
            "quantity": "12",
            "unit": "KG",
            "source_unit_price": None,
            "source_amount": "144.00",
        }
    ]
    assert counts(pg)[:4] == before[:4]
    with pg.owner.begin() as conn:
        assert (
            Journal(conn).claim(
                pg.actor,
                "source.extract",
                key,
                {"source_id": str(source_id), "parser_version": "simple-rows-v1"},
            )
            == first
        )
    assert pg.runtime.extraction.extract(pg.actor, key, source_id) == first


def test_concurrent_imports_and_audit_rollback(pg, monkeypatch):
    source, run = extracted(pg, monkeypatch)
    body = order_body(pg) | {"extraction_id": run["extraction_id"]}
    before = counts(pg)
    audit = Journal.audit

    def fail(self, actor, command, entity):
        if command == "order.confirm":
            raise RuntimeError("synthetic audit failure")
        audit(self, actor, command, entity)

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError):
        pg.runtime.orders.confirm(pg.actor, uuid4(), body)
    assert counts(pg) == before
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM source_imports")).scalar_one() == 0
    monkeypatch.setattr(Journal, "audit", audit)

    def confirm(index):
        try:
            return pg.runtime.orders.confirm(
                pg.actor, uuid4(), body | {"order_number": f"SYN-RACE-{index}"}
            )
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(confirm, range(2)))
    assert sum(isinstance(r, dict) for r in results) == 1
    assert "SOURCE_ALREADY_IMPORTED" in results


def test_ownership_viewer_and_immutable_sources(pg, monkeypatch):
    source, run = extracted(pg, monkeypatch)
    stranger = Actor(uuid4(), uuid4(), "synthetic-other", "admin")
    with pytest.raises(BusinessError, match="SOURCE_NOT_FOUND"):
        pg.runtime.extraction.original(stranger, UUID(source["source_id"]))
    with pytest.raises(BusinessError, match="EXTRACTION_NOT_FOUND"):
        pg.runtime.extraction.detail(stranger, UUID(run["extraction_id"]))
    viewer = Actor(pg.actor.organization_id, pg.actor.user_id, "synthetic-viewer", "viewer")
    with pytest.raises(BusinessError, match="WRITE_FORBIDDEN"):
        pg.runtime.extraction.extract(viewer, uuid4(), UUID(source["source_id"]))
    for table in ("source_files", "extraction_runs"):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(f"DELETE FROM {table}"))


def test_upload_http_limits_csrf_and_failed_ocr_manual_fallback(pg, monkeypatch):
    headers = {
        "Idempotency-Key": str(uuid4()),
        "X-Filename": "synthetic.png",
        "Content-Type": "image/png",
    }
    forbidden = pg.api.request(
        "POST", "/api/v1/sources", content=PNG, headers=headers | {"x-csrf-token": "invalid"}
    )
    assert forbidden.status_code == 403
    invalid = pg.api.request("POST", "/api/v1/sources", content=b"synthetic", headers=headers)
    assert invalid.json()["code"] == "FILE_TYPE_UNSUPPORTED"
    too_big = pg.api.request(
        "POST", "/api/v1/sources", content=PNG + b"x" * (10 * 1024 * 1024), headers=headers
    )
    assert too_big.status_code == 413
    assert pg.api.request("GET", "/api/v1/sources").json()["items"] == []
    upload = pg.api.request("POST", "/api/v1/sources", content=PNG, headers=headers)
    assert upload.status_code == 200, upload.text
    source_id = upload.json()["source_id"]
    monkeypatch.setattr(
        pg.runtime.extraction.extractor,
        "extract",
        lambda *args: {"status": "failed", "error_code": "OCR_UNAVAILABLE", "pages": []},
    )
    run = pg.runtime.extraction.extract(pg.actor, uuid4(), UUID(source_id))
    assert run["status"] == "failed"
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM orders")).scalar_one() == 0
    response = pg.api.command(
        "/api/v1/orders", order_body(pg) | {"extraction_id": run["extraction_id"]}
    )
    assert response.status_code == 200, response.text
    evidence = pg.api.request("GET", f"/api/v1/documents/{response.json()['revision_id']}").json()
    assert evidence["content"]["source"]["extraction_id"] == run["extraction_id"]
