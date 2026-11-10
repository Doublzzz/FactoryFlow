"""Explicit stdio smoke against the task-owned synthetic API (not a pytest fixture)."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def run(root):
    ids = json.loads((root / "synthetic-ids.json").read_text(encoding="utf-8"))
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "factoryflow_mcp.server",
            "--credentials",
            str(root / "mcp-credentials.json"),
        ],
    )
    results = {}
    async with Client(params, read_timeout_seconds=30) as client:
        listing = await client.list_tools()
        assert len(listing.tools) == 6

        async def call(name, args):
            result = await client.call_tool(name, args)
            assert not result.is_error, result.content
            return result.structured_content

        orders = await call("factoryflow_open_orders", {"limit": 1})
        line = orders["items"][0]
        assert line["order_id"] == ids["order_id"]
        assert (line["quantity"], line["delivered_quantity"], line["remaining_quantity"]) == (
            "10",
            "4",
            "6",
        )
        assert orders["complete"] is True
        inventory = await call("factoryflow_finished_inventory", {"limit": 1})
        assert not inventory["complete"]
        page2 = await call(
            "factoryflow_finished_inventory", {"limit": 1, "cursor": inventory["next_cursor"]}
        )
        assert page2["complete"]
        unopened = await call(
            "factoryflow_finished_inventory", {"material_id": ids["unopened_material_id"]}
        )
        assert unopened["complete"]
        items = {
            r["material"]["id"]: r for r in inventory["items"] + page2["items"] + unopened["items"]
        }
        assert items[ids["material_id"]]["account"]["balance"] == "16"
        assert items[ids["unopened_material_id"]]["account"] is None
        assert items[ids["zero_material_id"]]["account"]["balance"] == "0"
        statements = await call("factoryflow_statement_status", {"customer_id": ids["customer_id"]})
        statement = statements["items"][0]
        assert statement["id"] == ids["statement_id"]
        assert statement["status"] == "draft"
        assert statement["currency"] == "CNY"
        assert statement["calculation"]["total"] == "10.00"
        assert statement["payment_status"] == "not_recorded_by_this_api"
        customers = await call("factoryflow_find_customers", {"name": "SYN-MCP", "limit": 1})
        assert customers["items"][0]["id"] == ids["customer_id"]
        assert customers["complete"]
        detail = await call(
            "factoryflow_get_order",
            {"customer_id": ids["customer_id"], "order_number": "SYN-MCP-001"},
        )
        assert detail["order"]["id"] == ids["order_id"]
        assert detail["order"]["lines"][0]["remaining_quantity"] == "6"
        confirmation = await call(
            "factoryflow_check_order_confirmation", {"prepared_id": str(uuid4())}
        )
        assert (
            confirmation["outcome"] == "unknown" and confirmation["may_create_new_preview"] is False
        )
        rejected = await client.call_tool("factoryflow_create_order", {})
        assert rejected.is_error
        results = {
            "orders": orders,
            "inventory": [inventory, page2, unopened],
            "statements": statements,
            "customers": customers,
            "order_detail": detail,
            "unknown_confirmation": confirmation,
            "unknown_write_tool_rejected": True,
            "transport": "stdio",
        }
    (root / "protocol-results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "STDIO_OK: 6 read tools; 10/4/6, stock 16, unopened null, draft CNY 10.00, write rejected"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-mcp-"
    ):
        parser.error("Only the isolated synthetic smoke root is allowed")
    asyncio.run(run(root))
