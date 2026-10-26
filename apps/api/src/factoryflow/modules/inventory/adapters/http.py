from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field

router = APIRouter(tags=["Inventory"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class InventoryMaterial(StrictDTO):
    id: UUID
    own_code: str
    name: str
    specification: str | None
    unit: str | None
    active: bool
    version: int


class InventoryAccount(StrictDTO):
    material_id: UUID
    canonical_unit: str
    balance: str
    version: int
    has_skipped: bool
    negative_balance: bool
    needs_review: bool


class InventoryEntry(StrictDTO):
    id: UUID
    material_id: UUID
    kind: Literal[
        "opening", "receipt", "count", "delivery", "skip", "delivery_void", "receipt_void"
    ]
    delta: str
    balance_after: str
    account_version: int
    business_date: str
    recorded_at: str
    reason: str | None
    delivery_id: UUID | None
    order_line_id: UUID | None
    reverses_id: UUID | None
    reversed_by: UUID | None
    shortage_confirmed: bool
    target_quantity: str | None


class InventoryItem(StrictDTO):
    material: InventoryMaterial
    account: InventoryAccount | None


class InventoryDetail(InventoryItem):
    entries: list[InventoryEntry]
    next_cursor: str | None


class InventoryPage(StrictDTO):
    items: list[InventoryItem]
    next_cursor: str | None


class InventoryPreviewInput(StrictDTO):
    material_ids: list[UUID] = Field(min_length=1, max_length=200)


class InventoryPosition(StrictDTO):
    material_id: UUID
    account: InventoryAccount | None


class InventoryPreview(StrictDTO):
    items: list[InventoryPosition]


class InventoryQuantityInput(StrictDTO):
    quantity: str = Field(min_length=1, max_length=64)
    business_date: str = Field(min_length=10, max_length=10)
    reason: str | None = Field(default=None, max_length=500)


class InventoryCountInput(InventoryQuantityInput):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class InventoryVoidInput(StrictDTO):
    reason: str = Field(min_length=1, max_length=500)


class InventoryMutation(StrictDTO):
    account: InventoryAccount
    entry: InventoryEntry


@router.get("/inventory", operation_id="listInventory", response_model=InventoryPage)
def inventory_list(
    request: Request,
    actor: CurrentActor,
    cursor: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).inventory.list(actor, cursor, limit)


@router.post("/inventory/preview", operation_id="previewInventory", response_model=InventoryPreview)
def preview(body: InventoryPreviewInput, request: Request, actor: CurrentActor):
    return services(request).inventory.preview(actor, body.material_ids)


@router.post(
    "/inventory/entries/{entry_id}/void",
    operation_id="voidInventoryReceipt",
    response_model=InventoryMutation,
)
def void_receipt(
    entry_id: UUID,
    body: InventoryVoidInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).inventory.void_receipt(actor, idempotency_key, entry_id, body.reason)


@router.get("/inventory/{material_id}", operation_id="getInventory", response_model=InventoryDetail)
def detail(
    material_id: UUID,
    request: Request,
    actor: CurrentActor,
    cursor: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).inventory.detail(actor, material_id, cursor, limit)


@router.post(
    "/inventory/{material_id}/open", operation_id="openInventory", response_model=InventoryMutation
)
def opening(
    material_id: UUID,
    body: InventoryQuantityInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).inventory.record(
        actor, idempotency_key, material_id, "opening", body.model_dump(mode="json")
    )


@router.post(
    "/inventory/{material_id}/receipts",
    operation_id="receiveInventory",
    response_model=InventoryMutation,
)
def receipt(
    material_id: UUID,
    body: InventoryQuantityInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).inventory.record(
        actor, idempotency_key, material_id, "receipt", body.model_dump(mode="json")
    )


@router.post(
    "/inventory/{material_id}/counts",
    operation_id="countInventory",
    response_model=InventoryMutation,
)
def count(
    material_id: UUID,
    body: InventoryCountInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).inventory.record(
        actor, idempotency_key, material_id, "count", body.model_dump(mode="json")
    )
