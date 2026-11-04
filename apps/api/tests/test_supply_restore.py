"""PR15: actual PostgreSQL backups preserve supply evidence and upgrade old stock."""

from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.modules.inventory.adapters.raw_http import RawInventoryMutation
from factoryflow.modules.purchasing.adapters.http import PurchaseReceiptInput
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
from test_purchasing import fixture, ok, purchasing_effects, receipt
from test_raw_inventory import movement


def rows(engine, tables):
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1"))
            .scalars()
            .all()
            for table in tables
        }


def old_rows(engine, tables):
    snapshot = rows(engine, tables)
    with engine.connect() as conn:
        snapshot["inventory_ledger"] = (
            conn.execute(
                text(
                    "SELECT (to_jsonb(t)-ARRAY["
                    "'purchase_receipt_line_id','returns_issue_id',"
                    "'production_order_id','production_completion_id'])::text "
                    "FROM inventory_ledger t ORDER BY 1"
                )
            )
            .scalars()
            .all()
        )
    return snapshot


def test_supply_backup_restores_suppliers_orders_receipts_raw_ledger_and_replays(pg, tmp_path):
    supplier, materials, order = fixture(pg)
    received = ok(receipt(pg, supplier, order, ["6"]))
    direct_body = {
        "supplier_id": supplier["id"],
        "business_date": "2026-10-26",
        "lines": [{"material_id": materials[0]["id"], "quantity": "2"}],
    }
    direct_key = uuid4()
    direct = ok(pg.api.command("/api/v1/purchase-receipts", direct_body, direct_key))
    issue = ok(movement(pg, materials[0], "issues", "5"))
    return_key = uuid4()
    return_body = {
        "quantity": "2",
        "business_date": "2026-10-26",
        "reason": "Synthetic unused return",
    }
    returned = ok(
        pg.api.command(
            f"/api/v1/raw-inventory/entries/{issue['entry']['id']}/returns", return_body, return_key
        )
    )
    void_key = uuid4()
    void_body = {"expected_version": 1, "reason": "Synthetic wrong direct receipt"}
    voided = ok(
        pg.api.command(f"/api/v1/purchase-receipts/{direct['id']}/void", void_body, void_key)
    )
    before = purchasing_effects(pg)
    stock = pg.runtime.raw_inventory.detail(pg.actor, materials[0]["id"])
    backup = tmp_path / "supply-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest
    assert (backup / "database.dump").stat().st_size > 0
    with owned_database(pg, "ff_supply_restore_") as (name, admin):
        objects = tmp_path / "restored-objects"
        restore_backup(admin, name, objects, backup, BINARY, ROOT)
        url = make_url(pg.settings.database_url).set(database=name)
        restored = build_services(Settings(url.render_as_string(hide_password=False), objects))
        try:
            restored.check_ready()
            assert rows(restored.engine, before) == before
            assert restored.raw_inventory.detail(pg.actor, materials[0]["id"]) == stock
            assert (
                restored.purchasing.get_order(pg.actor, order["id"])["lines"][0][
                    "received_quantity"
                ]
                == "6"
            )
            assert restored.purchasing.get_receipt(pg.actor, received["id"]) == received
            direct_request = PurchaseReceiptInput.model_validate(direct_body).model_dump(
                mode="json"
            )
            assert (
                restored.purchasing.create_receipt(pg.actor, direct_key, direct_request) == direct
            )
            assert (
                restored.purchasing.void_receipt(pg.actor, void_key, direct["id"], void_body)
                == voided
            )
            replay = restored.raw_inventory.return_issue(
                pg.actor, return_key, issue["entry"]["id"], return_body
            )
            assert RawInventoryMutation.model_validate(replay).model_dump(mode="json") == returned
            assert rows(restored.engine, before) == before
        finally:
            restored.close()


