"""Explicit stdio order write/replay against the task-owned synthetic HTTP server."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import Client
from mcp.client.stdio import StdioServerParameters


async def run(root, order_number):
    params = StdioServerParameters(
        command=sys.executable,
        args=[
            "-m",
            "factoryflow_mcp.server",
            "--credentials",
            str(root / "mcp-credentials.json"),
            "--order-writer-credentials",
            str(root / "mcp-order-credentials.json"),
        ],
    )
    async with Client(params, read_timeout_seconds=30) as client:
        listing = await client.list_tools()
        assert len(listing.tools) == 8

        async def call(name, args):
            result = await client.call_tool(name, args)
            assert not result.is_error, result.content
            return result.structured_content

        customers = await call("factoryflow_find_customers", {"name": "合成测试客户 SYN-MCP"})
        assert len(customers["items"]) == 1
        body = {
            "customer_id": customers["items"][0]["id"],
            "order_number": order_number,
            "business_date": "2026-10-27",
            "currency": "CNY",
            "lines": [
                {
                    "item_name": "合成成品",
                    "quantity": "3",
                    "unit": "PCS",
                    "source_unit_price": "2.50",
                    "source_amount": "7.50",
                },
                {"item_name": "合成散料", "quantity": "1.125", "unit": "KG"},
            ],
        }
        preview = await call("factoryflow_prepare_order", {"order": body})
        assert preview["write_performed"] is False
        before = await call("factoryflow_open_orders", {"customer_id": body["customer_id"]})
        assert all(row["order_number"] != order_number for row in before["items"])
        # This executable is the explicitly authorized synthetic test driver.
        confirmed = await call("factoryflow_confirm_order", {"prepared_id": preview["prepared_id"]})
        assert confirmed["outcome"] == "confirmed"
        assert confirmed["readback_status"] == "succeeded"
        order = confirmed["order"]
        assert order["order_number"] == order_number
        assert order["currency"] == "CNY"
        assert [
            (
                row["quantity"],
                row["delivered_quantity"],
                row["remaining_quantity"],
                row["canonical_unit"],
            )
            for row in order["lines"]
        ] == [("3", "0", "3", "PCS"), ("1.125", "0", "1.125", "KG")]
        assert order["lines"][0]["source_unit_price"] == "2.50"
        assert order["lines"][0]["source_amount"] == "7.50"
        assert order["lines"][1]["source_unit_price"] is None
        replay = await call("factoryflow_confirm_order", {"prepared_id": preview["prepared_id"]})
        assert replay["command_result"] == confirmed["command_result"]
        (root / f"stdio-order-write-{order_number}-results.json").write_text(
            json.dumps(
                {
                    "preview": preview,
                    "confirmed": confirmed,
                    "replayed": replay,
                    "same_order_on_replay": True,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print("STDIO_ORDER_OK: preview unchanged; confirm/readback; exact decimals; same-order replay.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--order-number",
        choices=["SYN-STDIO-WRITE-001", "SYN-STDIO-WRITE-002"],
        default="SYN-STDIO-WRITE-001",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-mcp-orders-"
    ):
        parser.error("Only the isolated synthetic order-test root is accepted")
    asyncio.run(run(root, args.order_number))
