"""Restore must prove both PostgreSQL contents and immutable JSON, not just copy a dump."""

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from conftest import ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.platform.config import Settings
from psycopg import sql
from sqlalchemy.engine import make_url
from test_postgres_orders import confirm


def backup_module():
    name = "factoryflow.platform.backup"
    assert importlib.util.find_spec(name) is not None, (
        "Consistent backup/restore is not implemented"
    )
    return __import__(name, fromlist=["create_backup"])


def test_backup_restore_reopens_exact_snapshot_despite_a_concurrent_order(
    pg, tmp_path, monkeypatch
):
    module = backup_module()
    result = confirm(pg)
    backup = tmp_path / "backup"
    binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
    original_tool = module.pg_tool

    def commit_after_exported_snapshot(binary, name, url, *args):
        if name == "pg_dump":
            confirm(pg, number="SYN-AFTER-SNAPSHOT")
        return original_tool(binary, name, url, *args)

    monkeypatch.setattr(module, "pg_tool", commit_after_exported_snapshot)
    pg.runtime.backup(backup, binary)
    assert len(pg.runtime.orders.open_lines(pg.actor)["items"]) == 4
    manifest = json.loads((backup / "manifest.json").read_text())
    assert manifest["objects"] == [result["sha256"]]
    assert sorted(p.name for p in backup.iterdir()) == ["database.dump", "manifest.json", "objects"]
    target = "ff_restore_" + uuid4().hex
    private = json.loads(Path(os.environ["FACTORYFLOW_TEST_ADMIN_CONFIG"]).read_text())
    admin = make_url(private["admin_url"])
    object_root = tmp_path / "restored-objects"
    runtime = None
    try:
        module.restore_backup(admin, target, object_root, backup, binary, ROOT)
        url = admin.set(
            drivername="postgresql+psycopg",
            database=target,
            username="ff_runtime",
            password=private["runtime_password"],
        )
        runtime = build_services(Settings(url.render_as_string(hide_password=False), object_root))
        with pytest.raises(ValueError):
            runtime.identity.authenticate(pg.api.cookies.get("ff_session"))
        login = runtime.identity.login("synthetic-admin", SYNTHETIC_PASSWORD)
        lines = runtime.orders.open_lines(login["actor"])["items"]
        assert [line["quantity"] for line in lines] == ["1.125", "2"]
        assert (
            runtime.orders.evidence(login["actor"], result["revision_id"])["sha256"]
            == result["sha256"]
        )
    finally:
        if runtime:
            runtime.close()
        with psycopg.connect(private["admin_url"], autocommit=True) as conn:
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(target))
            )


def test_restore_rejects_tampered_backup_before_creating_database(pg, tmp_path):
    module = backup_module()
    result = confirm(pg)
    backup = tmp_path / "backup"
    binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
    pg.runtime.backup(backup, binary)
    (backup / "objects" / (result["sha256"] + ".json")).write_text("tampered")
    target = "ff_restore_" + uuid4().hex
    with pytest.raises(ValueError, match="integrity"):
        module.restore_backup(
            pg.admin_url.set(database="postgres"),
            target,
            tmp_path / "restored",
            backup,
            binary,
            ROOT,
        )
    with pg.owner.connect() as conn:
        from sqlalchemy import text

        assert not conn.execute(
            text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": target}
        ).scalar_one()
