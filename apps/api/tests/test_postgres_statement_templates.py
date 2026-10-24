import base64
import hashlib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.database import Journal
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_statement_exports import create
from test_statement_customer_templates import mapping, template_file


def upload_body(content=None):
    content = content or template_file()
    return {
        "filename": "synthetic-template.xlsx",
        "name": "合成客户模板",
        "content_base64": base64.b64encode(content).decode(),
        "inspected_sha256": hashlib.sha256(content).hexdigest(),
        "mapping": mapping(),
    }


def test_import_preview_pin_export_and_explicit_default(pg):
    delivery, _, statement, _ = create(pg, True)
    assert statement["lines"][0]["source"]["order_number"] == delivery["order_number"]
    path = f"/api/v1/customers/{pg.customer_id}/statement-templates"
    body = upload_body()
    inspected = pg.api.request(
        "POST", path + "/inspect", json={k: body[k] for k in ("filename", "content_base64")}
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["file_hash"] == body["inspected_sha256"]
    preview = pg.api.request(
        "POST",
        path + "/preview",
        json={
            **{k: body[k] for k in ("filename", "content_base64", "mapping", "inspected_sha256")},
            "statement_id": statement["id"],
            "expected_version": 1,
        },
    )
    assert preview.status_code == 200, preview.text
    assert "模板预览" in preview.json()["grid"][1][4]
    key = uuid4()
    imported = pg.api.command(path, body, key)
    assert imported.status_code == 200, imported.text
    first = imported.json()
    assert first["version"] == 1
    assert pg.api.command(path, body, key).json() == first
    assert pg.api.command(path, body | {"name": "另一合成名"}, key).status_code == 409
    assert (
        pg.api.request("GET", f"/api/v1/customers/{pg.customer_id}/statement-settings").json()
        is None
    )
    exported = pg.api.command(
        f"/api/v1/statements/{statement['id']}/exports",
        {
            "expected_version": 1,
            "template_id": "customer-v1",
            "customer_template_id": first["id"],
        },
    )
    assert exported.status_code == 200, exported.text
    record = exported.json()
    second = pg.api.command(path, body | {"name": "合成新版"}).json()
    assert second["version"] == 2
    generated = pg.api.request("POST", f"/api/v1/statement-exports/{record['id']}/generate")
    assert generated.json()["status"] == "ready", generated.text
    assert generated.json()["template_version"] == 1
    assert generated.json()["template_name"] == first["name"]
    downloaded = pg.api.request("GET", f"/api/v1/statement-exports/{record['id']}/file")
    sheet = load_workbook(BytesIO(downloaded.content)).active
    assert "草稿" in sheet["E2"].value and "模板预览" not in sheet["E2"].value
    assert sheet["G4"].value == "待定价"
    settings = pg.api.command(
        f"/api/v1/customers/{pg.customer_id}/statement-settings",
        {
            "expected_version": 0,
            "template_id": "customer-v1",
            "customer_template_id": second["id"],
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "reason": "合成默认格式",
        },
    )
    assert settings.status_code == 200, settings.text
    default_export = pg.api.command(
        f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1}
    ).json()
    assert default_export["customer_template_id"] == second["id"]
    assert default_export["template_version"] == 2
    assert (
        pg.api.request("GET", f"/api/v1/statement-exports/{record['id']}/file").content
        == downloaded.content
    )


def test_template_authorization_ownership_and_database_constraints(pg):
    _, _, statement, _ = create(pg)
    service = pg.runtime.statement_templates
    first = service.import_template(pg.actor, uuid4(), UUID(pg.customer_id), upload_body())
    other = pg.runtime.customers.create(pg.actor, uuid4(), "Synthetic Other Template Customer")
    outsider = Actor(uuid4(), uuid4(), "synthetic-outsider", "admin")
    viewer = replace(pg.actor, role="viewer")
    with pytest.raises(BusinessError) as error:
        service.import_template(viewer, uuid4(), UUID(pg.customer_id), upload_body())
    assert error.value.code == "WRITE_FORBIDDEN"
    with pytest.raises(BusinessError):
        service.detail(outsider, pg.customer_id, first["id"])
    assert service.detail(viewer, pg.customer_id, first["id"])["id"] == first["id"]
    with pytest.raises(BusinessError, match="STATEMENT_TEMPLATE_NOT_FOUND"):
        service.detail(pg.actor, other["id"], first["id"])
    settings = {
        "tax_mode": "untaxed_final",
        "tax_rate": "0",
        "reason": "Synthetic",
        "template_id": "customer-v1",
        "customer_template_id": first["id"],
    }
    with pytest.raises(BusinessError, match="STATEMENT_TEMPLATE_NOT_FOUND"):
        pg.runtime.statements.settings.save(pg.actor, uuid4(), other["id"], 0, settings)
    params = {"org": pg.actor.organization_id, "customer": other["id"], "template": first["id"]}
    queries = [
        "UPDATE statement_templates SET name='changed'",
        "DELETE FROM statement_templates",
        "INSERT INTO statement_customer_settings(organization_id,customer_id,version,"
        "tax_mode,tax_rate,template_id,customer_template_id) "
        "VALUES(:org,:customer,1,'untaxed_final',0,'customer-v1',:template)",
        "UPDATE statement_exports SET template_version=2",
    ]
    for query in queries:
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(query), params)
    # Check exact version and owner at INSERT too, independently of immutable UPDATE trigger.
    for custom_id, version, customer_id in [
        (first["id"], 2, pg.customer_id),
        (first["id"], 1, other["id"]),
        (None, 2, pg.customer_id),
    ]:
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(
                text("""INSERT INTO statement_exports(organization_id,id,statement_id,customer_id,
                statement_version,template_id,template_version,customer_template_id,snapshot)
                VALUES(:org,:id,:statement,:customer,1,:kind,:version,:template,'{}')"""),
                {
                    "org": pg.actor.organization_id,
                    "id": uuid4(),
                    "statement": statement["id"],
                    "customer": customer_id,
                    "kind": "customer-v1" if custom_id else "standard-v1",
                    "version": version,
                    "template": custom_id,
                },
            )
    with pg.runtime.engine.connect() as conn:
        assert not conn.scalar(
            text("SELECT has_table_privilege(current_user,'statement_templates','UPDATE')")
        )
        assert not conn.scalar(
            text("SELECT has_table_privilege(current_user,'statement_templates','DELETE')")
        )


