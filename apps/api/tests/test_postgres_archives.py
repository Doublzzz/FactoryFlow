"""Synthetic archive contracts on isolated PostgreSQL fixture databases."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from threading import Barrier
from uuid import uuid4
from zipfile import ZipFile

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services, create_app
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.modules.archives.adapters.repository import ArchiveRepository
from factoryflow.modules.fulfillment.application.archive import ArchiveDeliveries
from factoryflow.platform.database import Journal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_extraction import PNG, extracted
from test_postgres_orders import order_body
from test_postgres_statements import draft, source


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()


def test_settings_and_unclassified_original_preview(pg):
    settings = ok(pg.api.request("GET", "/api/v1/archive-settings"))
    assert settings["version"] == 0
    assert settings["rule"] == "month_customer"
    assert settings["root_configured"] is False
    payload = b"%PDF-1.4\nSYNTHETIC-ARCHIVE-ORIGINAL\n"
    source = pg.runtime.extraction.upload(
        pg.actor, uuid4(), "synthetic-order.pdf", "application/pdf", payload
    )
    items = ok(pg.api.request("GET", "/api/v1/archive-sources", params={"kind": "source"}))
    assert len(items["items"]) == 1 and items["next_cursor"] is None
    item = items["items"][0]
    assert item["key"] == "source:" + source["source_id"]
    assert item["business_date"] is None and item["customer_id"] is None
    preview = ok(
        pg.api.request(
            "POST",
            "/api/v1/archives/preview",
            json={
                "rule": "month_customer",
                "selections": [{"key": item["key"], "token": item["token"]}],
            },
        )
    )
    assert preview["items"][0]["path"].startswith("工作文件/待归类/订单原件/")
    assert preview["total_bytes"] == len(payload)
    assert len(preview["preview_token"]) == 64
    assert pg.runtime.extraction.original(pg.actor, source["source_id"])[1] == payload


@pytest.fixture
def enabled(pg, tmp_path):
    settings = replace(pg.settings, archive_root=tmp_path / "work-copies")
    runtime = build_services(settings)
    app = create_app(settings=settings)
    api = API(app)
    api.login()
    try:
        yield runtime.archives, api
    finally:
        runtime.close()
        app.state.services.close()


def uploaded(pg, suffix="one"):
    content = b"%PDF-1.4\nSYNTHETIC-ARCHIVE-" + suffix.encode() + b"\n"
    source = pg.runtime.extraction.upload(
        pg.actor, uuid4(), "synthetic.pdf", "application/pdf", content
    )
    return source, content


def selections(items):
    return [{"key": i["key"], "token": i["token"]} for i in items]


def prepare(service, actor, kinds=("source",), rule="month_customer"):
    items = [i for kind in kinds for i in service.catalog(actor, kind)["items"] if i["available"]]
    selected = selections(items)
    preview = service.preview(actor, rule, selected)
    return {
        "rule": rule,
        "selections": selected,
        "preview_token": preview["preview_token"],
    }, preview


def test_english_archive_freezes_language_and_legacy_default_replays(pg, enabled):
    service, api = enabled
    source(pg)
    selected = selections(service.catalog(pg.actor, "delivery")["items"])
    body = {"rule": "month_customer", "selections": selected, "locale": "en"}
    preview = ok(api.request("POST", "/api/v1/archives/preview", json=body))
    body["preview_token"] = preview["preview_token"]
    key = uuid4()
    batch = ok(api.command("/api/v1/archives", body, key))
    assert batch["locale"] == "en"
    assert batch["items"][0]["path"].startswith("Work files/")
    assert ok(api.command("/api/v1/archives", body, key))["id"] == batch["id"]
    changed = api.command("/api/v1/archives", body | {"locale": "zh-CN"}, key)
    assert changed.json()["code"] == "IDEMPOTENCY_CONFLICT"
    # A different language also needs a new matching preview, even under a new key.
    stale = api.command("/api/v1/archives", body | {"locale": "zh-CN"})
    assert stale.json()["code"] == "ARCHIVE_PREVIEW_STALE"
    ready = ok(api.request("POST", f"/api/v1/archives/{batch['id']}/generate"))
    assert ready["status"] == "ready"
    original = service.download(pg.actor, batch["id"])
    with ZipFile(BytesIO(original)) as archive:
        html = archive.read(batch["items"][0]["path"]).decode()
        assert "Delivery note" in html and "State at generation: Active" in html
        assert "manifest.json" in archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["locale"] == "en"
        assert manifest["items"][0]["state_label"] == "Active"
        assert manifest["items"][0]["version_label"].startswith("Delivery v")
    legacy_body, _ = prepare(service, pg.actor, kinds=("delivery",))
    old_key = uuid4()
    legacy = ok(api.command("/api/v1/archives", legacy_body, old_key))
    assert legacy["locale"] == "zh-CN"
    assert (
        ok(api.command("/api/v1/archives", legacy_body | {"locale": "zh-CN"}, old_key))["id"]
        == legacy["id"]
    )
    assert service.download(pg.actor, batch["id"]) == original


def test_installed_app_wires_archive_script_from_its_web_directory(pg, tmp_path, monkeypatch):
    from factoryflow.modules.fulfillment.adapters import archive_renderer

    source(pg)
    web = tmp_path / "bundled-web"
    web.mkdir()
    (web / "index.html").write_text("Synthetic app", encoding="utf-8")
    (web / "delivery-print.js").write_text("/* synthetic bundled paginator */", encoding="utf-8")
    monkeypatch.setattr(
        archive_renderer, "__file__", str(tmp_path / "missing/development/source.py")
    )
    app = create_app(
        settings=replace(pg.settings, archive_root=tmp_path / "copies"), web_directory=web
    )
    try:
        service = app.state.services.archives
        selected = selections(service.catalog(pg.actor, "delivery")["items"])
        preview = service.preview(pg.actor, "date", selected, "en")
        batch = service.create(pg.actor, uuid4(), "date", selected, preview["preview_token"], "en")
        assert service.generate(pg.actor, batch["id"])["status"] == "ready"
        with ZipFile(BytesIO(service.download(pg.actor, batch["id"]))) as archive:
            html = archive.read(batch["items"][0]["path"]).decode()
            assert "synthetic bundled paginator" in html and "Delivery note" in html
    finally:
        app.state.services.close()


def test_generation_zip_exactbytes_dedup_rules_and_immutable_history(pg, enabled):
    service, api = enabled
    _, content = uploaded(pg)
    body, preview = prepare(service, pg.actor)
    key = uuid4()
    created = ok(api.command("/api/v1/archives", body, key))
    assert created["status"] == "pending" and not created["local_available"]
    assert ok(api.command("/api/v1/archives", body, key))["id"] == created["id"]
    assert ok(api.command("/api/v1/archives", body))["id"] == created["id"]
    changed = body | {"rule": "date"}
    assert api.command("/api/v1/archives", changed, key).json()["code"] == "IDEMPOTENCY_CONFLICT"
    base = f"/api/v1/archives/{created['id']}"
    ready = ok(api.request("POST", base + "/generate"))
    assert ready["status"] == "ready" and ready["local_available"] and ready["current"]
    downloaded = api.request("GET", base + "/file")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == ready["file_hash"]
    with ZipFile(BytesIO(downloaded.content)) as archive:
        assert set(archive.namelist()) == {preview["items"][0]["path"], "清单.json"}
        assert archive.read(preview["items"][0]["path"]) == content
        manifest = json.loads(archive.read("清单.json"))
        assert manifest["type"] == "work-archive-v1" and manifest["id"] == created["id"]
    disk = service.copies.root / ready["relative_directory"] / preview["items"][0]["path"]
    assert disk.read_bytes() == content
    rule_key = uuid4()
    settings_body = {"expected_version": 0, "rule": "date"}
    saved = ok(api.command("/api/v1/archive-settings", settings_body, rule_key))
    assert ok(api.command("/api/v1/archive-settings", settings_body, rule_key)) == saved
    assert api.command("/api/v1/archive-settings", settings_body).status_code == 409
    new_body, _ = prepare(service, pg.actor, rule="date")
    assert ok(api.command("/api/v1/archives", new_body))["id"] != created["id"]
    assert service.download(pg.actor, created["id"]) == downloaded.content
    assert service.detail(pg.actor, created["id"])["rule"] == "month_customer"
    for query in (
        "UPDATE archive_batches SET input_hash=repeat('0',64)",
        "DELETE FROM archive_batches",
        "DELETE FROM archive_settings",
        "UPDATE archive_settings SET rule='customer'",
    ):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(query))


def test_confirmed_original_tokens_ignore_delivery_but_track_revision_and_claim(
    pg, enabled, monkeypatch
):
    service, _ = enabled
    document, run = extracted(pg, monkeypatch)
    pending_body, _ = prepare(service, pg.actor)
    pending = service.create(pg.actor, uuid4(), **pending_body)
    confirmed = ok(
        pg.api.command(
            "/api/v1/orders",
            order_body(pg, "SYN-ARCHIVE-CONFIRM") | {"extraction_id": run["extraction_id"]},
        )
    )
    assert not service.detail(pg.actor, pending["id"])["current"]
    with pytest.raises(BusinessError, match="ARCHIVE_PREVIEW_STALE"):
        service.create(pg.actor, uuid4(), **pending_body)
    item = service.catalog(pg.actor, "source")["items"][0]
    assert item["customer_id"] == pg.customer_id and item["business_date"] == "2026-09-30"
    captured_body, preview = prepare(service, pg.actor)
    assert "待归类" not in preview["items"][0]["path"]
    archive = service.create(pg.actor, uuid4(), **captured_body)
    service.generate(pg.actor, archive["id"])
    frozen = service.download(pg.actor, archive["id"])
    order = ok(pg.api.request("GET", f"/api/v1/orders/{confirmed['order_id']}"))
    delivery = ok(
        pg.api.command(
            "/api/v1/deliveries",
            {
                "order_id": order["id"],
                "customer_id": pg.customer_id,
                "revision_id": order["revision_id"],
                "expected_version": 1,
                "delivery_date": "2026-10-02",
                "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "0.1"}],
            },
        )
    )
    assert service.catalog(pg.actor, "source")["items"][0]["token"] == item["token"]
    assert service.detail(pg.actor, archive["id"])["current"]
    ok(
        pg.api.command(
            f"/api/v1/deliveries/{delivery['id']}/void",
            {"expected_version": 1, "reason": "Synthetic archive revision"},
        )
    )
    ok(
        pg.api.command(
            f"/api/v1/orders/{order['id']}/revisions",
            {
                "expected_version": 3,
                "reason": "Synthetic reclassification",
                "order": order_body(pg, "SYN-ARCHIVE-CONFIRM") | {"business_date": "2026-09-29"},
            },
        )
    )
    assert not service.detail(pg.actor, archive["id"])["current"]
    assert service.download(pg.actor, archive["id"], historical=True) == frozen
    assert pg.runtime.extraction.original(pg.actor, document["source_id"])[1] == PNG


def test_delivery_and_crossmonth_excel_snapshot_stale_download_and_pending_catalog(pg, enabled):
    service, api = enabled
    delivery = source(pg)
    draft_body = draft(pg, delivery, start="2026-09-20", end="2026-10-31")
    statement = ok(pg.api.command("/api/v1/statements", draft_body))
    pending = service.catalog(pg.actor, "statement_export")["items"]
    assert (
        len(pending) == 1 and not pending[0]["available"] and pending[0]["state_label"] == "未生成"
    )
    export = ok(
        pg.api.command(f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1})
    )
    pg.runtime.statement_exports.generate(pg.actor, export["id"])
    original_xlsx = pg.runtime.statement_exports.download(pg.actor, export["id"])[0]
    body, preview = prepare(service, pg.actor, ("delivery", "statement_export"))
    xlsx = next(i for i in preview["items"] if i["extension"] == "xlsx")
    assert "/2026/09/" in xlsx["path"] and "2026-10-31" in xlsx["path"]
    before = pg.runtime.orders.detail(pg.actor, delivery["order_id"])
    key = uuid4()
    batch = service.create(pg.actor, key, **body)
    ready = service.generate(pg.actor, batch["id"])
    content = service.download(pg.actor, batch["id"])
    with ZipFile(BytesIO(content)) as archive:
        assert archive.read(xlsx["path"]) == original_xlsx
        html = archive.read(
            next(i["path"] for i in preview["items"] if i["extension"] == "html")
        ).decode()
        assert 'src="/delivery-print.js"' not in html
        assert "生成时快照" in html and "完整明细" not in html and delivery["id"] in html
    assert pg.runtime.orders.detail(pg.actor, delivery["order_id"]) == before
    ok(
        pg.api.command(
            f"/api/v1/deliveries/{delivery['id']}/void",
            {"expected_version": 1, "reason": "Synthetic archive void"},
        )
    )
    assert not service.create(pg.actor, key, **body)["current"]  # replay reads a fresh snapshot
    assert not service.listing(pg.actor)["items"][0]["current"]
    refreshed = service.catalog(pg.actor, "statement_export")["items"]
    assert any(i["key"].startswith("statement_pending:") and not i["available"] for i in refreshed)
    assert (
        api.request("GET", f"/api/v1/archives/{batch['id']}/file").json()["code"] == "ARCHIVE_STALE"
    )
    assert service.download(pg.actor, batch["id"], historical=True) == content
    changed_body, changed_preview = prepare(service, pg.actor, ("delivery", "statement_export"))
    assert any(i["state_label"] == "已作废" for i in changed_preview["items"])
    historical = service.create(pg.actor, uuid4(), **changed_body)
    assert not historical["current"]  # old XLSX stays explicitly historical
    assert ready["file_hash"] == hashlib.sha256(content).hexdigest()


def test_scope_permissions_csrf_and_catalog_pagination(pg, enabled):
    service, api = enabled
    for value in ("one", "two", "three"):
        uploaded(pg, value)
    first = service.catalog(pg.actor, "source", limit=2)
    second = service.catalog(pg.actor, "source", first["next_cursor"], 2)
    assert len(first["items"]) == 2 and len(second["items"]) == 1 and second["next_cursor"] is None
    assert len({i["key"] for i in first["items"] + second["items"]}) == 3
    body, _ = prepare(service, pg.actor)
    batch = service.create(pg.actor, uuid4(), **body)
    other = Actor(uuid4(), uuid4(), "synthetic-other", "operator")
    assert service.catalog(other, "source")["items"] == []
    for action in (
        lambda: service.detail(other, batch["id"]),
        lambda: service.generate(other, batch["id"]),
        lambda: service.preview(other, body["rule"], body["selections"]),
    ):
        with pytest.raises(BusinessError) as error:
            action()
        assert error.value.status == 404
    pg.runtime.identity.add_user(pg.actor, "synthetic-archive-viewer", SYNTHETIC_PASSWORD, "viewer")
    viewer = API(api.app)
    viewer.login("synthetic-archive-viewer")
    assert viewer.request("GET", "/api/v1/archives").status_code == 200
    assert (
        viewer.request(
            "POST",
            "/api/v1/archives/preview",
            json={k: v for k, v in body.items() if k != "preview_token"},
        ).status_code
        == 200
    )
    assert viewer.command("/api/v1/archives", body).status_code == 403
    assert (
        viewer.command(
            "/api/v1/archive-settings", {"expected_version": 0, "rule": "date"}
        ).status_code
        == 403
    )
    assert viewer.request("POST", f"/api/v1/archives/{batch['id']}/generate").status_code == 403
    assert API(api.app).request("GET", "/api/v1/archives").status_code == 401
    assert (
        api.request(
            "POST",
            "/api/v1/archives",
            json=body,
            headers={"Idempotency-Key": str(uuid4()), "X-CSRF-Token": "wrong"},
        ).status_code
        == 403
    )


def test_archive_audit_rollback_and_published_directory_retry(pg, enabled, monkeypatch):
    service, _ = enabled
    uploaded(pg)
    body, _ = prepare(service, pg.actor)
    original = Journal.audit

    def fail(self, actor, command, identifier):
        if command.startswith("archive."):
            raise RuntimeError("Synthetic archive audit failure")
        return original(self, actor, command, identifier)

    key = uuid4()
    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic"):
        service.create(pg.actor, key, **body)
    assert service.listing(pg.actor)["items"] == []
    with pytest.raises(RuntimeError, match="Synthetic"):
        service.save_settings(pg.actor, uuid4(), 0, "date")
    assert service.settings(pg.actor)["version"] == 0
    monkeypatch.setattr(Journal, "audit", original)
    batch = service.create(pg.actor, key, **body)
    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic"):
        service.generate(pg.actor, batch["id"])
    partial = service.detail(pg.actor, batch["id"])
    assert partial["status"] == "pending" and partial["local_available"]
    monkeypatch.setattr(Journal, "audit", original)
    assert service.generate(pg.actor, batch["id"])["status"] == "ready"


def test_disk_failure_and_corrupt_copy_never_overwrite_ready(pg, enabled, monkeypatch):
    service, _ = enabled
    uploaded(pg)
    body, _ = prepare(service, pg.actor)
    batch = service.create(pg.actor, uuid4(), **body)
    original = service.copies.publish

    def fail(*args):
        raise OSError("Synthetic full disk")

    monkeypatch.setattr(service.copies, "publish", fail)
    failed = service.generate(pg.actor, batch["id"])
    assert failed["status"] == "failed" and failed["error_code"] == "ARCHIVE_WRITE_FAILED"
    monkeypatch.setattr(service.copies, "publish", original)
    ready = service.generate(pg.actor, batch["id"])
    content = service.download(pg.actor, batch["id"])
    copy = service.copies.root / ready["relative_directory"] / ready["items"][0]["path"]
    copy.write_bytes(b"SYNTHETIC-DAMAGE")
    damaged = service.detail(pg.actor, batch["id"])
    assert not damaged["local_available"] and damaged["local_error"] == "ARCHIVE_COPY_CONFLICT"
    with pytest.raises(BusinessError, match="ARCHIVE_COPY_CONFLICT"):
        service.generate(pg.actor, batch["id"])
    assert copy.read_bytes() == b"SYNTHETIC-DAMAGE"
    assert service.download(pg.actor, batch["id"]) == content
    assert service.detail(pg.actor, batch["id"])["status"] == "ready"


def test_concurrent_duplicate_batches_and_generation_have_one_identity(pg, enabled):
    service, _ = enabled
    uploaded(pg)
    body, _ = prepare(service, pg.actor)
    barrier = Barrier(2)
    key = uuid4()

    def create(_):
        barrier.wait(timeout=5)
        return service.create(pg.actor, key, **body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(create, range(2)))
    assert batches[0]["id"] == batches[1]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: service.generate(pg.actor, batches[0]["id"]), range(2)))
    assert results[0]["file_hash"] == results[1]["file_hash"] and results[0]["status"] == "ready"
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM archive_batches")).scalar() == 1
        assert len(ArchiveRepository(conn).backup_hashes()) == 2


def test_multisource_snapshot_during_concurrent_void_returns_history(pg, enabled, monkeypatch):
    service, _ = enabled
    delivery = source(pg)
    statement = ok(pg.api.command("/api/v1/statements", draft(pg, delivery)))
    export = ok(
        pg.api.command(f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1})
    )
    pg.runtime.statement_exports.generate(pg.actor, export["id"])
    body, _ = prepare(service, pg.actor, ("delivery", "statement_export"))
    original = ArchiveDeliveries.capture
    voided = False

    def capture(self, actor, key):
        nonlocal voided
        result = original(self, actor, key)
        if not voided:
            voided = True
            ok(
                pg.api.command(
                    f"/api/v1/deliveries/{delivery['id']}/void",
                    {"expected_version": 1, "reason": "Synthetic snapshot race"},
                )
            )
        return result

    monkeypatch.setattr(ArchiveDeliveries, "capture", capture)
    batch = service.create(pg.actor, uuid4(), **body)
    assert not batch["current"]
    assert all(i["current"] for i in batch["items"])  # both frozen before the concurrent void
    assert next(i for i in batch["items"] if i["kind"] == "delivery")["state_label"] == "有效"
