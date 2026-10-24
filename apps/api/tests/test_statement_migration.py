from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_order_contract import payload
from test_postgres_statements import draft, source


def drop_owned(admin, database):
    assert database.startswith("ff_statement_") and len(database.rsplit("_", 1)[-1]) == 32
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


def test_prior_schema_migration_rolls_back_and_preserves_evidence(pg, tmp_path):
    name = "ff_statement_upgrade_" + uuid4().hex
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
    owner = engine_for(pg.admin_url.set(database=name).render_as_string(hide_password=False))
    runtime = None
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with owner.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0005_order_item_fields")
        objects = tmp_path / "prior-objects"
        objects.mkdir()
        runtime = build_services(
            Settings(pg.admin_url.set(database=name).render_as_string(hide_password=False), objects)
        )
        actor = runtime.identity.provision_factory(
            "Synthetic Upgrade", "synthetic", SYNTHETIC_PASSWORD
        )
        customer = runtime.customers.create(actor, uuid4(), "Synthetic Migration Customer")
        order = runtime.orders.confirm(actor, uuid4(), payload() | {"customer_id": customer["id"]})
        evidence = runtime.orders.evidence(actor, order["revision_id"])
        original = runtime.extraction.store.read(evidence["sha256"])
        assert (
            runtime.backup(tmp_path / "prior-backup", ROOT / ".tools/postgresql-18.6-4/pgsql/bin")[
                "schema_revision"
            ]
            == "0005_order_item_fields"
        )
        with owner.begin() as conn:
            conn.execute(text("CREATE TABLE statement_lines(synthetic_marker integer)"))
        with pytest.raises(DBAPIError):
            upgrade_database(owner, ROOT)
        with owner.begin() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0005_order_item_fields"
            )
            assert conn.execute(text("SELECT to_regclass('statements')")).scalar_one() is None
            conn.execute(text("DROP TABLE statement_lines"))
        upgrade_database(owner, ROOT)
        runtime.check_ready()
        assert runtime.extraction.store.read(evidence["sha256"]) == original
        assert runtime.orders.evidence(actor, order["revision_id"]) == evidence
    finally:
        if runtime:
            runtime.close()
        owner.dispose()
        drop_owned(admin, name)


def test_statement_backup_restore_preserves_claims_prices_and_history(pg, tmp_path):
    delivery = source(pg)
    created = pg.runtime.statements.create(pg.actor, uuid4(), draft(pg, delivery))
    export = pg.runtime.statement_exports.create(pg.actor, uuid4(), created["id"], 1)
    pg.runtime.statement_exports.generate(pg.actor, export["id"])
    original_file = pg.runtime.statement_exports.download(pg.actor, export["id"])[0]
    binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
    backup = tmp_path / "backup"
    pg.runtime.backup(backup, binary)
    name = "ff_statement_restore_" + uuid4().hex
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    target = None
    try:
        restore_backup(admin, name, tmp_path / "restored-objects", backup, binary, ROOT)
        target = build_services(
            Settings(
                pg.admin_url.set(database=name).render_as_string(hide_password=False),
                tmp_path / "restored-objects",
            )
        )
        target.check_ready()
        assert target.statements.detail(pg.actor, created["id"]) == created
        assert target.statement_exports.download(pg.actor, export["id"])[0] == original_file
        target.deliveries.void(pg.actor, uuid4(), delivery["id"], 1, "Synthetic restored void")
        assert target.statements.detail(pg.actor, created["id"])["calculation"]["total"] == "0.00"
        assert (
            target.statement_exports.download(pg.actor, export["id"], historical=True)[0]
            == original_file
        )
    finally:
        if target:
            target.close()
        drop_owned(admin, name)
