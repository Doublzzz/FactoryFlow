"""PI11/14: old fingerprints, atomic 0018 migration and source-complete restores."""

import base64
import hashlib
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.modules.documents.application.extraction import encode
from factoryflow.modules.purchasing.adapters.http import PurchaseOrderInput
from factoryflow.modules.purchasing.adapters.repository import PurchasingRepository
from factoryflow.platform.backup import restore_backup, validate_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION, Journal, engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_archive_migration import BINARY, owned_database
from test_postgres_extraction import PNG
from test_purchase_document_safeguards import upload_sheet
from test_purchase_documents import BASE, effects, inputs, ok
from test_purchase_spreadsheet import workbook
from test_supply_restore import rows


def test_purchase_backup_restores_original_trace_prices_print_and_replay(pg, tmp_path):
    _, _, body = inputs(pg)
    content = workbook()
    upload, detail = upload_sheet(pg, content)
    body |= {
        "currency": "USD",
        "buyer_name": "Synthetic buyer",
        "source_id": upload["source_id"],
        "extraction_id": detail["extraction_id"],
    }
    body["lines"][0] |= {"source_unit_price": "2.50", "source_amount": "7.49"}
    key = uuid4()
    saved = ok(pg.api.command(BASE, body, key))
    before = effects(pg) | rows(pg.owner, ("source_files", "extraction_runs", "source_imports"))
    backup = tmp_path / "purchase-backup"
    manifest = pg.runtime.backup(backup, BINARY)
    assert manifest["schema_revision"] == REVISION
    assert validate_backup(backup) == manifest and len(manifest["objects"]) == 2
    with owned_database(pg, "ff_purchase_restore_") as (name, admin):
        objects = tmp_path / "restored-objects"
        restore_backup(admin, name, objects, backup, BINARY, ROOT)
        url = make_url(pg.settings.database_url).set(database=name)
        restored = build_services(Settings(url.render_as_string(hide_password=False), objects))
        try:
            restored.check_ready()
            assert rows(restored.engine, before) == before
            assert restored.extraction.original(pg.actor, upload["source_id"])[1] == content
            assert restored.extraction.detail(pg.actor, detail["extraction_id"]) == detail | {
                key: value
                for key, value in pg.runtime.extraction.detail(
                    pg.actor, detail["extraction_id"]
                ).items()
                if key not in detail
            }
            request = PurchaseOrderInput.model_validate(body).model_dump(mode="json")
            assert restored.purchasing.create_order(pg.actor, key, request) == saved
            assert rows(restored.engine, before) == before
            for original in pg.objects.glob("*.json"):
                assert (objects / original.name).read_bytes() == original.read_bytes()
        finally:
            restored.close()


def original_rows(engine):
    removed = {
        "source_files": ["purpose"],
        "purchase_orders": ["currency", "buyer_name", "source_id", "extraction_id"],
        "purchase_order_lines": ["source_unit_price", "source_amount"],
    }
    with engine.connect() as conn:
        return {
            table: list(
                conn.execute(
                    text(
                        "SELECT (to_jsonb(t)-CAST(:keys AS text[]))::text "
                        f"FROM {table} t ORDER BY 1"
                    ),
                    {"keys": removed.get(table, [])},
                ).scalars()
            )
            for table in (*removed, "suppliers", "materials", "audit_events", "command_results")
        }


