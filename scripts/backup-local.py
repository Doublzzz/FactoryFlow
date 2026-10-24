"""Explicit backup/restore. Restore always requires a new database and object directory."""

import argparse
import json
from pathlib import Path

from factoryflow.bootstrap import build_services
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "restore"])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--admin-config", type=Path)
    parser.add_argument("--database")
    parser.add_argument("--object-root", type=Path)
    parser.add_argument(
        "--postgres-bin", type=Path, default=ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
    )
    args = parser.parse_args()
    if args.action == "create":
        if not args.config:
            parser.error("create requires --config")
        runtime = build_services(Settings.load(args.config))
        try:
            manifest = runtime.backup(args.backup, args.postgres_bin)
        finally:
            runtime.close()
        print(f"Backup verified: {len(manifest['objects'])} immutable objects.")
    else:
        if not args.admin_config or not args.database or not args.object_root:
            parser.error("restore requires --admin-config, --database and --object-root")
        admin = json.loads(args.admin_config.read_text(encoding="utf-8"))
        restore_backup(
            admin["admin_url"],
            args.database,
            args.object_root,
            args.backup,
            args.postgres_bin,
            ROOT,
        )
        print("Restored to a new database and object directory; sessions revoked.")
        print(
            "Explicitly configure the application to use the restored database before starting it."
        )


if __name__ == "__main__":
    main()
