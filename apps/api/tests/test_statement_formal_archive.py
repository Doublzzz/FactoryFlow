"""Formal archives contain the frozen confirmation trail and original evidence bytes."""

import base64
import json
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.modules.statements.adapters.archive_repository import ArchiveStatementRepository
from factoryflow.modules.statements.application.archive import ArchiveStatements
from test_postgres_statement_lifecycle import (
    approve,
    blank,
    command,
    detail,
    reserve,
    settle,
    setup_statement,
)


def formal_case(pg):
    statement, source, sent, feedback = setup_statement(pg)
    attachment = b"%PDF-1.7\nSynthetic approved quantity and price\n"
    file_feedback = command(
        pg,
        f"/api/v1/statements/{statement['id']}/feedback",
        {
            "person": "Synthetic File Contact",
            "occurred_on": "2026-10-03",
            "note": "Synthetic signed feedback",
            "filename": "synthetic.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(attachment).decode(),
        },
    )
    approval = approve(pg, statement, source, sent, file_feedback, "60")
    phone_approval = approve(pg, statement, source, sent, feedback, "30")
    review = command(
        pg,
        f"/api/v1/statements/{statement['id']}/review",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            **source,
            "quantity": "10",
            "reason": "Synthetic unresolved quantity",
        },
    )
    reserve(pg, statement, approval, "60")
    formal = settle(pg, statement)
    export = command(
        pg,
        f"/api/v1/statements/{statement['id']}/exports",
        {
            "expected_version": formal["version"],
        },
    )
    response = pg.api.request("POST", f"/api/v1/statement-exports/{export['id']}/generate")
    assert response.status_code == 200 and response.json()["status"] == "ready", response.text
    return (
        statement,
        approval,
        phone_approval,
        review,
        sent,
        feedback,
        file_feedback,
        attachment,
        formal,
        export,
    )


def capture(pg, export):
    with pg.owner.connect() as conn:
        facade = ArchiveStatements(
            ArchiveStatementRepository(conn), pg.runtime.statement_exports.store
        )
        return facade.capture(pg.actor, f"statement_export:{export['id']}")


def test_formal_catalog_is_complete_material_package(pg):
    *_, export = formal_case(pg)
    response = pg.api.request("GET", "/api/v1/archive-sources", params={"kind": "statement_export"})
    assert response.status_code == 200, response.text
    item = next(row for row in response.json()["items"] if row["source_id"] == export["id"])
    assert item["title"] == "正式对账资料包"
    assert item["extension"] == "zip"
    assert item["available"] and item["current"]
    assert item["byte_size"] > 0


