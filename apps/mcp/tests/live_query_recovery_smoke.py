"""Real HTTP/stdio, lost response and process restart, on a new synthetic root only."""

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

import httpx
from mcp import Client
from mcp.client.stdio import StdioServerParameters

from factoryflow_mcp.api import Credentials
from factoryflow_mcp.orders import ManualOrder, OrderWorkflow


def parameters(root, *, writer=False):
    args = ["-m", "factoryflow_mcp.server", "--credentials", str(root / "mcp-credentials.json")]
    if writer:
        args.extend(["--order-writer-credentials", str(root / "mcp-order-credentials.json")])
    return StdioServerParameters(command=sys.executable, args=args)


async def call(client, name, args):
    result = await client.call_tool(name, args)
    assert not result.is_error, result.content
    return result.structured_content


def order(customer_id, number):
    return {
        "customer_id": customer_id,
        "order_number": number,
        "business_date": "2026-11-09",
        "currency": "CNY",
        "lines": [
            {
                "item_name": "SYN Recovery part",
                "quantity": "3",
                "unit": "PCS",
                "source_unit_price": "2.50",
                "source_amount": "7.50",
            },
            {"item_name": "SYN Recovery bulk", "quantity": "1.125", "unit": "KG"},
        ],
    }


def confirm_with_lost_http_response(root, body):
    def forward_then_drop(request):
        # The owning HTTP API really commits. Only the response to this adapter is lost.
        with httpx.Client(timeout=15, follow_redirects=False, trust_env=False) as client:
            response = client.send(request)
            content = response.read()
        if request.method == "POST" and request.url.path == "/api/v1/orders":
            assert response.status_code == 200
            raise httpx.ReadTimeout("Synthetic lost confirmation response", request=request)
        return httpx.Response(response.status_code, headers=response.headers, content=content)

    workflow = OrderWorkflow(
        Credentials.load(root / "mcp-order-credentials.json"),
        transport=httpx.MockTransport(forward_then_drop),
    )
    preview = workflow.prepare(ManualOrder.model_validate(body))
    result = workflow.confirm(preview["prepared_id"])
    assert result["outcome"] == "unknown"
    return preview["prepared_id"], result


async def run(root):
    ids = json.loads((root / "synthetic-ids.json").read_text(encoding="utf-8"))
    evidence = {}
    async with Client(parameters(root), read_timeout_seconds=30) as client:
        listing = await client.list_tools()
        assert len(listing.tools) == 6
        assert all(tool.annotations.read_only_hint for tool in listing.tools)
        customers = await call(
            client, "factoryflow_find_customers", {"name": "SYN-MCP", "limit": 1}
        )
        assert customers["items"] == [
            {"id": ids["customer_id"], "full_name": "合成测试客户 SYN-MCP"}
        ]
        by_number = await call(
            client,
            "factoryflow_get_order",
            {"customer_id": ids["customer_id"], "order_number": "SYN-MCP-001"},
        )
        by_id = await call(client, "factoryflow_get_order", {"order_id": ids["order_id"]})
        assert by_number["order"] == by_id["order"]
        assert by_id["order"]["lines"][0]["remaining_quantity"] == "6"
        absent = await call(
            client, "factoryflow_check_order_confirmation", {"prepared_id": str(uuid4())}
        )
        assert absent["outcome"] == "unknown" and absent["may_create_new_preview"] is False
        evidence["readonly_discovery"] = {"customers": customers, "order": by_id, "absent": absent}

    async with Client(parameters(root, writer=True), read_timeout_seconds=30) as client:
        listing = await client.list_tools()
        assert len(listing.tools) == 8
        prepared = await call(
            client,
            "factoryflow_prepare_order",
            {"order": order(ids["customer_id"], "SYN-RECOVERY-STDIO-001")},
        )
        unsent = await call(
            client,
            "factoryflow_prepare_order",
            {"order": order(ids["customer_id"], "SYN-RECOVERY-UNSENT")},
        )
        # Deliberately discard the confirmation result, then close the actual stdio process.
        await call(client, "factoryflow_confirm_order", {"prepared_id": prepared["prepared_id"]})
        evidence["discarded_confirmation_response"] = True

    lost_id, lost = await asyncio.to_thread(
        confirm_with_lost_http_response, root, order(ids["customer_id"], "SYN-RECOVERY-HTTP-001")
    )
    evidence["lost_http_response"] = lost

    async with Client(parameters(root), read_timeout_seconds=30) as client:
        for label, key, number in [
            ("after_stdio_restart", prepared["prepared_id"], "SYN-RECOVERY-STDIO-001"),
            ("after_lost_http_response", lost_id, "SYN-RECOVERY-HTTP-001"),
        ]:
            checked = await call(
                client, "factoryflow_check_order_confirmation", {"prepared_id": key}
            )
            assert checked["outcome"] == "confirmed" and checked["readback_status"] == "succeeded"
            assert checked["current_state_changed"] is False
            detail = checked["order"]
            assert detail["order_number"] == number
            assert detail["lines"][0]["source_unit_price"] == "2.50"
            assert detail["lines"][1]["source_amount"] is None
            direct = await call(
                client,
                "factoryflow_get_order",
                {"customer_id": ids["customer_id"], "order_number": number},
            )
            assert direct["order"]["id"] == checked["command_result"]["order_id"]
            evidence[label] = checked
        unknown = await call(
            client, "factoryflow_check_order_confirmation", {"prepared_id": unsent["prepared_id"]}
        )
        assert unknown["outcome"] == "unknown" and unknown["may_create_new_preview"] is False
        denied = await client.call_tool(
            "factoryflow_confirm_order", {"prepared_id": prepared["prepared_id"]}
        )
        assert denied.is_error
        evidence["unsent_preview_after_restart"] = unknown

    async with Client(parameters(root, writer=True), read_timeout_seconds=30) as client:
        expired = await client.call_tool(
            "factoryflow_confirm_order", {"prepared_id": prepared["prepared_id"]}
        )
        assert expired.is_error and "PREVIEW_NOT_FOUND" in expired.model_dump_json()
        checked = await call(
            client, "factoryflow_check_order_confirmation", {"prepared_id": prepared["prepared_id"]}
        )
        assert checked["outcome"] == "confirmed"
        evidence["expired_preview_rejected_but_receipt_available"] = True

    (root / "query-recovery-results.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        "QUERY_RECOVERY_OK: 6 viewer/8 opt-in tools; name and exact order lookup; "
        "stdio restart; real committed HTTP response lost; unknown never resubmits; 2 new orders."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    root = parser.parse_args().root.resolve()
    if root.parent != Path(tempfile.gettempdir()).resolve() or not root.name.startswith(
        "factoryflow-business-mcp-orders-"
    ):
        parser.error("Only a new isolated synthetic order-test root is allowed")
    marker = root / "query-recovery-started.marker"
    with marker.open("x", encoding="utf-8") as stream:
        stream.write("Synthetic query/recovery run started; do not rerun over partial evidence.\n")
    asyncio.run(run(root))
