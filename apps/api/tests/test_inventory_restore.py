"""0013 upgrade, atomic migration failure, old fingerprints and complete stock recovery."""

from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import API, ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services, create_app
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database
from legacy_delivery import create_legacy_delivery
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_archive_migration import BINARY, owned_database
from test_order_contract import payload
from test_postgres_inventory import make_order, ok, opening, receipt, send, stock, void_delivery
from test_postgres_materials import create_material


def test_iv24_inventory_backup_restores_exact_account_ledger_snapshots_and_replay(pg, tmp_path):
    material = create_material(pg)
    opening(pg, material, "70")
    received = receipt(pg, material)
    order = make_order(pg, [material])
    tracked = send(pg, order, ["20"])
    skipped = send(pg, order, ["10"], inventory_mode="skip")
    void_delivery(pg, tracked)
    key, body = uuid4(), {"reason": "Synthetic reverse receipt"}
    path = f"/api/v1/inventory/entries/{received['entry']['id']}/void"
    result = ok(pg.api.command(path, body, key))
    before = stock(pg, material)
    backup = tmp_path / "inventory-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest
    with owned_database(pg, "ff_inventory_restore_") as (name, admin):
        restored_objects = tmp_path / "restored-objects"
        restore_backup(
            admin.render_as_string(hide_password=False),
            name,
            restored_objects,
            backup,
            BINARY,
            ROOT,
        )
        url = make_url(pg.settings.database_url).set(database=name)
        restored = build_services(
            Settings(url.render_as_string(hide_password=False), restored_objects)
        )
        try:
            restored.check_ready()
            assert restored.inventory.detail(pg.actor, material["id"]) == before
            assert restored.deliveries.detail(pg.actor, skipped["id"]) == skipped
            assert (
                restored.inventory.void_receipt(
                    pg.actor, key, received["entry"]["id"], body["reason"]
                )
                == result
            )
            assert restored.inventory.detail(pg.actor, material["id"]) == before
        finally:
            restored.close()


def test_iv24_0013_backup_failure_rollback_and_restore_keep_old_delivery_untracked(pg, tmp_path):
    with owned_database(pg, "ff_inventory_legacy_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        owner_url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(owner_url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0013_material_pool")
            objects = tmp_path / "legacy-objects"
            objects.mkdir()
            runtime = build_services(Settings(owner_url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic Legacy Stock", "synthetic", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic Legacy Customer")
            material = runtime.materials.create(
                actor, uuid4(), {"name": "Synthetic Legacy Item", "unit": "KG"}
            )
            order_input = payload() | {
                "customer_id": customer["id"],
                "material_choices": [
                    {
                        "line_number": 1,
                        "material_id": material["id"],
                        "expected_material_version": 1,
                    },
                ],
            }
            confirmed = runtime.orders.confirm(actor, uuid4(), order_input)
            order = runtime.orders.detail(actor, confirmed["order_id"])
            key = uuid4()
            delivery_body = {
                "order_id": order["id"],
                "customer_id": customer["id"],
                "revision_id": order["revision_id"],
                "expected_version": order["version"],
                "delivery_date": "2026-10-24",
                "lines": [
                    {"order_line_id": order["lines"][0]["id"], "quantity": "0.125"},
                ],
            }
            original_delivery = create_legacy_delivery(runtime, actor, delivery_body, key)
            original_evidence = objects.joinpath(confirmed["sha256"] + ".json").read_bytes()
            backup = tmp_path / "0013-backup"
            assert runtime.backup(backup, BINARY)["schema_revision"] == "0013_material_pool"
            with owner.begin() as conn:
                conn.execute(
                    text("CREATE TABLE delivery_inventory_snapshots(synthetic_marker integer)")
                )
                conn.execute(text("INSERT INTO delivery_inventory_snapshots VALUES(13)"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    == "0013_material_pool"
                )
                for table in ("inventory_accounts", "inventory_ledger"):
                    assert (
                        conn.execute(
                            text("SELECT to_regclass(:name)"), {"name": table}
                        ).scalar_one()
                        is None
                    )
                assert (
                    conn.execute(
                        text("SELECT to_regprocedure('apply_inventory_entry()')")
                    ).scalar_one()
                    is None
                )
                assert (
                    conn.execute(
                        text("SELECT synthetic_marker FROM delivery_inventory_snapshots")
                    ).scalar_one()
                    == 13
                )
                conn.execute(text("DROP TABLE delivery_inventory_snapshots"))
            assert runtime.deliveries.create(actor, key, delivery_body) == original_delivery
            with owned_database(pg, "ff_inventory_old_restore_") as (restored_name, restore_admin):
                restored_objects = tmp_path / "legacy-restored-objects"
                restore_backup(
                    restore_admin.render_as_string(hide_password=False),
                    restored_name,
                    restored_objects,
                    backup,
                    BINARY,
                    ROOT,
                )
                url = make_url(pg.settings.database_url).set(database=restored_name)
                settings = Settings(url.render_as_string(hide_password=False), restored_objects)
                app = create_app(settings=settings)
                restored = app.state.services
                try:
                    restored.check_ready()
                    api = API(app)
                    api.login("synthetic")
                    assert (
                        ok(
                            api.command(
                                "/api/v1/deliveries",
                                delivery_body
                                | {
                                    "inventory_mode": "sync",
                                    "confirm_inventory_shortage": False,
                                },
                                key,
                            )
                        )
                        == original_delivery
                    )
                    assert (
                        restored_objects.joinpath(confirmed["sha256"] + ".json").read_bytes()
                        == original_evidence
                    )
                    assert restored.inventory.detail(actor, material["id"])["account"] is None
                    # Even a runtime temp table cannot hide a legacy delivery's sealed action.
                    with pytest.raises(DBAPIError), restored.engine.begin() as conn:
                        conn.execute(
                            text(
                                "CREATE TEMP TABLE fulfillment_actions AS "
                                "SELECT * FROM public.fulfillment_actions WITH NO DATA"
                            )
                        )
                        conn.execute(
                            text("""INSERT INTO public.delivery_inventory_snapshots
                            (organization_id,delivery_id,order_line_id,state,material_id,
                             canonical_unit,quantity,mode,shortage_confirmed)
                            SELECT organization_id,delivery_id,order_line_id,'unmanaged',:material,
                             canonical_unit,quantity,'sync',false FROM public.delivery_lines
                            WHERE delivery_id=:delivery"""),
                            {
                                "material": material["id"],
                                "delivery": original_delivery["id"],
                            },
                        )
                    restored.inventory.record(
                        actor,
                        uuid4(),
                        material["id"],
                        "opening",
                        {
                            "quantity": "70",
                            "business_date": "2026-10-24",
                        },
                    )
                    restored.deliveries.void(
                        actor, uuid4(), original_delivery["id"], 1, "Synthetic old void"
                    )
                    detail = restored.inventory.detail(actor, material["id"])
                    assert detail["account"]["balance"] == "70" and len(detail["entries"]) == 1
                    delivery = restored.deliveries.detail(actor, original_delivery["id"])
                    assert delivery["lines"][0]["inventory"] is None
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