def test_0015_backup_upgrade_and_atomic_failure_preserve_old_material_order_stock_journal(
    pg, tmp_path
):
    with owned_database(pg, "ff_supply_old_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        owner_url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(owner_url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0015_order_currencies")
            objects = tmp_path / "old-objects"
            objects.mkdir()
            runtime = build_services(Settings(owner_url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic Old Supply", "synthetic-old", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic Old Customer")
            material_id = uuid4()
            # Seed the actual 0015 material columns; current material service requires 0016.kind.
            with owner.begin() as conn:
                params = {
                    "org": actor.organization_id,
                    "actor": actor.user_id,
                    "material": material_id,
                    "entry": uuid4(),
                }
                conn.execute(
                    text("""INSERT INTO materials
                (organization_id,id,own_code,name,unit,created_by,updated_by)
                VALUES (:org,:material,'SYN-OLD-RAW','Synthetic Old Material','KG',
                        :actor,:actor)"""),
                    params,
                )
                conn.execute(
                    text("""INSERT INTO inventory_accounts
                (organization_id,material_id,canonical_unit,created_by)
                VALUES (:org,:material,'KG',:actor)"""),
                    params,
                )
                conn.execute(
                    text("""INSERT INTO inventory_ledger
                (organization_id,id,material_id,kind,delta,target_quantity,business_date,actor_id)
                VALUES (:org,:entry,:material,'opening',12,12,'2026-10-26',:actor)"""),
                    params,
                )
            key, body = uuid4(), payload() | {"customer_id": customer["id"]}
            confirmed = runtime.orders.confirm(actor, key, body)
            tables = [
                "orders",
                "order_lines",
                "confirmed_revisions",
                "order_events",
                "inventory_accounts",
                "inventory_ledger",
                "audit_events",
                "command_results",
            ]
            before = old_rows(owner, tables)
            with owner.connect() as conn:
                old_material = conn.scalar(text("SELECT to_jsonb(m)::text FROM materials m"))
            backup = tmp_path / "0015-backup"
            manifest = runtime.backup(backup, BINARY)
            assert manifest["schema_revision"] == "0015_order_currencies"
            assert validate_backup(backup) == manifest
            # A deliberate DDL collision after MATERIAL_DDL must roll back the whole migration.
            with owner.begin() as conn:
                conn.execute(text("CREATE TABLE suppliers (synthetic_marker integer)"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0015_order_currencies"
                )
                assert not conn.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                        "WHERE table_name='materials' AND column_name='kind')"
                    )
                )
                assert conn.scalar(text("SELECT to_regclass('public.purchase_orders')")) is None
                conn.execute(text("DROP TABLE suppliers"))
            assert old_rows(owner, tables) == before
            upgrade_database(owner, ROOT)
            runtime.check_ready()
            with owner.connect() as conn:
                assert (
                    conn.scalar(text("SELECT (to_jsonb(m)-'kind')::text FROM materials m"))
                    == old_material
                )
                assert conn.scalar(text("SELECT kind FROM materials")) == "finished"
            assert old_rows(owner, tables) == before
            assert runtime.orders.confirm(actor, key, body) == confirmed
            with owner.connect() as conn:
                assert (
                    conn.scalar(
                        text("""SELECT count(*) FROM inventory_ledger
                    WHERE production_order_id IS NOT NULL
                    OR production_completion_id IS NOT NULL""")
                    )
                    == 0
                )
            with owned_database(pg, "ff_supply_old_restore_") as (restored_name, restore_admin):
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
                        restored.inventory.detail(actor, material_id)["account"]["balance"] == "12"
                    )
                    with restored.engine.connect() as conn:
                        for table in [
                            "suppliers",
                            "purchase_orders",
                            "purchase_order_lines",
                            "purchase_receipts",
                            "purchase_receipt_lines",
                        ]:
                            assert conn.scalar(text(f"SELECT count(*) FROM {table}")) == 0
                    for path in objects.glob("*.json"):
                        assert (restored_objects / path.name).read_bytes() == path.read_bytes()
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
