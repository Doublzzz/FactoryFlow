"""Opt-in synthetic order preview/confirmation over the owning HTTP API."""

import json
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal
from uuid import UUID, uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field

from factoryflow_mcp.api import OrderResult, ReadError

DecimalText = Annotated[str, Field(min_length=1, max_length=64, strict=True)]


class OrderLine(BaseModel):
    model_config = ConfigDict(extra="forbid")
    description: str = Field(default="", max_length=1602)
    item_code: str | None = Field(default=None, max_length=100)
    item_name: str | None = Field(default=None, max_length=500)
    specification: str | None = Field(default=None, max_length=1000)
    quantity: DecimalText
    unit: str | None = Field(default=None, max_length=40)
    source_unit_price: DecimalText | None = None
    source_amount: DecimalText | None = None


class ManualOrder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_id: UUID
    order_number: str = Field(min_length=1, max_length=100)
    business_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency: Literal["CNY", "USD"]
    lines: list[OrderLine] = Field(min_length=1, max_length=200)


def check_order_view(payload, view, *, quantity_field):
    """Verify the displayed API projection describes the frozen manual request.

    Business validation and unit normalization remain owned by FactoryFlow.
    This check binds source text/identity and exact numeric value, without reimplementing policy.
    """
    try:
        if (
            view["order_number"] != payload["order_number"].strip()
            or view["business_date"] != payload["business_date"]
            or view["currency"] != payload["currency"]
            or not isinstance(view["lines"], list)
            or len(view["lines"]) != len(payload["lines"])
        ):
            raise ValueError
        for number, (source, line) in enumerate(zip(payload["lines"], view["lines"]), 1):
            structured = [source.get(k) for k in ("item_code", "item_name", "specification")]
            description = (
                " ".join(v.strip() for v in structured if v and v.strip())
                if any(v is not None for v in structured)
                else source["description"].strip()
            )
            policy = line["quantity_policy"]
            if (
                type(line["line_number"]) is not int
                or line["line_number"] != number
                or line["description"] != description
                or line["source_quantity_text"] != source["quantity"]
                or line["source_unit"] != source["unit"]
                or line["source_unit_price"] != source["source_unit_price"]
                or line["source_amount"] != source["source_amount"]
                or not isinstance(line[quantity_field], str)
                or Decimal(line[quantity_field]) != Decimal(source["quantity"].strip())
                or policy["mode"] not in {"INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"}
                or not isinstance(policy["canonical_unit"], (str, type(None)))
                or not isinstance(policy["warning_codes"], list)
                or not all(isinstance(w, str) for w in policy["warning_codes"])
                or not isinstance(policy["version"], str)
            ):
                raise ValueError
            for field in ("item_code", "item_name", "specification"):
                original = source[field]
                if line.get(field) != (original.strip() if original is not None else None):
                    raise ValueError
    except (KeyError, TypeError, ValueError, InvalidOperation):
        raise ReadError("INVALID_UPSTREAM_RESPONSE") from None


