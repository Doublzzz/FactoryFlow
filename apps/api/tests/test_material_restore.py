"""Old synthetic evidence survives 0012 upgrade; catalog identity and sequence survive restore."""

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
from test_postgres_material_order_links import confirm
from test_postgres_materials import create_material


def test_new_catalog_links_codes_and_sequence_restore(pg, tmp_path):
    material = create_material(pg)
    result, order = confirm(pg)
    response = pg.api.command(
        f"/api/v1/orders/{order['id']}/material-links",
        {
            "expected_version": 1,
            "lines": [
                {
                    "line_id": order["lines"][0]["id"],
                    "material_id": material["id"],
                    "expected_material_version": 1,
                    "remember_code": True,
                    "customer_code": "A-017",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    before = pg.runtime.orders.detail(pg.actor, order["id"])
    original = pg.objects.joinpath(result["sha256"] + ".json").read_bytes()
    backup = tmp_path / "m1-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest
    with owned_database(pg, "ff_material_restore_") as (name, admin):
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
            assert restored.orders.detail(pg.actor, order["id"]) == before
            assert restored_objects.joinpath(result["sha256"] + ".json").read_bytes() == original
            assert (
                restored.materials.codes(pg.actor, material["id"])["items"][0]["customer_code"]
                == "A-017"
            )
            next_material = restored.materials.create(pg.actor, uuid4(), {"name": "Synthetic next"})
            assert int(next_material["own_code"][2:]) > int(material["own_code"][2:])
        finally:
            restored.close()


def test_0012_backup_upgrade_rollback_keeps_old_evidence_and_null_links(pg, tmp_path):
    with owned_database(pg, "ff_material_legacy_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0012_external_document_number")
            objects = tmp_path / "legacy-objects"
            objects.mkdir()
            runtime = build_services(Settings(url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic legacy", "synthetic", SYNTHETIC_PASSWORD
            )
            customer = runtime.customers.create(actor, uuid4(), "Synthetic legacy customer")
            input_order = payload() | {"customer_id": customer["id"]}
            key = uuid4()
            result = runtime.orders.confirm(actor, key, input_order)
            original = objects.joinpath(result["sha256"] + ".json").read_bytes()
            backup = tmp_path / "legacy-backup"
            assert (
                runtime.backup(backup, BINARY)["schema_revision"] == "0012_external_document_number"
            )
            with owner.begin() as conn:
                conn.execute(text("CREATE TABLE customer_material_codes(synthetic_marker integer)"))
                conn.execute(text("INSERT INTO customer_material_codes VALUES(12)"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    == "0012_external_document_number"
                )
                assert conn.execute(text("SELECT to_regclass('materials')")).scalar_one() is None
                assert (
                    conn.execute(text("SELECT to_regclass('material_code_seq')")).scalar_one()
                    is None
                )
                assert (
                    conn.execute(
                        text("SELECT synthetic_marker FROM customer_material_codes")
                    ).scalar_one()
                    == 12
                )
                conn.execute(text("DROP TABLE customer_material_codes"))
            with owned_database(pg, "ff_material_old_restore_") as (restored_name, restore_admin):
                restored_objects = tmp_path / "legacy-restored-objects"
                restore_backup(
                    restore_admin.render_as_string(hide_password=False),
                    restored_name,
                    restored_objects,
                    backup,
                    BINARY,
                    ROOT,
                )
                restored_url = make_url(pg.settings.database_url).set(database=restored_name)
                restored = build_services(
                    Settings(restored_url.render_as_string(hide_password=False), restored_objects)
                )
                try:
                    restored.check_ready()
                    assert (
                        restored.orders.confirm(actor, key, input_order | {"material_choices": []})
                        == result
                    )
                    assert all(
                        line["material_id"] is None
                        for line in restored.orders.detail(actor, result["order_id"])["lines"]
                    )
                    assert (
                        restored_objects.joinpath(result["sha256"] + ".json").read_bytes()
                        == original
                    )
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
