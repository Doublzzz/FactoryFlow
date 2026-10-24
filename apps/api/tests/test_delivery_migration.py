"""Supported previous schema can be backed up, upgraded and restored with its orders intact."""

from uuid import uuid4

import psycopg
from alembic import command
from alembic.config import Config
from conftest import API, ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services, create_app
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from test_order_contract import payload


def test_upgrade_and_restore_from_0002_preserve_confirmed_orders(pg, tmp_path):
    source = "ff_upgrade_" + uuid4().hex
    restored = "ff_upgrade_" + uuid4().hex
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(source)))
    url = pg.admin_url.set(database=source)
    owner = engine_for(url.render_as_string(hide_password=False))
    runtime = application = target = None
    try:
        config = Config(str(ROOT / "alembic.ini"))
        with owner.begin() as conn:
            config.attributes["connection"] = conn
            command.upgrade(config, "0002_quantity_scale")
        objects = tmp_path / "before-objects"
        objects.mkdir()
        settings = Settings(url.render_as_string(hide_password=False), objects)
        runtime = build_services(settings)
        actor = runtime.identity.provision_factory(
            "Synthetic Upgrade", "synthetic-upgrade", SYNTHETIC_PASSWORD
        )
        customer = runtime.customers.create(actor, uuid4(), "Synthetic Upgrade Customer")
        body = payload()
        body["customer_id"] = customer["id"]
        order = runtime.orders.confirm(actor, uuid4(), body)
        original = runtime.orders.evidence(actor, order["revision_id"])
        application = create_app(settings=settings)
        assert (
            API(application).request("GET", "/api/v1/health/ready").json()["code"]
            == "SCHEMA_MISMATCH"
        )
        backup = tmp_path / "before-backup"
        binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
        manifest = runtime.backup(backup, binary)
        assert manifest["schema_revision"] == "0002_quantity_scale"
        upgrade_database(owner, ROOT)
        assert API(application).request("GET", "/api/v1/health/ready").status_code == 200
        assert runtime.orders.evidence(actor, order["revision_id"]) == original
        restore_backup(admin, restored, tmp_path / "restored", backup, binary, ROOT)
        target_url = url.set(database=restored)
        target = build_services(
            Settings(target_url.render_as_string(hide_password=False), tmp_path / "restored")
        )
        target.check_ready()
        assert target.orders.evidence(actor, order["revision_id"]) == original
        detail = target.orders.detail(actor, order["order_id"])
        delivery = target.deliveries.create(
            actor,
            uuid4(),
            {
                "customer_id": customer["id"],
                "order_id": order["order_id"],
                "revision_id": order["revision_id"],
                "expected_version": 1,
                "delivery_date": "2026-10-01",
                "lines": [{"order_line_id": detail["lines"][0]["id"], "quantity": "0.125"}],
            },
        )
        assert delivery["lines"][0]["quantity"] == "0.125"
        with target.engine.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                == REVISION
            )
    finally:
        if application:
            application.state.services.close()
        if runtime:
            runtime.close()
        if target:
            target.close()
        owner.dispose()
        # Only the two UUID-named synthetic databases allocated by this test.
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            for database in (source, restored):
                assert database.startswith("ff_upgrade_") and len(database) == 43
                conn.execute(
                    sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                        sql.Identifier(database)
                    )
                )
