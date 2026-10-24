"""Owned synthetic databases: template object closure and additive legacy recovery."""

import json
from uuid import UUID, uuid4, uuid7

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.modules.statements.domain.draft import calculate, prepare_draft
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_archive_migration import BINARY, owned_database
from test_order_contract import payload
from test_postgres_statement_exports import create
from test_postgres_statement_templates import upload_body
from test_statement_customer_templates import altered_file


def seed_legacy_business(runtime, actor, customer_id):
    """Frozen pre-0012 statement columns; current services must not write old schemas."""
    confirmed = runtime.orders.confirm(actor, uuid4(), payload() | {"customer_id": customer_id})
    order = runtime.orders.detail(actor, confirmed["order_id"])
    delivery = runtime.deliveries.create(
        actor,
        uuid4(),
        {
            "order_id": confirmed["order_id"],
            "customer_id": customer_id,
            "revision_id": confirmed["revision_id"],
            "expected_version": 1,
            "delivery_date": "2026-10-02",
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "0.5"}],
        },
    )
    body = prepare_draft(
        {
            "customer_id": customer_id,
            "period_start": "2026-10-01",
            "period_end": "2026-10-31",
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "adjustments": [],
            "lines": [
                {
                    "delivery_id": delivery["id"],
                    "order_line_id": order["lines"][0]["id"],
                    "quantity": "0.25",
                    "unit_price": "2",
                    "reason": "Synthetic recovery claim",
                }
            ],
        }
    )
    identifier, export_id, key = uuid7(), uuid7(), uuid4()
    with runtime.statements.transaction() as work:
        work.journal.claim(actor, "statement.create", key, body)
        customer = work.customers.lock(actor, UUID(customer_id))
        work.statements.create(actor, identifier, body, customer)
        lines = runtime.statements.resolve(work, actor, body)
        for line in lines:
            work.statements.conn.execute(
                text("""
                INSERT INTO statement_lines(organization_id,statement_id,customer_id,
                delivery_id,order_line_id,quantity,unit_price,status,reason,source)
                VALUES(:org,:statement,:customer,:delivery,:line,:quantity,:price,
                :status,:reason,CAST(:source AS jsonb))
            """),
                {
                    "org": actor.organization_id,
                    "statement": identifier,
                    "customer": customer_id,
                    "delivery": line["delivery_id"],
                    "line": line["order_line_id"],
                    "quantity": line["quantity"],
                    "price": line["unit_price"],
                    "status": line["status"],
                    "reason": line["reason"],
                    "source": json.dumps(line["source"]),
                },
            )
        statement = {
            k: body[k]
            for k in (
                "customer_id",
                "period_start",
                "period_end",
                "tax_mode",
                "tax_rate",
                "adjustments",
            )
        }
        statement.update(
            id=str(identifier),
            customer_name=customer["full_name"],
            status="draft",
            version=1,
            lines=lines,
            settlement_lines=[],
            fees_confirmed=False,
            reconfirmation="unknown",
            correction=None,
            approval_refs=[],
            confirmation_evidence_ids=[],
            calculation=calculate(lines, body["tax_mode"], body["tax_rate"], []),
        )
        work.statements.conn.execute(
            text("""
            INSERT INTO statement_events(organization_id,id,statement_id,version,action,
            reason,actor_id,snapshot) VALUES(:org,:id,:statement,1,'create','',:actor,
            CAST(:snapshot AS jsonb))
        """),
            {
                "org": actor.organization_id,
                "id": uuid7(),
                "statement": identifier,
                "actor": actor.user_id,
                "snapshot": json.dumps(statement),
            },
        )
        snapshot = {
            "id": str(export_id),
            "template_id": "standard-v1",
            "template_version": 1,
            "calculation_version": 1,
            "statement": statement,
        }
        work.exports.create(actor, snapshot)
        statement = {
            **statement,
            "history": [{"version": 1, "action": "create", "reason": "", "snapshot": statement}],
        }
        work.journal.audit(actor, "statement.create", identifier)
        work.journal.finish(actor, "statement.create", key, statement)
    assert runtime.statement_exports.generate(actor, export_id)["status"] == "ready"
    # Only the current DTO projection gains the new optional default after migration.
    statement = {**statement, "lines": [{**line, "external_document_number": ""} for line in lines]}
    return confirmed, delivery, statement, {"id": str(export_id)}


