"""Seed and verify only the new MCP synthetic smoke cluster, never an existing factory."""

import argparse
import hashlib
import json
import secrets
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from factoryflow.bootstrap import build_services
from factoryflow.platform.config import Settings
from psycopg import sql
from sqlalchemy.engine import make_url


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def snapshot(root):
    state = json.loads((root / "private-state.json").read_text(encoding="utf-8"))
    url = make_url(state["admin_url"]).set(database="factoryflow_smoke")
    result = {}
    with psycopg.connect(url.render_as_string(hide_password=False)) as conn:
        tables = conn.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ).fetchall()
        for (table,) in tables:
            if table == "sessions":
                continue
            condition = (
                sql.SQL(" WHERE command_type <> 'identity.login'")
                if table == "audit_events"
                else sql.SQL("")
            )
            rows = conn.execute(
                sql.SQL("SELECT row_to_json(t)::text FROM {} t{}").format(
                    sql.Identifier(table),
                    condition,
                )
            ).fetchall()
            encoded = "\n".join(sorted(r[0] for r in rows)).encode()
            result[table] = {"rows": len(rows), "sha256": hashlib.sha256(encoded).hexdigest()}
        sessions = conn.execute("SELECT count(*) FROM sessions").fetchone()[0]
        logins = conn.execute(
            "SELECT count(*) FROM audit_events WHERE command_type='identity.login'"
        ).fetchone()[0]
    return {"business": result, "sessions": sessions, "login_audits": logins}


def seed(root, port):
    if (root / "seed-started.marker").exists() or (root / "synthetic-ids.json").exists():
        raise ValueError("Already seeded; refusing duplicate business writes")
    config = Settings.load(root / "app.json")
    url = make_url(config.database_url)
    if url.host != "127.0.0.1" or url.database != "factoryflow_smoke":
        raise ValueError("Synthetic database identity mismatch")
    (root / "seed-started.marker").write_text("synthetic seed started\n", encoding="utf-8")
    admin = json.loads((root / "client.json").read_text(encoding="utf-8"))
    runtime = build_services(config)
    password = secrets.token_urlsafe(32)
    try:
        actor = runtime.identity.login(**admin)["actor"]
        runtime.identity.add_user(actor, "mcp-synthetic-viewer", password, "viewer")
    finally:
        runtime.close()
    origin = f"http://127.0.0.1:{port}"
    with httpx.Client(base_url=origin, timeout=30, trust_env=False) as client:
        response = client.post("/api/v1/auth/login", json=admin)
        response.raise_for_status()
        csrf = response.json()["csrf_token"]

        def command(path, body):
            response = client.post(
                "/api/v1" + path,
                json=body,
                headers={
                    "X-CSRF-Token": csrf,
                    "Idempotency-Key": str(uuid4()),
                },
            )
            if response.status_code != 200:
                raise RuntimeError(f"Synthetic seed failed: {path} HTTP {response.status_code}")
            return response.json()

        customer = command("/customers", {"full_name": "合成测试客户 SYN-MCP"})
        material = command(
            "/materials",
            {
                "own_code": "SYN-MCP-OPEN",
                "name": "合成成品A",
                "unit": "PCS",
            },
        )
        unopened = command(
            "/materials",
            {
                "own_code": "SYN-MCP-UNKNOWN",
                "name": "合成成品B（未开账）",
                "unit": "PCS",
            },
        )
        zero = command(
            "/materials",
            {
                "own_code": "SYN-MCP-ZERO",
                "name": "合成成品C（已开账零库存）",
                "unit": "PCS",
            },
        )
        command(
            f"/inventory/{zero['id']}/open",
            {
                "quantity": "0",
                "business_date": "2026-10-27",
            },
        )
        command(
            f"/inventory/{material['id']}/open",
            {
                "quantity": "20",
                "business_date": "2026-10-27",
            },
        )
        order = command(
            "/orders",
            {
                "customer_id": customer["id"],
                "order_number": "SYN-MCP-001",
                "business_date": "2026-10-27",
                "currency": "CNY",
                "lines": [{"item_name": "合成成品A", "quantity": "10", "unit": "PCS"}],
                "material_choices": [
                    {
                        "line_number": 1,
                        "material_id": material["id"],
                        "expected_material_version": 1,
                    }
                ],
            },
        )
        detail = client.get(f"/api/v1/orders/{order['order_id']}").json()
        line_id = detail["lines"][0]["id"]
        delivery = command(
            "/deliveries",
            {
                "order_id": order["order_id"],
                "customer_id": customer["id"],
                "revision_id": order["revision_id"],
                "expected_version": 1,
                "delivery_date": "2026-10-27",
                "lines": [{"order_line_id": line_id, "quantity": "4"}],
            },
        )
        statement = command(
            "/statements",
            {
                "customer_id": customer["id"],
                "currency": "CNY",
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "tax_mode": "untaxed_final",
                "tax_rate": "0",
                "adjustments": [],
                "lines": [
                    {
                        "delivery_id": delivery["id"],
                        "order_line_id": line_id,
                        "quantity": "4",
                        "unit_price": "2.50",
                        "reason": "Synthetic agreed price",
                    }
                ],
            },
        )
    credential = {
        "api_url": origin,
        "username": "mcp-synthetic-viewer",
        "password": password,
        "dataset": "synthetic",
    }
    save(root / "mcp-credentials.json", credential)
    save(
        root / "synthetic-ids.json",
        {
            "customer_id": customer["id"],
            "material_id": material["id"],
            "unopened_material_id": unopened["id"],
            "zero_material_id": zero["id"],
            "order_id": order["order_id"],
            "statement_id": statement["id"],
        },
    )
    # A viewer must also be rejected by the owning API even if bypassing MCP.
    with httpx.Client(base_url=origin, timeout=15, trust_env=False) as client:
        auth = client.post(
            "/api/v1/auth/login",
            json={
                "username": credential["username"],
                "password": password,
            },
        ).json()
        denied = client.post(
            "/api/v1/customers",
            json={"full_name": "SYN-MUST-NOT-EXIST"},
            headers={"X-CSRF-Token": auth["csrf_token"], "Idempotency-Key": str(uuid4())},
        )
        assert denied.status_code == 403
    save(root / "before-mcp.json", snapshot(root))
    print("Synthetic seed ready; viewer business write rejected (403); baseline saved.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["seed", "check"])
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-mcp-"
    ):
        parser.error("Only this task's new temporary synthetic cluster is accepted")
    if args.action == "seed":
        if not args.port or args.port in {8120, 8123}:
            parser.error("An isolated synthetic API port is required")
        seed(root, args.port)
    else:
        before = json.loads((root / "before-mcp.json").read_text(encoding="utf-8"))
        after = snapshot(root)
        unchanged = before["business"] == after["business"]
        receipt = {
            "business_tables_unchanged": unchanged,
            "tables_checked": len(after["business"]),
            "new_sessions": after["sessions"] - before["sessions"],
            "new_login_audits": after["login_audits"] - before["login_audits"],
        }
        save(root / "read-only-receipt.json", receipt)
        print(json.dumps(receipt))
        if not unchanged:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
