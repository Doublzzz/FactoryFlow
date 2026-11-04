"""0016 evidence survives upgrade; 0017 backup restores production and its stock effects."""

from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_archive_migration import BINARY, owned_database
from test_order_contract import payload
from test_production import BASE, DAY, finish, fixture, issue, ok, void
from test_production_safeguards import effects
from test_supply_restore import rows


def old_rows(engine, tables):
    result = rows(engine, tables)
    with engine.connect() as conn:
        result["inventory_ledger"] = list(
            conn.execute(
                text(
                    "SELECT (to_jsonb(t)-ARRAY['production_order_id',"
                    "'production_completion_id'])::text "
                    "FROM inventory_ledger t ORDER BY 1"
                )
            ).scalars()
        )
    return result


def test_pd_backup_restores_plans_issues_returns_completions_reversals_and_replay(pg, tmp_path):
    _, material, _, production, _ = fixture(pg)
    issued = ok(issue(pg, production, material))
    key = uuid4()
    result = ok(finish(pg, production, "40", "2", key))
    ok(void(pg, production, result))
    ok(finish(pg, production, "60", "1"))
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/issues/{issued['entry_id']}/returns",
            {
                "quantity": "5",
                "business_date": DAY,
                "reason": "Synthetic restored material",
            },
        )
    )
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/close", {"expected_version": 1, "reason": "Stop"}
        )
    )
    before = effects(pg)
    details = pg.runtime.production.get(pg.actor, production["id"])
    issues = pg.runtime.production.issues(pg.actor, production["id"])
    backup = tmp_path / "production-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION and validate_backup(backup) == manifest
    with owned_database(pg, "ff_production_restore_") as (name, admin):
        objects = tmp_path / "restored-objects"
        restore_backup(admin, name, objects, backup, BINARY, ROOT)
        url = make_url(pg.settings.database_url).set(database=name)
        restored = build_services(Settings(url.render_as_string(hide_password=False), objects))
        try:
            restored.check_ready()
            assert rows(restored.engine, before) == {
                table: list(value) for table, value in before.items()
            }
            assert restored.production.get(pg.actor, production["id"]) == details
            assert restored.production.issues(pg.actor, production["id"]) == issues
            assert (
                restored.production.complete(
                    pg.actor,
                    key,
                    production["id"],
                    {
                        "quantity": "40",
                        "scrap_quantity": "2",
                        "business_date": DAY,
                    },
                )
                == result
            )
            assert rows(restored.engine, before) == {
                table: list(value) for table, value in before.items()
            }
        finally:
            restored.close()


def test_pd_0016_upgrade_rollback_backup_restore_preserves_existing_rows_and_evidence(pg, tmp_path):
    with owned_database(pg, "ff_production_old_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        owner_url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(owner_url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0016_purchasing_raw_inventory")
            objects = tmp_path / "old-objects"
            objects.mkdir()
            runtime = build_services(Settings(owner_url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic old production", "synthetic-old", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic old customer")
            key, body = uuid4(), payload() | {"customer_id": customer["id"]}
            confirmed = runtime.orders.confirm(actor, key, body)
            material_id = uuid4()
            with owner.begin() as conn:
                params = {
                    "org": actor.organization_id,
                    "actor": actor.user_id,
                    "material": material_id,
                    "entry": uuid4(),
                }
                conn.execute(
                    text("""INSERT INTO materials
                 (organization_id,id,own_code,name,unit,kind,created_by,updated_by)
                 VALUES(:org,:material,'SYN-OLD-PRODUCTION','Synthetic material',
                        'KG','raw',:actor,:actor)"""),
                    params,
                )
                conn.execute(
                    text("""INSERT INTO inventory_accounts
                 (organization_id,material_id,canonical_unit,created_by)
                 VALUES(:org,:material,'KG',:actor)"""),
                    params,
                )
                conn.execute(
                    text("""INSERT INTO inventory_ledger
                 (organization_id,id,material_id,kind,delta,target_quantity,business_date,actor_id)
                 VALUES(:org,:entry,:material,'opening',12.125,12.125,'2026-10-26',:actor)"""),
                    params,
                )
            tables = [
                "orders",
                "order_lines",
                "confirmed_revisions",
                "order_events",
                "materials",
                "inventory_accounts",
                "inventory_ledger",
                "audit_events",
                "command_results",
            ]
            before = old_rows(owner, tables)
            backup = tmp_path / "0016-backup"
            manifest = runtime.backup(backup, BINARY)
            assert manifest["schema_revision"] == "0016_purchasing_raw_inventory"
            assert validate_backup(backup) == manifest
            with owner.begin() as conn:
                conn.execute(text("CREATE TABLE production_completions (synthetic_marker integer)"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0016_purchasing_raw_inventory"
                )
                assert conn.scalar(text("SELECT to_regclass('public.production_orders')")) is None
                conn.execute(text("DROP TABLE production_completions"))
            assert old_rows(owner, tables) == before
            upgrade_database(owner, ROOT)
            runtime.check_ready()
            assert old_rows(owner, tables) == before
            assert runtime.orders.confirm(actor, key, body) == confirmed
            with owner.connect() as conn:
                assert conn.scalar(text("SELECT count(*) FROM production_orders")) == 0
                assert (
                    conn.scalar(
                        text(
                            "SELECT count(*) FROM inventory_ledger "
                            "WHERE production_order_id IS NOT NULL"
                        )
                    )
                    == 0
                )
            with owned_database(pg, "ff_production_old_restore_") as (restored_name, restore_admin):
                restored_objects = tmp_path / "old-restored"
                restore_backup(restore_admin, restored_name, restored_objects, backup, BINARY, ROOT)
                url = make_url(pg.settings.database_url).set(database=restored_name)
                restored = build_services(
                    Settings(url.render_as_string(hide_password=False), restored_objects)
                )
                try:
                    restored.check_ready()
                    assert old_rows(restored.engine, tables) == before
                    assert restored.orders.confirm(actor, key, body) == confirmed
                    assert (
                        restored.raw_inventory.detail(actor, material_id)["account"]["balance"]
                        == "12.125"
                    )
                    for source in objects.glob("*.json"):
                        assert (restored_objects / source.name).read_bytes() == source.read_bytes()
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
