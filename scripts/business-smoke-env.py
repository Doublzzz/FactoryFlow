"""Test-only PostgreSQL cluster owned by one smoke run, containing synthetic data only."""

import argparse
import json
import os
import secrets
import socket
import subprocess
import tempfile
from pathlib import Path

import psycopg
from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"


def run(name, *args):
    result = subprocess.run(
        [str(BIN / f"{name}.exe"), *map(str, args)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError(f"Synthetic PostgreSQL {name} failed (exit {result.returncode})")


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=[
            "prepare",
            "restart-database",
            "restore-check",
            "inspect",
            "expire-sessions",
            "stop",
        ],
    )
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    directory = args.root.resolve()
    if directory.parent != Path(tempfile.gettempdir()).resolve() or not directory.name.startswith(
        "factoryflow-business-"
    ):
        parser.error(
            "Only a dedicated factoryflow-business-* system temporary directory is accepted"
        )
    state_path = directory / "private-state.json"
    data = directory / "pgdata"
    if args.action == "prepare":
        if state_path.exists() or data.exists():
            parser.error("Smoke environment exists; refusing to replace it")
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        admin_password, runtime_password, login_password = (secrets.token_hex(24) for _ in range(3))
        admin_url = f"postgresql://ff_admin:{admin_password}@127.0.0.1:{port}/postgres"
        state = {"admin_url": admin_url, "runtime_password": runtime_password, "port": port}
        save(state_path, state)
        password_file = directory / "init-password.tmp"
        password_file.write_text(admin_password, encoding="utf-8")
        try:
            run(
                "initdb",
                "-D",
                data,
                "-U",
                "ff_admin",
                "--pwfile",
                password_file,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            )
        finally:
            password_file.unlink(missing_ok=True)
        with (data / "postgresql.conf").open("a", encoding="utf-8") as stream:
            stream.write(f"\nlisten_addresses='127.0.0.1'\nport={port}\n")
            stream.write("log_statement='none'\nlog_min_error_statement='panic'\n")
        run("pg_ctl", "-D", data, "-l", directory / "postgres.log", "-w", "start")
        with psycopg.connect(admin_url, autocommit=True) as conn:
            conn.execute(
                sql.SQL("CREATE ROLE ff_runtime LOGIN PASSWORD {}").format(
                    sql.Literal(runtime_password)
                )
            )
            conn.execute("CREATE DATABASE factoryflow_smoke OWNER ff_admin")
        owner_url = make_url(admin_url).set(
            drivername="postgresql+psycopg", database="factoryflow_smoke"
        )
        engine = engine_for(owner_url.render_as_string(hide_password=False))
        try:
            upgrade_database(engine, ROOT)
        finally:
            engine.dispose()
        objects = directory / "objects"
        objects.mkdir()
        app_url = owner_url.set(username="ff_runtime", password=runtime_password)
        app = {
            "database_url": app_url.render_as_string(hide_password=False),
            "object_root": str(objects),
            "secure_cookies": False,
        }
        save(directory / "app.json", app)
        runtime = build_services(Settings.load(directory / "app.json"))
        try:
            runtime.identity.provision_factory(
                "Synthetic Smoke Factory", "smoke-admin", login_password
            )
        finally:
            runtime.close()
        save(directory / "client.json", {"username": "smoke-admin", "password": login_password})
        print("Synthetic smoke cluster prepared.")
        return
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if args.action == "restart-database":
        run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")
        run("pg_ctl", "-D", data, "-l", directory / "postgres.log", "-w", "start")
        print("Owned synthetic cluster restarted.")
    elif args.action == "stop":
        if (data / "postmaster.pid").exists():
            run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")
        print("Owned synthetic cluster stopped; evidence retained.")
    elif args.action == "restore-check":
        runtime = build_services(Settings.load(directory / "app.json"))
        try:
            manifest = runtime.backup(directory / "backup", BIN)
        finally:
            runtime.close()
        restore_backup(
            state["admin_url"],
            "factoryflow_restored",
            directory / "restored-objects",
            directory / "backup",
            BIN,
            ROOT,
        )
        url = make_url(state["admin_url"]).set(
            drivername="postgresql+psycopg",
            database="factoryflow_restored",
            username="ff_runtime",
            password=state["runtime_password"],
        )
        save(
            directory / "app-restored.json",
            {
                "database_url": url.render_as_string(hide_password=False),
                "object_root": str(directory / "restored-objects"),
                "secure_cookies": False,
            },
        )
        print(json.dumps({"backup_objects": len(manifest["objects"]), "restored": True}))
    elif args.action == "expire-sessions":
        url = make_url(state["admin_url"]).set(database="factoryflow_smoke")
        with psycopg.connect(url.render_as_string(hide_password=False)) as conn:
            conn.execute("UPDATE sessions SET expires_at=now()-interval '1 second'")
        print("Synthetic sessions expired.")
    else:
        settings = Settings.load(directory / "app.json")
        engine = engine_for(settings.database_url)
        try:
            with engine.connect() as conn:
                counts = {
                    table: conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
                    for table in (
                        "orders",
                        "order_lines",
                        "confirmed_revisions",
                        "order_events",
                        "deliveries",
                        "fulfillment_actions",
                        "source_files",
                        "extraction_runs",
                        "source_imports",
                    )
                }
        finally:
            engine.dispose()
        print(json.dumps(counts))


if __name__ == "__main__":
    main()
