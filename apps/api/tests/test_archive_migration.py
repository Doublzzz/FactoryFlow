"""Disposable 0008 upgrade and immutable work-archive recovery evidence."""

import hashlib
from contextlib import contextmanager
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.modules.fulfillment.domain.print_layout import default_layout
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_order_contract import payload

BINARY = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"


@contextmanager
def owned_database(pg, prefix):
    name = prefix + uuid4().hex
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    try:
        yield name, admin
    finally:
        assert name.startswith(prefix) and len(name.removeprefix(prefix)) == 32
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name))
            )


def seed_business(runtime, actor, customer_id):
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
    statement = runtime.statements.create(
        actor,
        uuid4(),
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
        },
    )
    export = runtime.statement_exports.create(actor, uuid4(), UUID(statement["id"]), 1)
    assert runtime.statement_exports.generate(actor, export["id"])["status"] == "ready"
    return confirmed, delivery, statement, export


def test_0008_upgrade_rollback_and_backup_restore_preserve_business(pg, tmp_path):
    from test_statement_template_restore import seed_legacy_business

    with owned_database(pg, "ff_archive_upgrade_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0008_delivery_layout")
            objects = tmp_path / "prior-objects"
            objects.mkdir()
            runtime = build_services(Settings(url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic Archive Upgrade", "synthetic", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic Archive Customer")
            confirmed, delivery, statement, export = seed_legacy_business(
                runtime, actor, customer["id"]
            )
            layout = runtime.delivery_layouts.save(
                actor, uuid4(), 0, default_layout() | {"company_name": "Synthetic prior layout"}
            )
            before = runtime.orders.detail(actor, confirmed["order_id"])
            evidence = runtime.orders.evidence(actor, confirmed["revision_id"])
            original = runtime.extraction.store.read(evidence["sha256"])
            excel = runtime.statement_exports.download(actor, export["id"])[0]
            backup = tmp_path / "0008-backup"
            manifest = runtime.backup(backup, BINARY)
            assert manifest["schema_revision"] == "0008_delivery_layout"
            assert validate_backup(backup) == manifest

            # A late DDL collision proves earlier 0009 tables/functions roll back too.
            with owner.begin() as conn:
                conn.execute(text("CREATE TABLE archive_batches(synthetic_marker integer)"))
                conn.execute(text("INSERT INTO archive_batches VALUES(8)"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert conn.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one() == ("0008_delivery_layout")
                assert (
                    conn.execute(text("SELECT synthetic_marker FROM archive_batches")).scalar_one()
                    == 8
                )
                assert (
                    conn.execute(text("SELECT to_regclass('archive_settings')")).scalar_one()
                    is None
                )
                assert (
                    conn.execute(
                        text("SELECT to_regprocedure('guard_archive_settings()')")
                    ).scalar_one()
                    is None
                )
                conn.execute(text("DROP TABLE archive_batches"))
            assert runtime.orders.detail(actor, confirmed["order_id"]) == before
            assert runtime.delivery_layouts.get(actor) == layout
            assert runtime.statement_exports.download(actor, export["id"])[0] == excel
            upgrade_database(owner, ROOT)
            runtime.check_ready()
            assert runtime.orders.detail(actor, confirmed["order_id"]) == before
            assert runtime.delivery_layouts.get(actor) == layout
            assert runtime.statement_exports.download(actor, export["id"])[0] == excel

            with owned_database(pg, "ff_archive_restore_") as (restored_name, restore_admin):
                restored_objects = tmp_path / "restored-0008-objects"
                restore_backup(restore_admin, restored_name, restored_objects, backup, BINARY, ROOT)
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
                    with restored.engine.connect() as conn:
                        assert (
                            conn.execute(
                                text("SELECT version_num FROM alembic_version")
                            ).scalar_one()
                            == REVISION
                        )
                    assert restored.orders.detail(actor, confirmed["order_id"]) == before
                    assert restored.orders.evidence(actor, confirmed["revision_id"]) == evidence
                    assert restored.extraction.store.read(evidence["sha256"]) == original
                    assert restored.delivery_layouts.get(actor) == layout
                    assert restored.deliveries.detail(actor, delivery["id"]) == delivery
                    assert restored.statements.detail(actor, UUID(statement["id"])) == statement
                    assert restored.statement_exports.download(actor, export["id"])[0] == excel
                    assert restored.archives.settings(actor)["version"] == 0
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()


def test_pending_failed_ready_archives_restore_fixed_bytes_without_rerender(
    pg, tmp_path, monkeypatch
):
    runtime = build_services(replace(pg.settings, archive_root=tmp_path / "original-copies"))
    restored = None
    try:
        _, delivery, _, _ = seed_business(runtime, pg.actor, pg.customer_id)
        source = runtime.extraction.upload(
            pg.actor, uuid4(), "synthetic-recovery.pdf", "application/pdf", b"%PDF-1.7\nsynthetic"
        )
        service = runtime.archives
        settings = service.save_settings(pg.actor, uuid4(), 0, "customer")
        selections = []
        for kind, identifier in (("source", source["source_id"]), ("delivery", delivery["id"])):
            item = next(
                i for i in service.catalog(pg.actor, kind)["items"] if i["source_id"] == identifier
            )
            selections.append({"key": item["key"], "token": item["token"]})
        expected, statuses, required_hashes = {}, {}, set()
        for rule, status in (
            ("date", "pending"),
            ("customer", "failed"),
            ("month_customer", "ready"),
        ):
            preview = service.preview(pg.actor, rule, selections)
            batch = service.create(pg.actor, uuid4(), rule, selections, preview["preview_token"])
            identifier = batch["id"]
            with service.snapshot() as work:
                record = work.archives.get(pg.actor, identifier)
            expected[identifier] = service.zipper(service.inputs(record), record["manifest"])
            required_hashes.add(record["input_hash"])
            if status == "failed":
                with monkeypatch.context() as patch:

                    def fail(*args):
                        raise OSError("Synthetic archive disk failure")

                    patch.setattr(service.copies, "publish", fail)
                    assert service.generate(pg.actor, identifier)["status"] == "failed"
            elif status == "ready":
                assert service.generate(pg.actor, identifier)["local_available"]
                assert service.download(pg.actor, identifier) == expected[identifier]
                with service.snapshot() as work:
                    required_hashes.add(work.archives.get(pg.actor, identifier)["object_hash"])
            statuses[identifier] = status
        backup = tmp_path / "archives-backup"
        manifest = runtime.backup(backup, BINARY)
        assert validate_backup(backup) == manifest
        assert required_hashes <= set(manifest["objects"])

        # Frozen archive restore must work even when the renderer is unavailable.
        def unavailable_renderer(*_):
            raise RuntimeError("Synthetic renderer unavailable")

        monkeypatch.setattr(
            "factoryflow.bootstrap.render_archive_delivery",
            unavailable_renderer,
        )
        with owned_database(pg, "ff_archive_rebuild_") as (name, admin):
            objects = tmp_path / "restored-archive-objects"
            restore_backup(admin, name, objects, backup, BINARY, ROOT)
            restored = build_services(
                Settings(
                    pg.admin_url.set(database=name).render_as_string(hide_password=False),
                    objects,
                    archive_root=tmp_path / "restored-copies",
                )
            )
            try:
                restored.check_ready()
                assert restored.archives.settings(pg.actor) == settings
                for digest in manifest["objects"]:
                    assert (
                        hashlib.sha256((objects / f"{digest}.json").read_bytes()).hexdigest()
                        == digest
                    )
                for identifier, status in statuses.items():
                    before = restored.archives.detail(pg.actor, identifier)
                    assert before["status"] == status
                    assert before["local_available"] is False
                    if status == "ready":
                        assert (
                            restored.archives.download(pg.actor, identifier, historical=True)
                            == expected[identifier]
                        )
                    generated = restored.archives.generate(pg.actor, identifier)
                    assert generated["status"] == "ready" and generated["local_available"]
                    assert (
                        generated["file_hash"] == hashlib.sha256(expected[identifier]).hexdigest()
                    )
                    assert (
                        restored.archives.download(pg.actor, identifier, historical=True)
                        == expected[identifier]
                    )
                    assert restored.archives.generate(pg.actor, identifier) == generated
            finally:
                restored.close()
                restored = None
    finally:
        if restored:
            restored.close()
        runtime.close()