def test_template_backup_restores_unused_versions_and_exact_exports(pg, tmp_path):
    _, _, statement, _ = create(pg)
    templates = pg.runtime.statement_templates
    first = templates.import_template(pg.actor, uuid4(), UUID(pg.customer_id), upload_body())
    unused = templates.import_template(
        pg.actor,
        uuid4(),
        UUID(pg.customer_id),
        upload_body(altered_file(lambda sheet: sheet.__setitem__("A12", "合成未使用版本"))),
    )
    export = pg.runtime.statement_exports.create(
        pg.actor, uuid4(), statement["id"], 1, "customer-v1", first["id"]
    )
    assert pg.runtime.statement_exports.generate(pg.actor, export["id"])["status"] == "ready"
    original = pg.runtime.statement_exports.download(pg.actor, export["id"])[0]
    with pg.owner.connect() as conn:
        records = list(
            conn.execute(
                text("SELECT to_jsonb(t) FROM statement_templates t ORDER BY version")
            ).scalars()
        )
    backup = tmp_path / "templates-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest
    assert all(record["object_hash"] in manifest["objects"] for record in records)
    with owned_database(pg, "ff_template_restore_") as (name, admin):
        objects = tmp_path / "restored-template-objects"
        restore_backup(admin, name, objects, backup, BINARY, ROOT)
        restored = build_services(
            Settings(pg.admin_url.set(database=name).render_as_string(hide_password=False), objects)
        )
        try:
            restored.check_ready()
            assert (
                restored.statement_templates.detail(pg.actor, pg.customer_id, unused["id"])
                == unused
            )
            assert restored.statement_exports.download(pg.actor, export["id"])[0] == original
            for record in records:
                assert (objects / f"{record['object_hash']}.json").read_bytes() == (
                    pg.objects / f"{record['object_hash']}.json"
                ).read_bytes()
            following = restored.statement_exports.create(
                pg.actor, uuid4(), statement["id"], 1, "customer-v1", unused["id"]
            )
            assert (
                restored.statement_exports.generate(pg.actor, following["id"])["status"] == "ready"
            )
            assert restored.statement_exports.download(pg.actor, export["id"])[0] == original
        finally:
            restored.close()


def test_0010_upgrade_rollback_and_restore_preserve_builtin_defaults_and_bytes(pg, tmp_path):
    with owned_database(pg, "ff_template_legacy_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0010_statement_lifecycle")
            objects = tmp_path / "legacy-template-objects"
            objects.mkdir()
            runtime = build_services(Settings(url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic Legacy Templates", "synthetic", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic Legacy Customer")
            _, _, statement, export = seed_legacy_business(runtime, actor, customer["id"])
            original = runtime.statement_exports.download(actor, export["id"])[0]
            with owner.begin() as conn:
                conn.execute(
                    text("""INSERT INTO statement_customer_settings(organization_id,customer_id,
                    version,cycle_day,tax_mode,tax_rate,template_id)
                    VALUES(:org,:customer,1,25,'untaxed_final',0,'delivery-v1')"""),
                    {"org": actor.organization_id, "customer": customer["id"]},
                )
            backup = tmp_path / "legacy-0010-backup"
            manifest = runtime.backup(backup, BINARY)
            assert manifest["schema_revision"] == "0010_statement_lifecycle"
            assert validate_backup(backup) == manifest
            with owner.begin() as conn:
                conn.execute(
                    text(
                        "CREATE FUNCTION guard_statement_template() RETURNS trigger "
                        "LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$"
                    )
                )
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0010_statement_lifecycle"
                )
                assert conn.scalar(text("SELECT to_regclass('statement_templates')")) is None
                conn.execute(text("DROP FUNCTION guard_statement_template()"))
            upgrade_database(owner, ROOT)
            runtime.check_ready()
            assert runtime.statements.detail(actor, statement["id"]) == statement
            assert (
                runtime.statements.settings.get(actor, customer["id"])["template_id"]
                == "delivery-v1"
            )
            assert runtime.statement_exports.download(actor, export["id"])[0] == original
            with owned_database(pg, "ff_template_oldrestore_") as (restored_name, restored_admin):
                restored_objects = tmp_path / "restored-old-template-objects"
                restore_backup(
                    restored_admin, restored_name, restored_objects, backup, BINARY, ROOT
                )
                restored = build_services(
                    Settings(
                        pg.admin_url.set(database=restored_name).render_as_string(
                            hide_password=False
                        ),
                        restored_objects,
                    )
                )
                try:
                    restored.check_ready()
                    assert restored.statements.detail(actor, statement["id"]) == statement
                    assert restored.statement_exports.download(actor, export["id"])[0] == original
                    assert (
                        restored.statement_templates.listing(actor, customer["id"])["items"] == []
                    )
                    settings = restored.statements.settings.get(actor, customer["id"])
                    assert (
                        settings["template_id"] == "delivery-v1"
                        and settings["customer_template_id"] is None
                    )
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