def test_template_import_rollback_concurrency_replay_and_unused_backup_hashes(pg, monkeypatch):
    from factoryflow.modules.statements.adapters.template_repository import (
        StatementTemplateRepository,
    )

    service = pg.runtime.statement_templates
    body, key = upload_body(), uuid4()
    original_audit = Journal.audit

    def fail(self, actor, command, entity_id):
        if command == "statement.template.import":
            raise RuntimeError("synthetic audit failure")
        return original_audit(self, actor, command, entity_id)

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        service.import_template(pg.actor, key, UUID(pg.customer_id), body)
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_templates")) == 0
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM command_results "
                    "WHERE command_type='statement.template.import'"
                )
            )
            == 0
        )
    monkeypatch.setattr(Journal, "audit", original_audit)
    first = service.import_template(pg.actor, key, UUID(pg.customer_id), body)
    barrier = Barrier(2)

    def save(index):
        barrier.wait()
        return service.import_template(
            pg.actor, uuid4(), UUID(pg.customer_id), body | {"name": f"Synthetic {index}"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        saved = list(pool.map(save, range(2)))
    assert sorted(item["version"] for item in saved) == [2, 3]
    same_key = uuid4()

    def replay(_):
        return service.import_template(pg.actor, same_key, UUID(pg.customer_id), body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        replayed = list(pool.map(replay, range(2)))
    assert replayed[0] == replayed[1] and replayed[0]["version"] == 4
    page = service.listing(pg.actor, pg.customer_id, limit=2)
    assert [row["version"] for row in page["items"]] == [4, 3]
    assert [
        row["version"]
        for row in service.listing(pg.actor, pg.customer_id, page["next_cursor"], 2)["items"]
    ] == [2, 1]
    with pg.owner.connect() as conn:
        hashes = StatementTemplateRepository(conn).backup_hashes()
        assert hashes and conn.scalar(text("SELECT count(*) FROM statement_exports")) == 0
        assert (
            conn.scalar(
                text(
                    "SELECT count(*) FROM audit_events "
                    "WHERE command_type='statement.template.import'"
                )
            )
            == 4
        )
    assert service.detail(pg.actor, pg.customer_id, first["id"])["version"] == 1


def test_template_file_swap_coverage_and_preview_do_not_write_business(pg):
    _, original, statement, _ = create(pg)
    body = upload_body()
    path = f"/api/v1/customers/{pg.customer_id}/statement-templates"
    assert (
        pg.api.command(path, body | {"inspected_sha256": "0" * 64}).json()["code"]
        == "STATEMENT_TEMPLATE_FILE_CHANGED"
    )
    assert pg.api.command(path, body | {"content_base64": "broken"}).status_code == 422
    # Tax details can use the header; adjustments still need their own mapped position.
    chosen = mapping()
    for field in ("tax_base", "tax_amount", "adjustments"):
        chosen["cells"].pop(field)
    imported = pg.api.command(path, body | {"mapping": chosen}).json()
    assert "id" in imported
    updated = pg.api.command(
        f"/api/v1/statements/{statement['id']}/save",
        {
            **original,
            "expected_version": 1,
            "tax_mode": "add_tax",
            "tax_rate": "13",
            "adjustments": [
                {
                    "stage": "after_tax",
                    "kind": "Synthetic fixed fee",
                    "amount": "1",
                    "reason": "Synthetic fee needs an output position",
                }
            ],
            "reason": "Synthetic tax and adjustment change",
        },
    ).json()
    export = pg.api.command(
        f"/api/v1/statements/{statement['id']}/exports",
        {
            "expected_version": updated["version"],
            "template_id": "customer-v1",
            "customer_template_id": imported["id"],
        },
    )
    assert export.json()["code"] == "STATEMENT_TEMPLATE_COVERAGE"
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_exports")) == 1
        assert conn.scalar(text("SELECT count(*) FROM statement_templates")) == 1
    preview = pg.api.request(
        "POST",
        path + "/preview",
        json={
            **{k: body[k] for k in ("filename", "content_base64", "mapping", "inspected_sha256")},
            "statement_id": statement["id"],
            "expected_version": 1,
        },
    )
    assert preview.json()["code"] == "VERSION_CONFLICT"