def frozen_0017_facts(runtime, actor):
    """Seed only the actual 0017 columns and exact pre-0018 command payloads."""
    supplier = runtime.purchasing.create_supplier(
        actor, uuid4(), {"full_name": "Synthetic legacy supplier"}
    )
    material = runtime.materials.create(
        actor, uuid4(), {"kind": "raw", "name": "Synthetic legacy raw", "unit": "KG"}
    )
    key, identifier, line_id = uuid4(), uuid4(), uuid4()
    body = {
        "supplier_id": supplier["id"],
        "number": None,
        "note": None,
        "business_date": "2026-10-27",
        "lines": [{"material_id": material["id"], "quantity": "3"}],
    }
    params = {
        "org": actor.organization_id,
        "actor": actor.user_id,
        "id": identifier,
        "line": line_id,
        "supplier": supplier["id"],
        "supplier_name": supplier["full_name"],
        "material": material["id"],
        "code": material["own_code"],
        "material_name": material["name"],
    }
    with runtime.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO purchase_orders
            (organization_id,id,supplier_id,number,business_date,supplier_name,created_by)
            VALUES(:org,:id,:supplier,'SYN-LEGACY-PO','2026-10-27',:supplier_name,:actor)"""),
            params,
        )
        conn.execute(
            text("""INSERT INTO purchase_order_lines
            (organization_id,id,order_id,line_number,material_id,own_code,material_name,canonical_unit,ordered_quantity)
            VALUES(:org,:line,:id,1,:material,:code,:material_name,'KG',3)"""),
            params,
        )
        result = PurchasingRepository.view(
            conn.execute(text("SELECT * FROM purchase_orders WHERE id=:id"), params)
            .mappings()
            .one()
        )
        result["lines"] = [
            PurchasingRepository.view(
                conn.execute(text("SELECT * FROM purchase_order_lines WHERE id=:line"), params)
                .mappings()
                .one()
            )
            | {"received_quantity": "0", "remaining_quantity": "3"}
        ]
        journal = Journal(conn)
        assert journal.claim(actor, "purchase_order.create", key, body) is None
        journal.audit(actor, "purchase_order.create", identifier)
        journal.finish(actor, "purchase_order.create", key, result)
    upload_key, source_id = uuid4(), uuid4()
    digest = hashlib.sha256(PNG).hexdigest()
    blob = runtime.extraction.store.put(
        encode(
            {
                "format": "source-file-v1",
                "media_type": "image/png",
                "original_sha256": digest,
                "base64": base64.b64encode(PNG).decode(),
            }
        )
    )
    upload = {"source_id": str(source_id), "original_sha256": digest}
    with runtime.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO source_files
            (organization_id,id,actor_id,filename,media_type,byte_size,original_sha256,blob_hash)
            VALUES(:org,:id,:actor,'synthetic-legacy.png','image/png',:size,:sha,:blob)"""),
            {
                "org": actor.organization_id,
                "id": source_id,
                "actor": actor.user_id,
                "size": len(PNG),
                "sha": digest,
                "blob": blob,
            },
        )
        journal = Journal(conn)
        journal.claim(
            actor,
            "source.upload",
            upload_key,
            {"filename": "synthetic-legacy.png", "media_type": "image/png", "sha256": digest},
        )
        journal.audit(actor, "source.upload", source_id)
        journal.finish(actor, "source.upload", upload_key, upload)
    return key, body, result, upload_key, upload


def test_0017_migration_failure_restore_and_old_key_replay(pg, tmp_path):
    with owned_database(pg, "ff_purchase_old_") as (name, admin):
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(name)))
        owner_url = pg.admin_url.set(database=name).render_as_string(hide_password=False)
        owner = engine_for(owner_url)
        runtime = None
        try:
            config = Config(str(ROOT / "alembic.ini"))
            with owner.begin() as conn:
                config.attributes["connection"] = conn
                command.upgrade(config, "0017_production")
            objects = tmp_path / "old-objects"
            objects.mkdir()
            runtime = build_services(Settings(owner_url, objects))
            actor = runtime.identity.provision_factory(
                "Synthetic legacy purchase", "synthetic-old", SYNTHETIC_PASSWORD
            )
            key, body, saved, upload_key, upload = frozen_0017_facts(runtime, actor)
            before = original_rows(owner)
            backup = tmp_path / "0017-backup"
            assert runtime.backup(backup, BINARY)["schema_revision"] == "0017_production"
            validate_backup(backup)
            with owner.begin() as conn:
                conn.execute(text("ALTER TABLE purchase_orders ADD COLUMN currency text"))
            with pytest.raises(DBAPIError):
                upgrade_database(owner, ROOT)
            with owner.begin() as conn:
                assert (
                    conn.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0017_production"
                )
                assert (
                    conn.scalar(
                        text(
                            "SELECT count(*) FROM information_schema.columns "
                            "WHERE table_name='source_files' AND column_name='purpose'"
                        )
                    )
                    == 0
                )
                conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN currency"))
            assert original_rows(owner) == before
            upgrade_database(owner, ROOT)
            assert original_rows(owner) == before
            request = PurchaseOrderInput.model_validate(body).model_dump(mode="json")
            assert runtime.purchasing.create_order(actor, key, request) == saved
            assert (
                runtime.extraction.upload(
                    actor, upload_key, "synthetic-legacy.png", "image/png", PNG
                )
                == upload
            )
            with owned_database(pg, "ff_purchase_old_restore_") as (restored_name, restore_admin):
                restored_objects = tmp_path / "restored-old-objects"
                restore_backup(restore_admin, restored_name, restored_objects, backup, BINARY, ROOT)
                url = make_url(pg.settings.database_url).set(database=restored_name)
                restored = build_services(
                    Settings(url.render_as_string(hide_password=False), restored_objects)
                )
                try:
                    restored.check_ready()
                    assert original_rows(restored.engine) == before
                    assert restored.purchasing.create_order(actor, key, request) == saved
                    assert (
                        restored.extraction.upload(
                            actor, upload_key, "synthetic-legacy.png", "image/png", PNG
                        )
                        == upload
                    )
                    assert (
                        restored.extraction.original(actor, upload["source_id"])[0]["purpose"]
                        == "sales_order"
                    )
                    assert restored.purchasing.get_order(actor, saved["id"])["currency"] is None
                    for original in objects.glob("*.json"):
                        assert (
                            restored_objects / original.name
                        ).read_bytes() == original.read_bytes()
                finally:
                    restored.close()
        finally:
            if runtime:
                runtime.close()
            owner.dispose()
