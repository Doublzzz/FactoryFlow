"""Provision/check only the new temporary MCP order-write demonstration cluster."""

import argparse
import hashlib
import json
import secrets
import tempfile
from collections import Counter
from pathlib import Path

import psycopg
from factoryflow.bootstrap import build_services
from factoryflow.platform.config import Settings
from psycopg import sql
from sqlalchemy.engine import make_url


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def connect(root):
    state = json.loads((root / "private-state.json").read_text(encoding="utf-8"))
    url = make_url(state["admin_url"])
    config = Settings.load(root / "app.json")
    runtime_url = make_url(config.database_url)
    if (
        url.host != "127.0.0.1"
        or runtime_url.host != url.host
        or runtime_url.port != url.port
        or runtime_url.database != "factoryflow_smoke"
    ):
        raise ValueError("Synthetic database identity mismatch")
    return psycopg.connect(
        url.set(database="factoryflow_smoke").render_as_string(hide_password=False)
    )


def snapshot(root):
    result = {}
    with connect(root) as conn:
        for (table,) in conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall():
            if table == "sessions":
                continue
            condition = (
                sql.SQL(" WHERE command_type <> 'identity.login'")
                if table == "audit_events"
                else sql.SQL("")
            )
            rows = conn.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t{}").format(
                    sql.Identifier(table), condition
                )
            ).fetchall()
            result[table] = sorted(hashlib.sha256(r[0].encode()).hexdigest() for r in rows)
    return result


def provision(root):
    target = root / "mcp-order-credentials.json"
    if target.exists():
        raise ValueError("Operator already provisioned; refusing replacement")
    with connect(root):
        pass
    admin = json.loads((root / "client.json").read_text(encoding="utf-8"))
    reader = json.loads((root / "mcp-credentials.json").read_text(encoding="utf-8"))
    config = Settings.load(root / "app.json")
    runtime = build_services(config)
    password = secrets.token_urlsafe(32)
    try:
        actor = runtime.identity.login(**admin)["actor"]
        runtime.identity.add_user(actor, "mcp-synthetic-operator", password, "operator")
    finally:
        runtime.close()
    save(
        target,
        {
            "api_url": reader["api_url"],
            "username": "mcp-synthetic-operator",
            "password": password,
            "dataset": "synthetic",
        },
    )
    save(root / "before-order-writes.json", snapshot(root))
    print("Dedicated synthetic operator created; append-only baseline recorded.")


def check(root, expected):
    before = json.loads((root / "before-order-writes.json").read_text(encoding="utf-8"))
    after = snapshot(root)
    assert set(before) == set(after), "Unexpected schema change"
    changes = {}
    allowed = {
        "orders",
        "order_lines",
        "order_events",
        "confirmed_revisions",
        "command_results",
        "audit_events",
    }
    for table, rows in after.items():
        old, new = Counter(before[table]), Counter(rows)
        assert not (old - new), f"Existing synthetic rows changed: {table}"
        additions = sum((new - old).values())
        if additions:
            assert table in allowed, f"Unexpected business write: {table}"
            changes[table] = additions
    assert changes.get("orders", 0) == expected
    assert changes.get("order_lines", 0) == expected * 2
    assert changes.get("confirmed_revisions", 0) == expected
    assert changes.get("order_events", 0) == expected
    assert changes.get("command_results", 0) == expected
    receipt = {
        "existing_rows_unchanged": True,
        "tables_checked": len(after),
        "expected_new_orders": expected,
        "appended_rows": changes,
        "inventory_fulfillment_statements_unchanged": True,
    }
    save(root / "order-write-receipt.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["provision", "check"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-orders", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-mcp-orders-"
    ):
        parser.error("Only a new task-owned synthetic order test root is accepted")
    if args.action == "provision":
        provision(root)
    else:
        if args.expected_orders is None or args.expected_orders < 0:
            parser.error("Explicit nonnegative expected order count is required")
        check(root, args.expected_orders)
