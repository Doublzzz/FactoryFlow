"""Discovery works without write credentials; recovery never sends a business command."""

import asyncio
import json
from copy import deepcopy

import httpx
import pytest
from mcp import Client
from test_order_tools import CUSTOMER, ORDER, RESULT, REVISION
from test_order_tools import DETAIL as WRITE_DETAIL

from factoryflow_mcp.api import Credentials
from factoryflow_mcp.server import create_server

KEY = "00000000-0000-4000-8000-000000000090"
DETAIL = deepcopy(WRITE_DETAIL)
DETAIL["revisions"] = [
    {
        "revision_id": REVISION,
        "sha256": "0" * 64,
        "revision_number": 1,
        "parent_revision_id": None,
        "confirmed_at": "2026-10-27T00:00:00+00:00",
    }
]
MATERIAL = {
    "id": KEY,
    "own_code": "SYN-MAT",
    "name": "Synthetic finished part",
    "specification": None,
    "unit": "PCS",
    "version": 1,
    "active": True,
    "kind": "finished",
}


def server(handler, *, writer=False):
    origin = "http://127.0.0.1:18123"
    return create_server(
        Credentials(origin, "dedicated-viewer", "synthetic-password", "synthetic"),
        transport=httpx.MockTransport(handler),
        order_credentials=(
            Credentials(origin, "dedicated-operator", "synthetic-password", "synthetic")
            if writer
            else None
        ),
    )


def upstream(request):
    if request.url.path == "/api/v1/auth/login":
        assert json.loads(request.content)["username"] == "dedicated-viewer"
        return httpx.Response(200, json={"user": {"role": "viewer"}})
    assert request.method == "GET", "Query/recovery must never send a business command"
    if request.url.path == "/api/v1/customers/search":
        return httpx.Response(
            200,
            json={
                "items": [{"id": CUSTOMER, "full_name": "Synthetic customer"}],
                "next_cursor": None,
            },
        )
    if request.url.path in {"/api/v1/orders/lookup", f"/api/v1/orders/{ORDER}"}:
        return httpx.Response(200, json=DETAIL)
    if request.url.path == f"/api/v1/orders/confirmations/{KEY}":
        return httpx.Response(
            200, json={"idempotency_key": KEY, "outcome": "confirmed", "command_result": RESULT}
        )
    raise AssertionError(f"Unexpected read: {request.method} {request.url.path}")


def call(handler, name, args, *, writer=False):
    async def run():
        async with Client(server(handler, writer=writer)) as client:
            return await client.call_tool(name, args)

    return asyncio.run(run())


@pytest.mark.parametrize("writer", [False, True])
def test_customer_search_uses_viewer_and_preserves_pagination_in_both_modes(writer):
    def handler(request):
        if request.url.path == "/api/v1/customers/search":
            assert request.method == "GET"
            assert dict(request.url.params) == {"name": "Synthetic", "cursor": KEY, "limit": "1"}
            return httpx.Response(
                200,
                json={
                    "items": [{"id": CUSTOMER, "full_name": "Synthetic customer"}],
                    "next_cursor": CUSTOMER,
                },
            )
        return upstream(request)

    result = call(
        handler,
        "factoryflow_find_customers",
        {"name": " Synthetic ", "cursor": KEY, "limit": 1},
        writer=writer,
    )
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["items"] == [{"id": CUSTOMER, "full_name": "Synthetic customer"}]
    assert value["next_cursor"] == CUSTOMER and value["complete"] is False
    assert "selected_customer_id" not in value


@pytest.mark.parametrize(
    "identity", [{"order_id": ORDER}, {"customer_id": CUSTOMER, "order_number": " SYN-WRITE-001 "}]
)
def test_readonly_order_detail_keeps_exact_source_values_and_all_lines(identity):
    def handler(request):
        if request.url.path == "/api/v1/orders/lookup":
            assert dict(request.url.params) == {
                "customer_id": CUSTOMER,
                "order_number": "SYN-WRITE-001",
            }
        return upstream(request)

    result = call(handler, "factoryflow_get_order", identity)
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["dataset"] == "synthetic" and value["read_at"]
    detail = value["order"]
    assert detail["id"] == ORDER and detail["currency"] == "CNY"
    assert len(detail["lines"]) == 2
    assert detail["lines"][0]["source_unit_price"] == "2.50"
    assert detail["lines"][0]["source_amount"] == "7.50"
    assert detail["lines"][1]["quantity"] == "1.125"
    assert detail["lines"][1]["source_amount"] is None


