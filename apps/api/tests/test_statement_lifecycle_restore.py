"""Synthetic lifecycle and legacy-backup recovery into new disposable databases."""

import base64
import hashlib
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
from alembic import command as migrate
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from test_archive_migration import BINARY, owned_database
from test_postgres_extraction import PNG
from test_postgres_statement_lifecycle import (
    approve,
    blank,
    command,
    detail,
    reserve,
    settle,
    setup_statement,
)
from test_statement_template_restore import seed_legacy_business


def lifecycle_rows(conn):
    return {
        table: list(conn.execute(text(f"SELECT to_jsonb(t) FROM {table} t ORDER BY id")).scalars())
        for table in (
            "statement_evidence",
            "statement_approvals",
            "statement_allocations",
            "statement_reviews",
            "statement_review_transfers",
            "statement_lifecycle_events",
            "statement_events",
            "statement_exports",
        )
    }


def test_current_backup_restore_keeps_lifecycle_quantities_and_attachment_bytes(pg, tmp_path):
    statement, source, sent, _ = setup_statement(pg)
    feedback = command(
        pg,
        f"/api/v1/statements/{statement['id']}/feedback",
        {
            "person": "Synthetic File Contact",
            "occurred_on": "2026-10-03",
            "note": "Synthetic signed quantity and price feedback",
            "filename": "synthetic.png",
            "media_type": "image/png",
            "content_base64": base64.b64encode(PNG).decode(),
        },
    )
    approval = approve(pg, statement, source, sent, feedback)
    review = command(
        pg,
        f"/api/v1/statements/{statement['id']}/review",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            **source,
            "quantity": "10",
            "reason": "Synthetic disputed quantity",
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
    assert pg.runtime.statement_exports.generate(pg.actor, export["id"])["status"] == "ready"
    original_file = pg.runtime.statement_exports.download(pg.actor, export["id"])[0]
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
    before_draft = detail(pg, following["id"])
    before_views = {
        identifier: pg.runtime.statement_lifecycle.view(pg.actor, identifier)
        for identifier in (statement["id"], following["id"])
    }
    with pg.owner.connect() as conn:
        before_rows = lifecycle_rows(conn)
        assert conn.scalar(text("SELECT sum(claimed) FROM statement_balances")) == Decimal(96)
    backup = tmp_path / "lifecycle-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest
    assert feedback["object_hash"] in manifest["objects"]
    with owned_database(pg, "ff_lifecycle_restore_") as (name, admin):
        objects = tmp_path / "restored-lifecycle-objects"
        restore_backup(admin, name, objects, backup, BINARY, ROOT)
        target = build_services(
            Settings(
                pg.admin_url.set(database=name).render_as_string(hide_password=False),
                objects,
            )
        )
        try:
            target.check_ready()
            assert target.statements.detail(pg.actor, UUID(statement["id"])) == formal
            assert target.statements.detail(pg.actor, UUID(following["id"])) == before_draft
            for identifier, expected in before_views.items():
                assert target.statement_lifecycle.view(pg.actor, identifier) == expected
            with target.engine.connect() as conn:
                assert lifecycle_rows(conn) == before_rows
                assert conn.scalar(text("SELECT sum(claimed) FROM statement_balances")) == Decimal(
                    96
                )
            row, restored_feedback = target.statement_lifecycle.download_evidence(
                pg.actor, feedback["id"]
            )
            assert row["object_hash"] == feedback["object_hash"] and restored_feedback == PNG
            assert target.statement_exports.download(pg.actor, export["id"])[0] == original_file
            for digest in manifest["objects"]:
                restored_bytes = (objects / f"{digest}.json").read_bytes()
                assert restored_bytes == (pg.objects / f"{digest}.json").read_bytes()
                assert hashlib.sha256(restored_bytes).hexdigest() == digest
            reviews = target.statement_lifecycle.listing(pg.actor, "reviews", UUID(pg.customer_id))
            assert reviews["items"][0]["remaining_quantity"] == "4"
            # Restored transfer ownership remains actionable; abandoning releases the six.
            abandoned = target.statements.abandon(
                pg.actor,
                uuid4(),
                UUID(following["id"]),
                before_draft["version"],
                "Synthetic restored release",
            )
            assert abandoned["status"] == "abandoned"
            reviews = target.statement_lifecycle.listing(pg.actor, "reviews", UUID(pg.customer_id))
            assert reviews["items"][0]["remaining_quantity"] == "10"
            assert target.statements.detail(pg.actor, UUID(statement["id"])) == formal
            assert target.statement_exports.download(pg.actor, export["id"])[0] == original_file
        finally:
            target.close()


def test_0009_upgrade_and_old_backup_keep_drafts_without_automatic_approval(pg, tmp_path):
    with owned_database(pg, "ff_lifecycle_prior_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                migrate.upgrade(config, "0009_work_archives")
            objects = tmp_path / "legacy-objects"
            objects.mkdir()
            runtime = build_services(Settings(url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic Legacy Factory",
                "synthetic",
                SYNTHETIC_PASSWORD,
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic Legacy Customer")
            _, _, statement, export = seed_legacy_business(runtime, actor, customer["id"])
            original_file = runtime.statement_exports.download(actor, export["id"])[0]
            with owner.connect() as conn:
                old_lines = list(
                    conn.execute(
                        text("SELECT to_jsonb(t)-'external_document_number' FROM statement_lines t")
                    ).scalars()
                )
                old_events = list(
                    conn.execute(
                        text("SELECT to_jsonb(t) FROM statement_events t ORDER BY id")
                    ).scalars()
                )
                old_claim = conn.scalar(text("SELECT sum(claimed) FROM statement_balances"))
            backup = tmp_path / "legacy-0009-backup"
            manifest = runtime.backup(backup, BINARY)
            assert manifest["schema_revision"] == "0009_work_archives"
            assert validate_backup(backup) == manifest
            upgrade_database(owner, ROOT)
            runtime.check_ready()
            assert_legacy_preserved(
                runtime,
                actor,
                statement,
                export,
                original_file,
                old_lines,
                old_events,
                old_claim,
            )
            with owned_database(pg, "ff_lifecycle_legacy_restore_") as (
                restored_name,
                restored_admin,
            ):
                restored_objects = tmp_path / "restored-legacy-objects"
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
                    assert_legacy_preserved(
                        restored,
                        actor,
                        statement,
                        export,
                        original_file,
                        old_lines,
                        old_events,
                        old_claim,
                    )
                    for digest in manifest["objects"]:
                        assert (restored_objects / f"{digest}.json").read_bytes() == (
                            objects / f"{digest}.json"
                        ).read_bytes()
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()


def assert_legacy_preserved(runtime, actor, statement, export, original_file, lines, events, claim):
    current = runtime.statements.detail(actor, UUID(statement["id"]))
    assert current == statement
    assert current["status"] == "draft" and current["settlement_lines"] == []
    assert current["fees_confirmed"] is False and current["reconfirmation"] == "unknown"
    assert runtime.statement_exports.download(actor, export["id"])[0] == original_file
    with runtime.engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_approvals")) == 0
        assert conn.scalar(text("SELECT count(*) FROM statement_allocations")) == 0
        assert conn.scalar(text("SELECT count(*) FROM statement_reviews")) == 0
        assert conn.scalar(text("SELECT sum(claimed) FROM statement_balances")) == claim
        assert (
            list(
                conn.execute(
                    text("SELECT to_jsonb(t)-'external_document_number' FROM statement_lines t")
                ).scalars()
            )
            == lines
        )
        assert (
            list(
                conn.execute(
                    text("SELECT to_jsonb(t) FROM statement_events t ORDER BY id")
                ).scalars()
            )
            == events
        )
