import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from mcp import Client

from factoryflow_mcp.api import Credentials
from factoryflow_mcp.server import create_server

CUSTOMER = "00000000-0000-4000-8000-000000000001"
ORDER = "00000000-0000-4000-8000-000000000002"
REVISION = "00000000-0000-4000-8000-000000000003"
BODY = {
    "customer_id": CUSTOMER,
    "order_number": "SYN-WRITE-001",
    "business_date": "2026-10-27",
    "currency": "CNY",
    "lines": [
        {
            "item_name": "Synthetic part",
            "quantity": "3",
            "unit": "PCS",
            "source_unit_price": "2.50",
            "source_amount": "7.50",
        },
        {"item_name": "Synthetic bulk", "quantity": "1.125", "unit": "KG"},
    ],
}
PREVIEW = {
    "customer_id": CUSTOMER,
    "customer_name": "Synthetic customer",
    "order": {
        "order_number": "SYN-WRITE-001",
        "business_date": "2026-10-27",
        "currency": "CNY",
        "lines": [
            {
                "line_number": 1,
                "description": "Synthetic part",
                "item_name": "Synthetic part",
                "source_quantity_text": "3",
                "canonical_quantity": "3",
                "source_unit": "PCS",
                "source_unit_price": "2.50",
                "source_amount": "7.50",
                "quantity_policy": {
                    "mode": "INTEGER_ONLY",
                    "canonical_unit": "PCS",
                    "warning_codes": [],
                    "version": "v1",
                },
            },
            {
                "line_number": 2,
                "description": "Synthetic bulk",
                "item_name": "Synthetic bulk",
                "source_quantity_text": "1.125",
                "canonical_quantity": "1.125",
                "source_unit": "KG",
                "source_unit_price": None,
                "source_amount": None,
                "quantity_policy": {
                    "mode": "DECIMAL_ALLOWED",
                    "canonical_unit": "KG",
                    "warning_codes": [],
                    "version": "v1",
                },
            },
        ],
    },
    "material_suggestions": [],
}
RESULT = {
    "order_id": ORDER,
    "version": 1,
    "status": "active",
    "revision_id": REVISION,
    "sha256": "0" * 64,
    "revision_number": 1,
    "material_links": [],
}
DETAIL = {
    "id": ORDER,
    "customer_id": CUSTOMER,
    "customer_name": "Synthetic customer",
    "order_number": "SYN-WRITE-001",
    "business_date": "2026-10-27",
    "currency": "CNY",
    "revision_id": REVISION,
    "status": "active",
    "version": 1,
    "lines": [
        {
            "id": "00000000-0000-4000-8000-000000000011",
            "line_number": 1,
            "description": "Synthetic part",
            "item_name": "Synthetic part",
            "quantity": "3",
            "delivered_quantity": "0",
            "remaining_quantity": "3",
            "source_quantity_text": "3",
            "source_unit": "PCS",
            "canonical_unit": "PCS",
            "source_unit_price": "2.50",
            "source_amount": "7.50",
            "quantity_policy": {
                "mode": "INTEGER_ONLY",
                "canonical_unit": "PCS",
                "warning_codes": [],
                "version": "v1",
            },
        },
        {
            "id": "00000000-0000-4000-8000-000000000012",
            "line_number": 2,
            "description": "Synthetic bulk",
            "item_name": "Synthetic bulk",
            "quantity": "1.125",
            "delivered_quantity": "0",
            "remaining_quantity": "1.125",
            "source_quantity_text": "1.125",
            "source_unit": "KG",
            "canonical_unit": "KG",
            "source_unit_price": None,
            "source_amount": None,
            "quantity_policy": {
                "mode": "DECIMAL_ALLOWED",
                "canonical_unit": "KG",
                "warning_codes": [],
                "version": "v1",
            },
        },
    ],
    "revisions": [],
}


def make_server(handler, *, dataset="synthetic", origin="http://127.0.0.1:18123"):
    return create_server(
        Credentials(origin, "viewer", "private-viewer", "synthetic"),
        order_credentials=Credentials(origin, "operator", "private-operator", dataset),
        transport=httpx.MockTransport(handler),
    )


