"""Imported identities, mappings, results and numbering survive the existing backup path."""

from uuid import uuid4

from conftest import ROOT
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import REVISION
from sqlalchemy.engine import make_url
from test_archive_migration import BINARY, owned_database
from test_postgres_material_import import confirm, mapped, preview


def test_imported_catalog_and_original_command_recover_with_numbering(pg, tmp_path):
    body = mapped(
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    shown = preview(pg, body)
    key = uuid4()
    saved = confirm(pg, body, shown, key)
    assert saved.status_code == 200, saved.text
    payload = body | {"preview_fingerprint": shown["preview_fingerprint"]}
    original = pg.runtime.materials.confirm_import(pg.actor, key, payload)
    before = pg.runtime.materials.list(pg.actor)
    codes = pg.runtime.materials.codes(pg.actor)
    backup = tmp_path / "m2-backup"
    assert pg.runtime.backup(backup, BINARY)["schema_revision"] == REVISION
    with owned_database(pg, "ff_m2_restore_") as (name, admin):
        objects = tmp_path / "recovered-objects"
        restore_backup(
            admin.render_as_string(hide_password=False), name, objects, backup, BINARY, ROOT
        )
        url = make_url(pg.settings.database_url).set(database=name)
        recovered = build_services(Settings(url.render_as_string(hide_password=False), objects))
        try:
            recovered.check_ready()
            assert recovered.materials.list(pg.actor) == before
            assert recovered.materials.codes(pg.actor) == codes
            assert recovered.materials.confirm_import(pg.actor, key, payload) == original
            next_item = recovered.materials.create(pg.actor, uuid4(), {"name": "Synthetic next"})
            auto = saved.json()["rows"][1]["material"]["own_code"]
            assert int(next_item["own_code"][2:]) > int(auto[2:])
        finally:
            recovered.close()
