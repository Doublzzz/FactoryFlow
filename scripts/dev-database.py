"""Prepare/start a project-private synthetic PostgreSQL cluster; no system service."""

import argparse
import json
import os
import secrets
import subprocess
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".tools" / "postgresql-18.6-4" / "pgsql" / "bin"
STATE = ROOT / ".runtime" / "development"
PORT = 55433


def run(name, *args):
    return subprocess.run(
        [str(BIN / f"{name}.exe"), *map(str, args)],
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "start", "stop", "status"])
    args = parser.parse_args()
    if not (BIN / "pg_ctl.exe").is_file():
        parser.error("Prepare the documented EDB PostgreSQL binary archive first.")
    data = STATE / "pgdata"
    config_path = STATE / "admin.json"
    if args.action == "prepare":
        if data.exists() or config_path.exists():
            parser.error("Development cluster already exists; use start/status. Nothing replaced.")
        STATE.mkdir(parents=True, exist_ok=True)
        admin_password = secrets.token_hex(32)
        app_password = secrets.token_hex(32)
        config = {
            "admin_url": f"postgresql://ff_admin:{admin_password}@127.0.0.1:{PORT}/postgres",
            "runtime_password": app_password,
            "port": PORT,
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        password_file = STATE / "init-password.tmp"
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
            stream.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\n")
            stream.write("log_statement = 'none'\nlog_min_error_statement = 'panic'\n")
        run("pg_ctl", "-D", data, "-l", STATE / "postgres.log", "-w", "start")
        with psycopg.connect(config["admin_url"], autocommit=True) as conn:
            from psycopg import sql

            conn.execute(
                sql.SQL("CREATE ROLE ff_runtime LOGIN PASSWORD {}").format(
                    sql.Literal(app_password)
                )
            )
            conn.execute("CREATE DATABASE factoryflow_dev OWNER ff_admin")
        application = {
            "database_url": f"postgresql+psycopg://ff_runtime:{app_password}"
            f"@127.0.0.1:{PORT}/factoryflow_dev",
            "object_root": str(STATE / "objects"),
            "secure_cookies": False,
        }
        (STATE / "app.json").write_text(json.dumps(application, indent=2) + "\n", encoding="utf-8")
        (STATE / "objects").mkdir()
        print("Prepared synthetic development cluster. Config: .runtime/development/app.json")
        print("Explicit migration and first-account setup are still required.")
    elif args.action == "start":
        run("pg_ctl", "-D", data, "-l", STATE / "postgres.log", "-w", "start")
    elif args.action == "stop":
        run("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")
    else:
        run("pg_ctl", "-D", data, "status")


if __name__ == "__main__":
    main()