def test_formal_materials_pin_originals_and_versions_after_later_changes(pg, monkeypatch):
    (
        statement,
        approval,
        phone,
        review,
        sent,
        feedback,
        file_feedback,
        attachment,
        formal,
        export,
    ) = formal_case(pg)
    metadata, content = capture(pg, export)
    assert metadata["extension"] == "zip" and metadata["byte_size"] == len(content)
    assert capture(pg, export)[1] == content
    prefix = f"statements/{statement['id']}/v{formal['version']}"
    original_excel = pg.runtime.statement_exports.download(pg.actor, export["id"])[0]
    with ZipFile(BytesIO(content)) as zipped:
        assert all(entry.date_time == (1980, 1, 1, 0, 0, 0) for entry in zipped.infolist())
        assert zipped.read(f"{prefix}/statement.xlsx") == original_excel
        confirmation = json.loads(zipped.read(f"{prefix}/confirmation.json"))
        assert confirmation["statement"]["approval_refs"] == formal["approval_refs"]
        assert confirmation["statement"]["calculation"]["total"] == "600.00"
        for item in (approval, phone):
            saved = json.loads(zipped.read(f"approvals/{item['id']}/v{item['version']}.json"))
            assert str(saved["quantity"]) == item["quantity"]
            assert saved["sent_id"] == sent["id"]
        assert zipped.read(f"evidence/{file_feedback['id']}.pdf") == attachment
        telephone = json.loads(zipped.read(f"evidence/{feedback['id']}.json"))
        assert telephone["person"] == feedback["person"] and telephone["object_hash"] is None
        assert (
            zipped.read(f"sent-exports/{sent['export_id']}.xlsx")
            == pg.runtime.statement_exports.download(
                pg.actor,
                sent["export_id"],
                historical=True,
            )[0]
        )
        assert (
            json.loads(zipped.read(f"{prefix}/formal-history/v{formal['version']}.json"))["action"]
            == "settle"
        )
    following = blank(pg, "2026-11-01", "2026-11-30")
    command(
        pg,
        f"/api/v1/statements/{following['id']}/claim-review",
        {
            "expected_version": 1,
            "review_id": review["id"],
            "review_version": review["version"],
            "quantity": "6",
            "unit_price": "10",
            "reason": "Synthetic partial review resolution",
        },
    )
    assert capture(pg, export)[1] == content
    correction_bytes = b"\xff\xd8\xffSynthetic corrected confirmation"
    evidence = command(
        pg,
        f"/api/v1/statements/{statement['id']}/feedback",
        {
            "person": "Synthetic Correction Contact",
            "occurred_on": "2026-10-04",
            "note": "Synthetic correction evidence",
            "filename": "synthetic-correction.jpg",
            "media_type": "image/jpeg",
            "content_base64": base64.b64encode(correction_bytes).decode(),
        },
    )
    body = {
        "expected_version": formal["version"],
        "allocation_id": formal["settlement_lines"][0]["allocation_id"],
        "quantity": "55",
        "unit_price": "10",
        "disposition": "pending",
        "evidence_id": evidence["id"],
        "cause": "entry_error",
        "no_downstream_effects": True,
        "reason": "Synthetic formal correction",
    }
    preview = command(pg, f"/api/v1/statements/{statement['id']}/correction-preview", body)
    assert preview["blockers"] == [], preview
    corrected = command(
        pg,
        f"/api/v1/statements/{statement['id']}/correct",
        body | {"preview_token": preview["token"]},
    )
    revised_export = command(
        pg,
        f"/api/v1/statements/{statement['id']}/exports",
        {"expected_version": corrected["version"]},
    )
    assert (
        pg.runtime.statement_exports.generate(pg.actor, revised_export["id"])["status"] == "ready"
    )
    historical_metadata, historical_content = capture(pg, export)
    assert not historical_metadata["current"] and historical_content == content
    _, revised = capture(pg, revised_export)
    new_prefix = f"statements/{statement['id']}/v{corrected['version']}"
    with ZipFile(BytesIO(revised)) as zipped:
        assert zipped.read(f"evidence/{evidence['id']}.jpg") == correction_bytes
        assert f"{new_prefix}/formal-history/v{formal['version']}.json" in zipped.namelist()
        assert f"{new_prefix}/formal-history/v{corrected['version']}.json" in zipped.namelist()
        assert f"approvals/{approval['id']}/v1.json" in zipped.namelist()
        latest = next(
            item for item in corrected["approval_refs"] if item["approval_id"] == approval["id"]
        )
        assert f"approvals/{approval['id']}/v{latest['version']}.json" in zipped.namelist()
    with pg.owner.connect() as conn:
        repo = ArchiveStatementRepository(conn)
        other = Actor(uuid4(), pg.actor.user_id, "synthetic-other", "operator")
        with pytest.raises(BusinessError, match="STATEMENT_EXPORT_NOT_FOUND"):
            repo.get(other, f"statement_export:{export['id']}")
        row = repo.get(pg.actor, f"statement_export:{export['id']}")
        with pytest.raises(BusinessError, match="EVIDENCE_INTEGRITY_FAILED"):
            repo.formal_material(other, row)
        monkeypatch.setattr("factoryflow.modules.statements.application.archive.MAX_BYTES", 1)
        facade = ArchiveStatements(repo, pg.runtime.statement_exports.store)
        with pytest.raises(BusinessError, match="ARCHIVE_LIMIT_EXCEEDED"):
            facade.describe(pg.actor, f"statement_export:{export['id']}")


