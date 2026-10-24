from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.modules.fulfillment.adapters.print_renderer import (
    localized_defaults,
    render_delivery,
)
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import HTMLResponse
from pydantic import Field

router = APIRouter(tags=["Delivery layouts"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class DeliveryLayoutColumn(StrictDTO):
    key: Literal["index", "order_number", "item_code", "specification", "unit", "quantity", "note"]
    label: str = Field(min_length=1, max_length=30)
    width_mm: int = Field(ge=6, le=200, strict=True)


class DeliveryLayoutConfig(StrictDTO):
    company_name: str = Field(max_length=100)
    address: str = Field(max_length=240)
    phone: str = Field(max_length=60)
    fax: str = Field(max_length=60)
    postcode: str = Field(max_length=20)
    delivery_person: str = Field(max_length=60)
    title: str = Field(min_length=1, max_length=40)
    footer_note: str = Field(max_length=300)
    signatures: list[Annotated[str, Field(max_length=40)]] = Field(min_length=4, max_length=4)
    paper_width_mm: int = Field(ge=100, le=420, strict=True)
    paper_height_mm: int = Field(ge=100, le=420, strict=True)
    margin_top_mm: int = Field(ge=0, le=40, strict=True)
    margin_bottom_mm: int = Field(ge=0, le=40, strict=True)
    margin_left_mm: int = Field(ge=0, le=40, strict=True)
    margin_right_mm: int = Field(ge=0, le=40, strict=True)
    font_size_pt: int = Field(ge=8, le=16, strict=True)
    title_size_pt: int = Field(ge=12, le=26, strict=True)
    row_height_mm: int = Field(ge=6, le=18, strict=True)
    rows_per_page: int = Field(ge=1, le=30, strict=True)
    columns: list[DeliveryLayoutColumn] = Field(min_length=7, max_length=7)


class DeliveryLayoutDetail(StrictDTO):
    version: int
    config: DeliveryLayoutConfig
    defaults: DeliveryLayoutConfig
    updated_at: str | None


class SaveDeliveryLayout(StrictDTO):
    expected_version: int = Field(ge=0, strict=True)
    config: DeliveryLayoutConfig


class PreviewDeliveryLayout(StrictDTO):
    delivery_id: UUID
    config: DeliveryLayoutConfig
    locale: Literal["zh-CN", "en"] = "zh-CN"


@router.get(
    "/delivery-layout", operation_id="getDeliveryLayout", response_model=DeliveryLayoutDetail
)
def get_layout(request: Request, actor: CurrentActor, locale: Literal["zh-CN", "en"] = "zh-CN"):
    result = services(request).delivery_layouts.get(actor)
    defaults = localized_defaults(locale)
    return {
        **result,
        "defaults": defaults,
        "config": defaults if result["version"] == 0 else result["config"],
    }


@router.post(
    "/delivery-layout", operation_id="saveDeliveryLayout", response_model=DeliveryLayoutDetail
)
def save_layout(
    body: SaveDeliveryLayout, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).delivery_layouts.save(
        actor, idempotency_key, body.expected_version, body.config.model_dump()
    )


def print_response(content):
    # Script/style restrictions are in the renderer's meta CSP (unique script nonce).
    return HTMLResponse(content, headers={"Content-Security-Policy": "frame-ancestors 'self'"})


@router.post(
    "/delivery-layout/preview", operation_id="previewDeliveryLayout", response_class=HTMLResponse
)
def preview_layout(body: PreviewDeliveryLayout, request: Request, actor: CurrentActor):
    delivery, config, version = services(request).delivery_layouts.printable(
        actor, body.delivery_id, body.config.model_dump()
    )
    return print_response(
        render_delivery(delivery, config, version, preview=True, locale=body.locale)
    )
