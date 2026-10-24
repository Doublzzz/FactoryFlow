"""Explicit local migration and initial identity administration. Never starts on import."""

import argparse
import getpass
import json
from pathlib import Path

from factoryflow.bootstrap import build_services
from factoryflow.kernel.contracts import Actor
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for
from factoryflow.platform.migrations import upgrade_database
from sqlalchemy import text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["migrate", "setup", "add-user"])
    parser.add_argument("--admin-config", type=Path, required=True)
    parser.add_argument("--database", default="factoryflow_dev")
    parser.add_argument("--object-root", type=Path, default=ROOT / ".runtime/development/objects")
    parser.add_argument("--factory")
    parser.add_argument("--username")
    parser.add_argument("--role", choices=["operator", "viewer"])
    args = parser.parse_args()
    source = json.loads(args.admin_config.read_text(encoding="utf-8"))
    url = make_url(source["admin_url"]).set(drivername="postgresql+psycopg", database=args.database)
    engine = engine_for(url.render_as_string(hide_password=False))
    try:
        if args.action == "migrate":
            upgrade_database(engine, ROOT)
            print("Explicit migration completed.")
            return
        if not args.username:
            parser.error("--username is required")
        password = getpass.getpass("New local password (12–128 characters): ")
        if password != getpass.getpass("Repeat password: "):
            parser.error("Passwords differ")
        runtime = build_services(
            Settings(url.render_as_string(hide_password=False), args.object_root)
        )
        try:
            if args.action == "setup":
                if not args.factory:
                    parser.error("--factory is required")
                runtime.identity.provision_factory(args.factory, args.username, password)
            else:
                if not args.role:
                    parser.error("--role is required")
                with engine.connect() as conn:
                    row = (
                        conn.execute(
                            text(
                                "SELECT organization_id,id,username,role FROM users "
                                "WHERE role='admin' AND active ORDER BY id LIMIT 1"
                            )
                        )
                        .mappings()
                        .one()
                    )
                actor = Actor(row["organization_id"], row["id"], row["username"], row["role"])
                runtime.identity.add_user(actor, args.username, password, args.role)
            print("Local identity created. No password was printed or stored in source.")
        finally:
            runtime.close()
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