@pytest.mark.parametrize(
    "name,args",
    [
        ("factoryflow_find_customers", {"name": " "}),
        ("factoryflow_find_customers", {"name": "SYN", "limit": True}),
        ("factoryflow_find_customers", {"name": "SYN", "cursor": "bad"}),
        ("factoryflow_get_order", {}),
        ("factoryflow_get_order", {"order_number": "SYN"}),
        ("factoryflow_get_order", {"customer_id": CUSTOMER, "order_number": " "}),
        (
            "factoryflow_get_order",
            {"order_id": ORDER, "customer_id": CUSTOMER, "order_number": "SYN"},
        ),
        ("factoryflow_get_order", {"order_id": "../other"}),
        ("factoryflow_check_order_confirmation", {"prepared_id": "bad"}),
    ],
)
def test_invalid_read_identity_is_rejected_before_authentication(name, args):
    def handler(request):
        pytest.fail("Invalid identity must not reach HTTP")

    assert call(handler, name, args).is_error


def test_recovery_in_fresh_readonly_process_uses_committed_receipt_not_memory():
    requests = []

    def handler(request):
        requests.append(request)
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["outcome"] == "confirmed"
    assert value["prepared_id"] == KEY
    assert value["command_result"]["order_id"] == ORDER
    assert value["readback_status"] == "succeeded"
    assert value["order"]["id"] == ORDER
    assert value["current_state_changed"] is False
    assert [r.method for r in requests] == ["POST", "GET", "GET"]


def test_missing_receipt_stays_unknown_and_never_reads_or_creates_an_order():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path == f"/api/v1/orders/confirmations/{KEY}":
            return httpx.Response(
                200, json={"idempotency_key": KEY, "outcome": "unknown", "command_result": None}
            )
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["outcome"] == "unknown" and value["command_result"] is None
    assert value["readback_status"] == "not_attempted"
    assert value["may_create_new_preview"] is False
    assert calls == ["/api/v1/auth/login", f"/api/v1/orders/confirmations/{KEY}"]


def test_recovery_distinguishes_original_receipt_from_revised_deleted_current_state():
    detail = deepcopy(DETAIL)
    detail.update(version=3, status="deleted", revision_id="00000000-0000-4000-8000-000000000099")
    detail["revisions"].append(
        dict(
            detail["revisions"][0],
            revision_id=detail["revision_id"],
            revision_number=2,
            parent_revision_id=REVISION,
        )
    )

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["outcome"] == "confirmed" and value["command_result"]["version"] == 1
    assert value["command_result"]["status"] == "active"
    assert value["readback_status"] == "succeeded" and value["current_state_changed"] is True
    assert value["order"]["status"] == "deleted" and value["order"]["version"] == 3


@pytest.mark.parametrize("failure", ["503", "wrong_id", "stale_version"])
def test_recovery_readback_failure_does_not_erase_known_confirmation(failure):
    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            if failure == "503":
                return httpx.Response(503, text="private upstream details")
            detail = deepcopy(DETAIL)
            detail["id" if failure == "wrong_id" else "version"] = (
                KEY if failure == "wrong_id" else 0
            )
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert not result.is_error, result.content
    value = result.structured_content
    assert value["outcome"] == "confirmed" and value["readback_status"] == "failed"
    assert value["command_result"]["order_id"] == ORDER and value["order"] is None
    assert "private upstream details" not in result.model_dump_json()


