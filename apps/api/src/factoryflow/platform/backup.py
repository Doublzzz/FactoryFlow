"""Consistent local snapshot + immutable objects, restored only into a new database."""

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

from factoryflow.platform.database import REVISION, engine_for
from factoryflow.platform.migrations import upgrade_database

SUPPORTED_BACKUP_REVISIONS = {
    "0002_quantity_scale",
    "0003_normal_delivery",
    "0004_document_extraction",
    "0005_order_item_fields",
    "0006_statement_drafts",
    "0007_statement_exports",
    "0008_delivery_layout",
    "0009_work_archives",
    "0010_statement_lifecycle",
    "0011_customer_templates",
    "0012_external_document_number",
    REVISION,
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pg_environment(url):
    if url.host not in {"127.0.0.1", "localhost", "::1"} or url.query:
        raise ValueError("Local maintenance requires an explicit loopback PostgreSQL URL")
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("PG")}
    env.update(
        PGHOST=url.host,
        PGHOSTADDR="127.0.0.1" if url.host == "localhost" else url.host,
        PGPORT=str(url.port or 5432),
        PGUSER=url.username or "",
        PGPASSWORD=url.password or "",
        PGDATABASE=url.database or "",
        PGCONNECT_TIMEOUT="5",
        PGCLIENTENCODING="UTF8",
    )
    return env


def pg_tool(binary: Path, name: str, url, *args):
    executable = binary / (name + (".exe" if os.name == "nt" else ""))
    result = subprocess.run(
        [str(executable), *map(str, args)],
        env=pg_environment(url),
        capture_output=True,
        timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode or result.stderr.strip():
        # pg tools can print connection details or data; callers get no raw stderr.
        raise RuntimeError(f"{name} failed or reported warnings; backup is not verified")


def create_backup(engine, destination: Path, binary: Path, list_hashes, read_object) -> dict:
    if destination.exists():
        raise ValueError("Backup destination already exists; nothing will be replaced")
    destination.mkdir(parents=True)
    objects = destination / "objects"
    objects.mkdir()
    dump = destination / "database.dump"
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        with conn.begin():
            conn.execute(text("SET TRANSACTION READ ONLY"))
            revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            if revision not in SUPPORTED_BACKUP_REVISIONS:
                raise ValueError("Backup requires the supported schema revision")
            snapshot = conn.execute(text("SELECT pg_export_snapshot()")).scalar_one()
            hashes = sorted(set(list_hashes(conn)))
            pg_tool(
                binary,
                "pg_dump",
                engine.url,
                "--format=custom",
                "--no-owner",
                "--no-acl",
                f"--snapshot={snapshot}",
                "--file",
                dump,
            )
            for digest in hashes:
                content = read_object(digest)
                with (objects / f"{digest}.json").open("xb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
    manifest = {
        "format": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "schema_revision": revision,
        "database_sha256": file_hash(dump),
        "objects": hashes,
    }
    with (destination / "manifest.json").open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(manifest, indent=2) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return manifest


def validate_backup(source: Path) -> dict:
    try:
        manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
        hashes = manifest["objects"]
        if (
            manifest["format"] != 1
            or manifest["schema_revision"] not in SUPPORTED_BACKUP_REVISIONS
            or not isinstance(hashes, list)
            or len(hashes) != len(set(hashes))
            or any(not isinstance(h, str) or not re.fullmatch(r"[0-9a-f]{64}", h) for h in hashes)
        ):
            raise ValueError
        files = [(source / "database.dump", manifest["database_sha256"])]
        files += [(source / "objects" / f"{h}.json", h) for h in hashes]
        for path, expected in files:
            if path.is_symlink() or file_hash(path) != expected:
                raise ValueError
    except OSError, KeyError, ValueError, TypeError:
        raise ValueError("Backup integrity validation failed") from None
    return manifest


def restore_backup(
    admin_url, database: str, object_root: Path, source: Path, binary: Path, repository_root: Path
):
    manifest = validate_backup(source)
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,62}", database) or database in {
        "postgres",
        "template0",
        "template1",
    }:
        raise ValueError("Choose a new, explicitly named application database")
    if object_root.exists():
        raise ValueError("Restore object directory already exists; nothing will be replaced")
    admin_url = make_url(admin_url) if isinstance(admin_url, str) else admin_url
    pg_environment(admin_url)
    connection_url = admin_url.set(drivername="postgresql", database="postgres")
    with psycopg.connect(
        connection_url.render_as_string(hide_password=False), autocommit=True
    ) as conn:
        # CREATE DATABASE refuses an existing name; there is deliberately no DROP or --clean.
        conn.execute(
            sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(database), sql.Identifier(admin_url.username)
            )
        )
    object_root.mkdir(parents=True)
    for digest in manifest["objects"]:
        content = (source / "objects" / f"{digest}.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("Backup integrity changed during restore")
        with (object_root / f"{digest}.json").open("xb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    target_url = admin_url.set(drivername="postgresql+psycopg", database=database)
    pg_tool(
        binary,
        "pg_restore",
        target_url,
        "--single-transaction",
        "--no-owner",
        "--no-acl",
        "--dbname",
        database,
        source / "database.dump",
    )
    engine = engine_for(target_url.render_as_string(hide_password=False))
    try:
        upgrade_database(engine, repository_root)
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM sessions"))
    finally:
        engine.dispose()
