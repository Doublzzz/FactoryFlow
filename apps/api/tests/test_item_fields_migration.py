"""Upgrade a synthetic prior database without rewriting its confirmed evidence."""

from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from test_order_contract import payload


def test_prior_0004_backup_upgrade_restore_preserves_old_bytes(pg, tmp_path):
    source, restored = ("ff_upgrade_" + uuid4().hex for _ in range(2))
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(source)))
    url = pg.admin_url.set(database=source)
    owner = engine_for(url.render_as_string(hide_password=False))
    runtime = target = None
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with owner.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0004_document_extraction")
        objects = tmp_path / "old-objects"
        objects.mkdir()
        runtime = build_services(Settings(url.render_as_string(hide_password=False), objects))
        actor = runtime.identity.provision_factory(
            "Synthetic Upgrade", "synthetic-upgrade", SYNTHETIC_PASSWORD
        )
        customer = runtime.customers.create(actor, uuid4(), "Synthetic Customer")
        body = payload() | {"customer_id": customer["id"]}
        key = uuid4()
        original_order = runtime.orders.confirm(actor, key, body)
        original = runtime.orders.evidence(actor, original_order["revision_id"])
        original_bytes = runtime.extraction.store.read(original["sha256"])
        backup = tmp_path / "old-backup"
        binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
        assert runtime.backup(backup, binary)["schema_revision"] == "0004_document_extraction"
        upgrade_database(owner, ROOT)
        runtime.check_ready()
        assert runtime.orders.confirm(actor, key, body) == original_order
        assert runtime.orders.evidence(actor, original_order["revision_id"]) == original
        assert (
            runtime.orders.detail(actor, original_order["order_id"])["lines"][0]["item_code"]
            is None
        )
        restore_backup(admin, restored, tmp_path / "restored", backup, binary, ROOT)
        target = build_services(
            Settings(
                url.set(database=restored).render_as_string(hide_password=False),
                tmp_path / "restored",
            )
        )
        target.check_ready()
        assert target.orders.evidence(actor, original_order["revision_id"]) == original
        assert target.extraction.store.read(original["sha256"]) == original_bytes
    finally:
        if runtime:
            runtime.close()
        if target:
            target.close()
        owner.dispose()
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            for database in (source, restored):
                assert database.startswith("ff_upgrade_") and len(database) == 43
                conn.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(database)
                    )
                )
