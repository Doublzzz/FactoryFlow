from typing import Annotated, Literal
from uuid import UUID

from factoryflow.modules.inventory.adapters.http import (
    CommandKey,
    CurrentActor,
    InventoryAccount,
    InventoryCountInput,
    InventoryEntry,
    InventoryItem,
    InventoryPage,
    InventoryQuantityInput,
)
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, services
from fastapi import APIRouter, Query, Request
from pydantic import Field

router = APIRouter(tags=["Raw inventory"], responses=ERROR_RESPONSES)


class RawInventoryEntry(InventoryEntry):
    kind: Literal[
        "opening",
        "count",
        "purchase_receipt",
        "purchase_receipt_void",
        "material_issue",
        "material_return",
    ]
    purchase_receipt_line_id: UUID | None = None
    purchase_receipt_id: UUID | None = None
    purchase_receipt_number: str | None = None
    returns_issue_id: UUID | None = None
    returns_issue_version: int | None = None
    returned_quantity: str | None = None


class RawInventoryDetail(InventoryItem):
    entries: list[RawInventoryEntry]
    next_cursor: str | None


class RawInventoryMutation(StrictDTO):
    account: InventoryAccount
    entry: RawInventoryEntry


class RawIssueInput(InventoryQuantityInput):
    reason: str = Field(min_length=1, max_length=500)


@router.get("/raw-inventory", operation_id="listRawInventory", response_model=InventoryPage)
def list_raw_inventory(
    request: Request,
    actor: CurrentActor,
    cursor: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).raw_inventory.list(actor, cursor, limit)


@router.post(
    "/raw-inventory/entries/{issue_id}/returns",
    operation_id="returnRawInventory",
    response_model=RawInventoryMutation,
)
def return_issue(
    issue_id: UUID,
    body: RawIssueInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).raw_inventory.return_issue(
        actor, idempotency_key, issue_id, body.model_dump(mode="json")
    )


@router.get(
    "/raw-inventory/{material_id}",
    operation_id="getRawInventory",
    response_model=RawInventoryDetail,
)
def get_raw_inventory(
    material_id: UUID,
    request: Request,
    actor: CurrentActor,
    cursor: Annotated[str | None, Query(max_length=40)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).raw_inventory.detail(actor, material_id, cursor, limit)


@router.post(
    "/raw-inventory/{material_id}/open",
    operation_id="openRawInventory",
    response_model=RawInventoryMutation,
)
def open_raw_inventory(
    material_id: UUID,
    body: InventoryQuantityInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).raw_inventory.record(
        actor, idempotency_key, material_id, "opening", body.model_dump(mode="json")
    )


@router.post(
    "/raw-inventory/{material_id}/counts",
    operation_id="countRawInventory",
    response_model=RawInventoryMutation,
)
def count_raw_inventory(
    material_id: UUID,
    body: InventoryCountInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).raw_inventory.record(
        actor, idempotency_key, material_id, "count", body.model_dump(mode="json")
    )


@router.post(
    "/raw-inventory/{material_id}/issues",
    operation_id="issueRawInventory",
    response_model=RawInventoryMutation,
)
def issue_raw_inventory(
    material_id: UUID,
    body: RawIssueInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).raw_inventory.issue(
        actor, idempotency_key, material_id, body.model_dump(mode="json")
    )