class OrderAPI:
    def __init__(self, credentials, transport=None):
        self.credentials = credentials
        self.client = httpx.Client(
            base_url=credentials.api_url,
            timeout=15,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.client.close()

    def request(self, method, path, *, expected=dict, **kwargs):
        try:
            response = self.client.request(method, path, **kwargs)
        except httpx.HTTPError:
            raise ReadError("UPSTREAM_UNAVAILABLE") from None
        status = response.status_code
        if status != 200:
            if status in {409, 422}:
                # Only known business codes, never arbitrary response text or fields.
                try:
                    code = response.json().get("code")
                except (ValueError, AttributeError):
                    code = None
                if code in {
                    "IDEMPOTENCY_CONFLICT",
                    "ORDER_NUMBER_CONFLICT",
                    "INVALID_INPUT",
                    "CURRENCY_REQUIRED",
                    "LINES_REQUIRED",
                    "SOURCE_DECIMAL_INVALID",
                    "QUANTITY_INVALID",
                    "QUANTITY_PRECISION",
                    "INTEGER_QUANTITY_REQUIRED",
                    "QUANTITY_INVALID_TYPE",
                    "QUANTITY_INVALID_FORMAT",
                    "QUANTITY_OUT_OF_RANGE",
                    "UNIT_INVALID_TYPE",
                    "UNIT_REQUIRES_INTEGER_QUANTITY",
                }:
                    raise ReadError(code)
                raise ReadError("COMMAND_REJECTED")
            if status == 401:
                raise ReadError("AUTHENTICATION_FAILED")
            if status == 403:
                raise ReadError("ACCESS_DENIED")
            if status == 404:
                raise ReadError("NOT_FOUND")
            if 300 <= status < 400:
                raise ReadError("UPSTREAM_REDIRECT")
            raise ReadError("UPSTREAM_UNAVAILABLE")
        try:
            value = response.json()
        except ValueError:
            raise ReadError("INVALID_UPSTREAM_RESPONSE") from None
        if not isinstance(value, expected):
            raise ReadError("INVALID_UPSTREAM_RESPONSE")
        return value

    def login(self):
        value = self.request(
            "POST",
            "/api/v1/auth/login",
            json={
                "username": self.credentials.username,
                "password": self.credentials.password,
            },
        )
        if not isinstance(value.get("user"), dict) or value["user"].get("role") != "operator":
            raise ReadError("OPERATOR_REQUIRED")
        if not isinstance(value.get("csrf_token"), str) or not value["csrf_token"]:
            raise ReadError("INVALID_UPSTREAM_RESPONSE")
        self.client.headers["X-CSRF-Token"] = value["csrf_token"]


class OrderWorkflow:
    def __init__(self, credentials, *, transport=None):
        if credentials.dataset != "synthetic":
            raise ValueError("SYNTHETIC_ORDER_WRITER_REQUIRED")
        self.credentials = credentials
        self.transport = transport
        # Serialized requests cannot be altered by a later caller's mutable dictionary.
        # Process-local previews are not durable business drafts or proof of human approval.
        self.prepared: dict[str, str] = {}

    def prepare(self, order):
        if len(self.prepared) >= 100:
            raise ReadError("PREVIEW_CAPACITY_REACHED")
        payload = order.model_dump(mode="json")
        with OrderAPI(self.credentials, self.transport) as api:
            api.login()
            preview = api.request("POST", "/api/v1/orders/preview", json=payload)
        if (
            preview.get("customer_id") != payload["customer_id"]
            or not isinstance(preview.get("customer_name"), str)
            or not preview["customer_name"].strip()
            or not isinstance(preview.get("order"), dict)
        ):
            raise ReadError("INVALID_UPSTREAM_RESPONSE")
        check_order_view(payload, preview["order"], quantity_field="canonical_quantity")
        prepared_id = str(uuid4())
        self.prepared[prepared_id] = json.dumps(payload, ensure_ascii=False)
        return {
            "dataset": "synthetic",
            "prepared_id": prepared_id,
            "write_performed": False,
            "preview": preview,
            "submitted_order": payload,
            "authorization_required": True,
            "notes": [
                "Show this preview and obtain explicit user approval before confirmation.",
                "This is an in-memory preview, not a saved order. Restart loses it.",
                "Keep prepared_id: factoryflow_check_order_confirmation can read its "
                "committed receipt even after restart.",
                "No material suggestion is applied. Source prices/amounts are not receivables.",
            ],
        }

    def confirm(self, prepared_id):
        key = str(prepared_id)
        payload = self.prepared.get(key)
        if payload is None:
            raise ReadError("PREVIEW_NOT_FOUND_RECHECK_ORDER_BEFORE_REPREPARING")
        payload = json.loads(payload)
        with OrderAPI(self.credentials, self.transport) as api:
            api.login()
            try:
                result = api.request(
                    "POST",
                    "/api/v1/orders",
                    json=payload,
                    headers={"Idempotency-Key": key},
                )
                receipt = OrderResult.model_validate(result)
            except (ValueError, ReadError) as error:
                if isinstance(error, ReadError) and str(error) not in {
                    "UPSTREAM_UNAVAILABLE",
                    "INVALID_UPSTREAM_RESPONSE",
                    "UPSTREAM_REDIRECT",
                }:
                    raise
                return {
                    "dataset": "synthetic",
                    "outcome": "unknown",
                    "prepared_id": key,
                    "notes": [
                        "Do not create a new preview or key. Retry this prepared ID. "
                        "If the process restarted, call factoryflow_check_order_confirmation "
                        "with this ID first."
                    ],
                }
            response = {
                "dataset": "synthetic",
                "outcome": "confirmed",
                "prepared_id": key,
                "command_result": result,
                "readback_status": "failed",
                "order": None,
            }
            try:
                detail = api.request("GET", f"/api/v1/orders/{receipt.order_id}")
                if (
                    detail.get("id") != str(receipt.order_id)
                    or detail.get("revision_id") != str(receipt.revision_id)
                    or detail.get("customer_id") != payload["customer_id"]
                    or not isinstance(detail.get("customer_name"), str)
                    or not detail["customer_name"].strip()
                    or type(detail.get("version")) is not int
                    or detail["version"] < receipt.version
                    or detail.get("status") not in {"active", "deleted"}
                ):
                    raise ReadError("INVALID_UPSTREAM_RESPONSE")
                check_order_view(payload, detail, quantity_field="quantity")
                try:
                    if not all(isinstance(row.get("id"), str) for row in detail["lines"]):
                        raise ValueError
                    ids = [str(UUID(row["id"])) for row in detail["lines"]]
                    if len(set(ids)) != len(ids):
                        raise ValueError
                    for row in detail["lines"]:
                        if row["canonical_unit"] != row["quantity_policy"]["canonical_unit"]:
                            raise ValueError
                        for field in ("delivered_quantity", "remaining_quantity"):
                            if (
                                not isinstance(row[field], str)
                                or not Decimal(row[field]).is_finite()
                            ):
                                raise ValueError
                except (KeyError, TypeError, ValueError, InvalidOperation):
                    raise ReadError("INVALID_UPSTREAM_RESPONSE") from None
                response.update(
                    readback_status="succeeded",
                    order=detail,
                    read_at=datetime.now(timezone.utc).isoformat(),
                )
            except ReadError as error:
                response["readback_error"] = str(error)
            return response