def test_next_period_package_uses_exact_referenced_approval_version(pg):
    statement, _, phone, _, sent, feedback, _, _, _, export = formal_case(pg)
    original = capture(pg, export)[1]
    following = blank(pg, "2026-11-01", "2026-11-30")
    target = {
        "expected_version": phone["version"],
        "target_start": "2026-11-01",
        "target_end": "2026-11-30",
        "reason": "Synthetic next-period recognition",
    }
    preview = command(pg, f"/api/v1/statement-approvals/{phone['id']}/defer-preview", target)
    deferred = command(
        pg,
        f"/api/v1/statement-approvals/{phone['id']}/defer",
        target | {"preview_token": preview["token"]},
    )
    reserve(pg, following, deferred, "30")
    formal = settle(pg, following)
    selected = command(
        pg, f"/api/v1/statements/{following['id']}/exports", {"expected_version": formal["version"]}
    )
    assert pg.runtime.statement_exports.generate(pg.actor, selected["id"])["status"] == "ready"
    _, content = capture(pg, selected)
    with ZipFile(BytesIO(content)) as zipped:
        approval = json.loads(zipped.read(f"approvals/{phone['id']}/v{deferred['version']}.json"))
        assert approval["statement_id"] == statement["id"]
        assert approval["target_start"] == "2026-11-01"
        assert f"sent-exports/{sent['export_id']}.xlsx" in zipped.namelist()
        assert f"evidence/{feedback['id']}.json" in zipped.namelist()
    assert capture(pg, export)[1] == original


def test_received_next_period_feedback_is_frozen_into_formal_package(pg):
    _, _, phone, _, _, _, _, _, _, _ = formal_case(pg)
    following = blank(pg, "2026-11-01", "2026-11-30")
    target = {
        "expected_version": phone["version"],
        "target_start": "2026-11-01",
        "target_end": "2026-11-30",
        "reason": "Synthetic next-period settlement",
    }
    preview = command(pg, f"/api/v1/statement-approvals/{phone['id']}/defer-preview", target)
    deferred = command(
        pg,
        f"/api/v1/statement-approvals/{phone['id']}/defer",
        target | {"preview_token": preview["token"]},
    )
    reserve(pg, following, deferred, "30")
    original = b"%PDF-1.7\nSynthetic second-period countersignature\n"
    file_feedback = command(
        pg,
        f"/api/v1/statements/{following['id']}/feedback",
        {
            "person": "Synthetic Second Period Signer",
            "occurred_on": "2026-11-03",
            "note": "Synthetic received countersignature",
            "filename": "synthetic-second-period.pdf",
            "media_type": "application/pdf",
            "content_base64": base64.b64encode(original).decode(),
        },
    )
    phone_feedback = command(
        pg,
        f"/api/v1/statements/{following['id']}/feedback",
        {
            "person": "Synthetic Second Period Contact",
            "occurred_on": "2026-11-03",
            "note": "Synthetic second-period telephone confirmation",
        },
    )
    body = {
        "expected_version": detail(pg, following["id"])["version"],
        "fees_confirmed": True,
        "reconfirmation": "received",
        "reason": "Synthetic second-period feedback received",
    }
    preview = command(pg, f"/api/v1/statements/{following['id']}/settlement-preview", body)
    assert preview["blockers"] == [], preview
    formal = command(
        pg,
        f"/api/v1/statements/{following['id']}/settle",
        body | {"preview_token": preview["token"]},
    )
    assert set(formal["confirmation_evidence_ids"]) == {file_feedback["id"], phone_feedback["id"]}
    export = command(
        pg, f"/api/v1/statements/{following['id']}/exports", {"expected_version": formal["version"]}
    )
    assert pg.runtime.statement_exports.generate(pg.actor, export["id"])["status"] == "ready"
    _, package = capture(pg, export)
    with ZipFile(BytesIO(package)) as zipped:
        assert f"evidence/{file_feedback['id']}.pdf" in zipped.namelist()
        assert zipped.read(f"evidence/{file_feedback['id']}.pdf") == original
        saved_phone = json.loads(zipped.read(f"evidence/{phone_feedback['id']}.json"))
        assert saved_phone["note"] == phone_feedback["note"]
    later = command(
        pg,
        f"/api/v1/statements/{following['id']}/feedback",
        {
            "person": "Synthetic Later Contact",
            "occurred_on": "2026-11-04",
            "note": "Synthetic feedback recorded after formal confirmation",
        },
    )
    assert detail(pg, following["id"]) == formal
    assert capture(pg, export)[1] == package
    with ZipFile(BytesIO(package)) as zipped:
        assert f"evidence/{later['id']}.json" not in zipped.namelist()