def upstream(request):
    path = request.url.path
    if path == "/api/v1/auth/login":
        return httpx.Response(
            200,
            json={"user": {"role": "operator"}, "csrf_token": "csrf"},
            headers={"set-cookie": "ff_session=synthetic; Path=/"},
        )
    if path == "/api/v1/customers":
        return httpx.Response(
            200,
            json=[
                {"id": CUSTOMER, "full_name": "Synthetic customer"},
                {"id": ORDER, "full_name": "Synthetic customer"},
            ],
        )
    if path == "/api/v1/orders/preview":
        return httpx.Response(200, json=PREVIEW)
    if path == "/api/v1/orders":
        return httpx.Response(200, json=RESULT)
    if path == f"/api/v1/orders/{ORDER}":
        return httpx.Response(200, json=DETAIL)
    raise AssertionError(f"Unexpected request: {request.method} {path}")


async def prepare(client, body=None):
    result = await client.call_tool("factoryflow_prepare_order", {"order": body or BODY})
    assert not result.is_error, result.content
    return result.structured_content


def test_preview_does_not_confirm_and_replay_keeps_payload_and_command_key():
    requests = []

    def handler(request):
        requests.append(request)
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            listing = await client.list_tools()
            confirm = next(t for t in listing.tools if t.name == "factoryflow_confirm_order")
            assert confirm.annotations.read_only_hint is False
            assert confirm.annotations.destructive_hint is True
            assert confirm.annotations.idempotent_hint is True
            assert set(confirm.input_schema["properties"]) == {"prepared_id"}
            body = deepcopy(BODY)
            preview = await prepare(client, body)
            body["lines"][0]["quantity"] = "999"
            assert preview["write_performed"] is False
            assert preview["preview"]["order"]["lines"][1]["canonical_quantity"] == "1.125"
            assert not any(r.url.path == "/api/v1/orders" for r in requests)
            args = {"prepared_id": preview["prepared_id"]}
            for _ in range(2):
                result = await client.call_tool("factoryflow_confirm_order", args)
                assert not result.is_error
                value = result.structured_content
                assert value["outcome"] == "confirmed"
                assert value["command_result"]["order_id"] == ORDER
                assert value["readback_status"] == "succeeded"
            writes = [r for r in requests if r.url.path == "/api/v1/orders"]
            assert len(writes) == 2
            for request in writes:
                assert request.method == "POST"
                assert request.headers["Idempotency-Key"] == args["prepared_id"]
                assert request.headers["X-CSRF-Token"] == "csrf"
                assert "ff_session=synthetic" in request.headers["cookie"]
                body = json.loads(request.content)
                assert body["lines"][0]["quantity"] == "3"
                assert body["lines"][0]["source_unit_price"] == "2.50"
                assert body["lines"][1]["source_unit_price"] is None
                assert body["currency"] == "CNY"

    asyncio.run(run())


@pytest.mark.parametrize("role", ["viewer", "admin"])
def test_non_operator_is_rejected_before_preview(role):
    requests = []

    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200, json={"user": {"role": role}, "csrf_token": "secret"})

    async def run():
        async with Client(make_server(handler)) as client:
            result = await client.call_tool("factoryflow_prepare_order", {"order": BODY})
            assert result.is_error
            assert "OPERATOR_REQUIRED" in result.model_dump_json()
            assert requests == ["/api/v1/auth/login"]

    asyncio.run(run())


def test_ambiguous_customers_return_candidates_without_selecting():
    def handler(request):
        if request.url.path == "/api/v1/auth/login":
            assert json.loads(request.content)["username"] == "viewer"
            return httpx.Response(200, json={"user": {"role": "viewer"}})
        assert request.method == "GET" and request.url.path == "/api/v1/customers/search"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": CUSTOMER, "full_name": "Synthetic customer"},
                    {"id": ORDER, "full_name": "Synthetic customer"},
                ],
                "next_cursor": None,
            },
        )

    async def run():
        async with Client(make_server(handler)) as client:
            result = await client.call_tool("factoryflow_find_customers", {"name": "Synthetic"})
            assert not result.is_error
            value = result.structured_content
            assert len(value["items"]) == 2
            assert value["items"][0]["id"] != value["items"][1]["id"]
            assert "selected_customer_id" not in value

    asyncio.run(run())


@pytest.mark.parametrize(
    "change",
    [
        {"currency": "EUR"},
        {"material_choices": []},
        {"lines": [{"item_name": "Synthetic", "quantity": 3, "unit": "PCS"}]},
        {"customer_id": "../../other"},
    ],
)
def test_invalid_or_unsupported_input_is_rejected_before_http(change):
    calls = []

    def handler(request):
        calls.append(request)
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            result = await client.call_tool("factoryflow_prepare_order", {"order": BODY | change})
            assert result.is_error
            assert not calls

    asyncio.run(run())