@pytest.mark.parametrize(
    "corruption",
    ["wrong_key", "missing_result", "unknown_with_result", "invalid_result", "invalid_outcome"],
)
def test_malformed_receipt_cannot_claim_confirmation(corruption):
    value = {"idempotency_key": KEY, "outcome": "confirmed", "command_result": deepcopy(RESULT)}
    if corruption == "wrong_key":
        value["idempotency_key"] = CUSTOMER
    elif corruption == "missing_result":
        value["command_result"] = None
    elif corruption == "unknown_with_result":
        value["outcome"] = "unknown"
    elif corruption == "invalid_outcome":
        value["outcome"] = []
    else:
        value["command_result"]["order_id"] = "bad"

    def handler(request):
        if request.url.path == f"/api/v1/orders/confirmations/{KEY}":
            return httpx.Response(200, json=value)
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert result.is_error
    assert "INVALID_UPSTREAM_RESPONSE" in result.model_dump_json()


@pytest.mark.parametrize(
    "identity", [{"order_id": KEY}, {"customer_id": KEY, "order_number": "DIFFERENT"}]
)
def test_detail_must_match_the_requested_identity(identity):
    def handler(request):
        if request.url.path == f"/api/v1/orders/{KEY}":
            return httpx.Response(200, json=DETAIL)
        return upstream(request)

    result = call(handler, "factoryflow_get_order", identity)
    assert result.is_error
    assert "INVALID_UPSTREAM_RESPONSE" in result.model_dump_json()


@pytest.mark.parametrize(
    "field,value", [("quantity", 3), ("remaining_quantity", "NaN"), ("source_unit_price", 2.5)]
)
def test_detail_rejects_lossy_or_nonfinite_decimal_projection(field, value):
    detail = deepcopy(DETAIL)
    detail["lines"][0][field] = value

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_get_order", {"order_id": ORDER})
    assert result.is_error


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_unavailable_recovery_is_an_error_not_a_negative_confirmation(status):
    def handler(request):
        if request.url.path == f"/api/v1/orders/confirmations/{KEY}":
            return httpx.Response(status, text="private-error-body")
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert result.is_error
    assert "private-error-body" not in result.model_dump_json()


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_source_unit",
        "missing_policy_version",
        "missing_policy_warnings",
        "bad_warning",
        "bad_material",
        "mismatched_material",
        "empty_history",
        "missing_current_revision",
        "bad_hash",
        "duplicate_line",
        "duplicate_line_number",
    ],
)
def test_detail_rejects_incomplete_or_malformed_nested_contract(corruption):
    detail = deepcopy(DETAIL)
    line = detail["lines"][0]
    if corruption == "missing_source_unit":
        del line["source_unit"]
    elif corruption == "missing_policy_version":
        del line["quantity_policy"]["version"]
    elif corruption == "missing_policy_warnings":
        del line["quantity_policy"]["warning_codes"]
    elif corruption == "bad_warning":
        line["quantity_policy"]["warning_codes"] = [123]
    elif corruption in {"bad_material", "mismatched_material"}:
        line.update(material_id=KEY, material=deepcopy(MATERIAL))
        line["material"]["version" if corruption == "bad_material" else "id"] = (
            "1" if corruption == "bad_material" else ORDER
        )
    elif corruption == "empty_history":
        detail["revisions"] = []
    elif corruption == "missing_current_revision":
        detail["revisions"][0]["revision_id"] = KEY
    elif corruption == "bad_hash":
        detail["revisions"][0]["sha256"] = "not-a-sha256"
    elif corruption == "duplicate_line":
        detail["lines"][1]["id"] = line["id"]
    else:
        detail["lines"][1]["line_number"] = 1

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_get_order", {"order_id": ORDER})
    assert result.is_error
    assert "INVALID_UPSTREAM_RESPONSE" in result.model_dump_json()


def test_detail_projects_only_known_fields_at_every_nested_level():
    detail = deepcopy(DETAIL)
    detail["lines"][0].update(material_id=KEY, material=deepcopy(MATERIAL))
    for item in [
        detail,
        detail["lines"][0],
        detail["lines"][0]["quantity_policy"],
        detail["lines"][0]["material"],
        detail["revisions"][0],
    ]:
        item["private_future_field"] = "must-not-escape"

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_get_order", {"order_id": ORDER})
    assert not result.is_error, result.content
    value = result.structured_content["order"]
    assert value["lines"][0]["material"] == MATERIAL
    assert value["revisions"][0] == DETAIL["revisions"][0]
    assert "must-not-escape" not in result.model_dump_json()


