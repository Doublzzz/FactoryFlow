from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.modules.fulfillment.adapters.layout_http import print_response
from factoryflow.modules.fulfillment.adapters.print_renderer import render_delivery
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import Field

router = APIRouter(tags=["Deliveries"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class DeliveryLineInput(StrictDTO):
    order_line_id: UUID
    quantity: str = Field(min_length=1, max_length=64)


class DeliveryInput(StrictDTO):
    order_id: UUID
    customer_id: UUID
    revision_id: UUID
    expected_version: int = Field(ge=1, strict=True)
    delivery_date: str = Field(min_length=10, max_length=10)
    lines: list[DeliveryLineInput] = Field(min_length=1, max_length=200)


class VoidDeliveryInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class DeliveryPolicy(StrictDTO):
    mode: Literal["INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"]
    canonical_unit: str | None
    warning_codes: list[str]
    version: str


class DeliveryLine(StrictDTO):
    order_line_id: UUID
    line_number: int
    description: str
    quantity: str
    source_unit: str | None
    canonical_unit: str | None
    quantity_policy: DeliveryPolicy


class DeliverySummary(StrictDTO):
    id: UUID
    order_id: UUID
    customer_id: UUID
    revision_id: UUID
    customer_name: str
    order_number: str
    delivery_date: str
    status: Literal["active", "void"]
    version: int
    void_reason: str | None
    created_at: str
    voided_at: str | None


class DeliveryDetail(DeliverySummary):
    lines: list[DeliveryLine]


class DeliveryPage(StrictDTO):
    items: list[DeliverySummary]
    next_cursor: str | None


@router.post("/deliveries", operation_id="createDelivery", response_model=DeliveryDetail)
def create(body: DeliveryInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey):
    return services(request).deliveries.create(actor, idempotency_key, body.model_dump(mode="json"))


@router.get("/deliveries", operation_id="listDeliveries", response_model=DeliveryPage)
def list_deliveries(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    order_id: UUID | None = None,
):
    return services(request).deliveries.list(actor, customer_id, cursor, limit, order_id)


@router.get("/deliveries/{delivery_id}", operation_id="getDelivery", response_model=DeliveryDetail)
def detail(delivery_id: UUID, request: Request, actor: CurrentActor):
    return services(request).deliveries.detail(actor, delivery_id)


@router.post(
    "/deliveries/{delivery_id}/void", operation_id="voidDelivery", response_model=DeliveryDetail
)
def void(
    delivery_id: UUID,
    body: VoidDeliveryInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).deliveries.void(
        actor, idempotency_key, delivery_id, body.expected_version, body.reason
    )


@router.get(
    "/deliveries/{delivery_id}/print", operation_id="printDelivery", response_class=HTMLResponse
)
def print_delivery(
    delivery_id: UUID,
    request: Request,
    actor: CurrentActor,
    locale: Literal["zh-CN", "en"] = "zh-CN",
):
    delivery, config, version = services(request).delivery_layouts.printable(actor, delivery_id)
    if version == 0:
        from factoryflow.modules.fulfillment.adapters.print_renderer import localized_defaults

        config = localized_defaults(locale)
    return print_response(render_delivery(delivery, config, version, locale=locale))