def test_unknown_or_previous_process_prepared_id_cannot_write():
    async def run():
        async with Client(make_server(upstream)) as first:
            value = await prepare(first)
        calls = []
        async with Client(make_server(lambda request: calls.append(request))) as second:
            result = await second.call_tool(
                "factoryflow_confirm_order", {"prepared_id": value["prepared_id"]}
            )
            assert result.is_error
            assert "PREVIEW_NOT_FOUND" in result.model_dump_json()
            assert not calls

    asyncio.run(run())


@pytest.mark.parametrize("failure", ["timeout", "503", "invalid_success"])
def test_uncertain_write_retains_id_for_same_key_retry(failure):
    writes = []

    def handler(request):
        if request.url.path == "/api/v1/orders":
            writes.append(request)
            if len(writes) == 1:
                if failure == "timeout":
                    raise httpx.ReadTimeout("secret details", request=request)
                if failure == "503":
                    return httpx.Response(503, text="secret details")
                return httpx.Response(200, json={"unexpected": "secret details"})
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            value = await prepare(client)
            args = {"prepared_id": value["prepared_id"]}
            result = await client.call_tool("factoryflow_confirm_order", args)
            assert not result.is_error
            assert result.structured_content["outcome"] == "unknown"
            assert "secret details" not in result.model_dump_json()
            retry = await client.call_tool("factoryflow_confirm_order", args)
            assert retry.structured_content["outcome"] == "confirmed"
            assert writes[0].headers["Idempotency-Key"] == writes[1].headers["Idempotency-Key"]

    asyncio.run(run())


def test_failed_readback_does_not_misreport_successful_commit():
    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(503, text="secret")
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            value = await prepare(client)
            result = await client.call_tool(
                "factoryflow_confirm_order", {"prepared_id": value["prepared_id"]}
            )
            result = result.structured_content
            assert result["outcome"] == "confirmed"
            assert result["command_result"]["order_id"] == ORDER
            assert result["readback_status"] == "failed"
            assert result["order"] is None

    asyncio.run(run())


def test_non_synthetic_write_config_fails_closed():
    with pytest.raises(ValueError, match="SYNTHETIC"):
        make_server(upstream, dataset="unspecified")


@pytest.mark.parametrize(
    "corruption", ["empty", "currency", "quantity", "source_price", "item_name"]
)
def test_incomplete_or_mismatched_preview_cannot_be_approved(corruption):
    preview = deepcopy(PREVIEW)
    if corruption == "empty":
        preview["order"] = {}
    elif corruption == "currency":
        preview["order"]["currency"] = "USD"
    elif corruption == "quantity":
        preview["order"]["lines"][0]["canonical_quantity"] = "999"
    elif corruption == "source_price":
        preview["order"]["lines"][0]["source_unit_price"] = "0"
    else:
        preview["order"]["lines"][0]["item_name"] = "Wrong part"

    def handler(request):
        if request.url.path == "/api/v1/orders/preview":
            return httpx.Response(200, json=preview)
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            result = await client.call_tool("factoryflow_prepare_order", {"order": BODY})
            assert result.is_error
            assert "INVALID_UPSTREAM_RESPONSE" in result.model_dump_json()

    asyncio.run(run())


@pytest.mark.parametrize(
    "corruption",
    [
        "lines",
        "customer_id",
        "currency",
        "revision_id",
        "quantity",
        "numeric_line_id",
        "array_line_id",
    ],
)
def test_mismatched_readback_does_not_claim_verified_order(corruption):
    detail = deepcopy(DETAIL)
    if corruption == "lines":
        detail["lines"] = []
    elif corruption == "quantity":
        detail["lines"][0]["quantity"] = "999"
    elif corruption == "numeric_line_id":
        detail["lines"][0]["id"] = 123
    elif corruption == "array_line_id":
        detail["lines"][0]["id"] = []
    elif corruption == "currency":
        detail["currency"] = "USD"
    else:
        detail[corruption] = "00000000-0000-4000-8000-000000000099"

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    async def run():
        async with Client(make_server(handler)) as client:
            preview = await prepare(client)
            result = await client.call_tool(
                "factoryflow_confirm_order", {"prepared_id": preview["prepared_id"]}
            )
            assert not result.is_error
            value = result.structured_content
            assert value["outcome"] == "confirmed"
            assert value["readback_status"] == "failed"
            assert value["order"] is None

    asyncio.run(run())