def test_detail_can_include_a_later_revision_after_current_state_was_read():
    # The owning API uses separate READ COMMITTED queries for current state and history.
    detail = deepcopy(DETAIL)
    detail["revisions"].append(
        dict(
            detail["revisions"][0], revision_id=KEY, revision_number=2, parent_revision_id=REVISION
        )
    )

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_get_order", {"order_id": ORDER})
    assert not result.is_error, result.content
    assert result.structured_content["order"]["revision_id"] == REVISION


@pytest.mark.parametrize("field,value", [("version", 2), ("status", "deleted")])
def test_confirmation_receipt_must_be_the_original_active_version_one(field, value):
    receipt = dict(RESULT, **{field: value})

    def handler(request):
        if request.url.path == f"/api/v1/orders/confirmations/{KEY}":
            return httpx.Response(
                200,
                json={"idempotency_key": KEY, "outcome": "confirmed", "command_result": receipt},
            )
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert result.is_error
    assert "INVALID_UPSTREAM_RESPONSE" in result.model_dump_json()


@pytest.mark.parametrize("field,value", [("revision_id", KEY), ("status", "deleted")])
def test_same_version_cannot_change_revision_or_status_in_confirmation_readback(field, value):
    detail = deepcopy(DETAIL)
    detail[field] = value
    detail["revisions"][0]["revision_id"] = detail["revision_id"]

    def handler(request):
        if request.url.path == f"/api/v1/orders/{ORDER}":
            return httpx.Response(200, json=detail)
        return upstream(request)

    result = call(handler, "factoryflow_check_order_confirmation", {"prepared_id": KEY})
    assert not result.is_error, result.content
    response = result.structured_content
    assert response["outcome"] == "confirmed"
    assert response["readback_status"] == "failed"
    assert response["readback_error"] == "INVALID_UPSTREAM_RESPONSE"
    assert response["command_result"]["version"] == 1 and response["order"] is None


@pytest.mark.parametrize(
    "name,args,path,status,body,code",
    [
        (
            "factoryflow_find_customers",
            {"name": "SYN"},
            "/api/v1/customers/search",
            404,
            {"detail": "Not Found"},
            "QUERY_ENDPOINT_UNAVAILABLE",
        ),
        (
            "factoryflow_check_order_confirmation",
            {"prepared_id": KEY},
            f"/api/v1/orders/confirmations/{KEY}",
            404,
            {"detail": "Not Found"},
            "QUERY_ENDPOINT_UNAVAILABLE",
        ),
        (
            "factoryflow_get_order",
            {"customer_id": CUSTOMER, "order_number": "SYN"},
            "/api/v1/orders/lookup",
            404,
            {"detail": "Not Found"},
            "QUERY_ENDPOINT_UNAVAILABLE",
        ),
        (
            "factoryflow_get_order",
            {"customer_id": CUSTOMER, "order_number": "SYN"},
            "/api/v1/orders/lookup",
            422,
            {"code": "INVALID_INPUT", "field": "path.order_id"},
            "QUERY_ENDPOINT_UNAVAILABLE",
        ),
        (
            "factoryflow_get_order",
            {"customer_id": CUSTOMER, "order_number": "SYN"},
            "/api/v1/orders/lookup",
            404,
            {"code": "ORDER_NOT_FOUND"},
            "ORDER_NOT_FOUND",
        ),
        (
            "factoryflow_get_order",
            {"order_id": ORDER},
            f"/api/v1/orders/{ORDER}",
            404,
            {"code": "ORDER_NOT_FOUND"},
            "ORDER_NOT_FOUND",
        ),
    ],
)
def test_old_query_endpoint_is_distinct_from_a_missing_order(name, args, path, status, body, code):
    def handler(request):
        if request.url.path == path:
            return httpx.Response(status, json={**body, "message": "private-upstream-body"})
        return upstream(request)

    result = call(handler, name, args)
    assert result.is_error
    assert code in result.model_dump_json()
    assert "private-upstream-body" not in result.model_dump_json()
