"""Disposable synthetic 0007 → current head upgrade and evidence preservation."""

from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.modules.fulfillment.domain.print_layout import default_layout
from factoryflow.platform.backup import validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_order_contract import payload


def test_0007_upgrade_rolls_back_and_preserves_order_evidence(pg, tmp_path):
    database = "ff_layout_upgrade_" + uuid4().hex
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(database)))
    owner = engine_for(pg.admin_url.set(database=database).render_as_string(hide_password=False))
    runtime = None
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with owner.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0007_statement_exports")
        objects = tmp_path / "prior-objects"
        objects.mkdir()
        runtime = build_services(
            Settings(
                pg.admin_url.set(database=database).render_as_string(hide_password=False), objects
            )
        )
        actor = runtime.identity.provision_factory(
            "Synthetic Layout Upgrade", "synthetic", SYNTHETIC_PASSWORD
        )
        customer = runtime.customers.create(actor, uuid4(), "Synthetic Migration Customer")
        created = runtime.orders.confirm(
            actor, uuid4(), payload() | {"customer_id": customer["id"]}
        )
        original_order = runtime.orders.detail(actor, created["order_id"])
        evidence = runtime.orders.evidence(actor, created["revision_id"])
        original_bytes = runtime.extraction.store.read(evidence["sha256"])
        backup = tmp_path / "prior-backup"
        manifest = runtime.backup(backup, ROOT / ".tools/postgresql-18.6-4/pgsql/bin")
        assert manifest["schema_revision"] == "0007_statement_exports"
        assert validate_backup(backup) == manifest
        assert (backup / "objects" / f"{evidence['sha256']}.json").read_bytes() == original_bytes

        with owner.begin() as conn:
            conn.execute(text("CREATE TABLE delivery_layout_versions(synthetic_marker integer)"))
            conn.execute(text("INSERT INTO delivery_layout_versions VALUES(7)"))
        with pytest.raises(DBAPIError):
            upgrade_database(owner, ROOT)
        with owner.begin() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == "0007_statement_exports"
            )
            assert (
                conn.execute(
                    text("SELECT synthetic_marker FROM delivery_layout_versions")
                ).scalar_one()
                == 7
            )
            assert (
                conn.execute(
                    text("SELECT to_regprocedure('guard_delivery_layout_version()')")
                ).scalar_one()
                is None
            )
            conn.execute(text("DROP TABLE delivery_layout_versions"))
        assert runtime.orders.detail(actor, created["order_id"]) == original_order
        assert runtime.orders.evidence(actor, created["revision_id"]) == evidence
        assert runtime.extraction.store.read(evidence["sha256"]) == original_bytes

        upgrade_database(owner, ROOT)
        runtime.check_ready()
        with owner.begin() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == REVISION
            )
        initial = runtime.delivery_layouts.get(actor)
        assert initial["version"] == 0
        assert initial["config"] == default_layout()
        saved_config = default_layout() | {"company_name": "Synthetic Migrated Layout"}
        saved = runtime.delivery_layouts.save(actor, uuid4(), 0, saved_config)
        assert saved["version"] == 1
        assert saved["config"] == saved_config
        assert runtime.delivery_layouts.get(actor) == saved
        assert runtime.orders.detail(actor, created["order_id"]) == original_order
        assert runtime.orders.evidence(actor, created["revision_id"]) == evidence
        assert runtime.extraction.store.read(evidence["sha256"]) == original_bytes
    finally:
        if runtime:
            runtime.close()
        owner.dispose()
        assert database.startswith("ff_layout_upgrade_")
        assert len(database.removeprefix("ff_layout_upgrade_")) == 32
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
