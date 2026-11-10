import asyncio
import json

import httpx
from mcp import Client

from factoryflow_mcp.api import Credentials
from factoryflow_mcp.server import create_server


def test_six_read_tools_and_protocol_rejections():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            return httpx.Response(200, json={"user": {"role": "viewer"}})
        return httpx.Response(200, json={"items": [], "next_cursor": None})

    server = create_server(
        Credentials("http://127.0.0.1:18123", "synthetic", "synthetic-password"),
        transport=httpx.MockTransport(handler),
    )

    async def run():
        async with Client(server) as client:
            listing = await client.list_tools()
            assert {t.name for t in listing.tools} == {
                "factoryflow_open_orders",
                "factoryflow_finished_inventory",
                "factoryflow_statement_status",
                "factoryflow_find_customers",
                "factoryflow_get_order",
                "factoryflow_check_order_confirmation",
            }
            for tool in listing.tools:
                assert tool.annotations.read_only_hint is True
                assert tool.annotations.destructive_hint is False
                assert "password" not in json.dumps(tool.input_schema)
                if tool.name in {
                    "factoryflow_find_customers",
                    "factoryflow_get_order",
                    "factoryflow_check_order_confirmation",
                }:
                    continue  # Their successful read paths are covered in test_queries_recovery.
                args = (
                    {"customer_id": "00000000-0000-4000-8000-000000000001"}
                    if tool.name == "factoryflow_statement_status"
                    else {}
                )
                result = await client.call_tool(tool.name, args)
                assert not result.is_error
                assert result.structured_content["items"] == []
            assert len(calls) == 6
            for name, args in [
                ("factoryflow_create_order", {}),
                ("factoryflow_open_orders", {"customer_id": "../other"}),
                ("factoryflow_open_orders", {"limit": 101}),
                ("factoryflow_open_orders", {"limit": True}),
                ("factoryflow_finished_inventory", {"cursor": "x" * 41}),
            ]:
                result = await client.call_tool(name, args)
                assert result.is_error
            assert len(calls) == 6

    asyncio.run(run())


def test_authentication_failure_is_error_not_success():
    server = create_server(
        Credentials("http://127.0.0.1:18123", "synthetic", "synthetic-password"),
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="secret-body")),
    )

    async def run():
        async with Client(server) as client:
            result = await client.call_tool("factoryflow_open_orders", {})
            assert result.is_error
            serialized = result.model_dump_json()
            assert "AUTHENTICATION_FAILED" in serialized
            assert "synthetic-password" not in serialized
            assert "secret-body" not in serialized

    asyncio.run(run())
