from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field

router = APIRouter(prefix="/production-orders", tags=["Production"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]


class ProductionInput(StrictDTO):
    order_id: UUID
    revision_id: UUID
    order_line_id: UUID
    expected_order_version: int = Field(ge=1, strict=True)
    planned_quantity: str = Field(min_length=1, max_length=64)
    business_date: str = Field(min_length=10, max_length=10)
    note: str | None = Field(default=None, max_length=500)


class ProductionResponse(StrictDTO):
    id: UUID
    number: str
    order_id: UUID
    source_revision_id: UUID
    order_line_id: UUID
    order_number: str
    source_quantity: str
    material_id: UUID
    own_code: str
    material_name: str
    specification: str | None
    canonical_unit: str
    planned_quantity: str
    completed_quantity: str
    scrap_quantity: str
    remaining_quantity: str
    business_date: str
    note: str | None
    status: Literal["open", "closed"]
    version: int
    created_by: UUID
    created_at: str
    closed_by: UUID | None
    closed_at: str | None
    close_reason: str | None
    source_current: bool


class ProductionPage(StrictDTO):
    items: list[ProductionResponse]
    total: int
    offset: int
    limit: int


class ProductionMaterialInput(StrictDTO):
    quantity: str = Field(min_length=1, max_length=64)
    business_date: str = Field(min_length=10, max_length=10)
    reason: str = Field(min_length=1, max_length=500)


class ProductionIssueInput(ProductionMaterialInput):
    material_id: UUID


class ProductionMovement(StrictDTO):
    entry_id: UUID
    production_order_id: UUID
    material_id: UUID
    quantity: str
    business_date: str
    reason: str


class ProductionIssue(ProductionMovement):
    own_code: str
    material_name: str
    specification: str | None
    canonical_unit: str
    returned_quantity: str
    outstanding_quantity: str


class ProductionIssuePage(StrictDTO):
    items: list[ProductionIssue]
    total: int
    offset: int
    limit: int


class ProductionCompletionInput(StrictDTO):
    quantity: str = Field(min_length=1, max_length=64)
    scrap_quantity: str = Field(default="0", min_length=1, max_length=64)
    business_date: str = Field(min_length=10, max_length=10)
    note: str | None = Field(default=None, max_length=500)


class ProductionTransitionInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class ProductionCompletion(ProductionCompletionInput):
    id: UUID
    production_order_id: UUID
    material_id: UUID
    status: Literal["active", "void"]
    version: int
    created_by: UUID
    created_at: str
    void_by: UUID | None
    void_at: str | None
    void_reason: str | None


class ProductionCompletionPage(StrictDTO):
    items: list[ProductionCompletion]
    total: int
    offset: int
    limit: int


@router.get("", operation_id="listProductionOrders", response_model=ProductionPage)
def list_orders(
    request: Request,
    actor: CurrentActor,
    q: Annotated[str, Query(max_length=200)] = "",
    order_id: UUID | None = None,
    offset: Offset = 0,
    limit: Limit = 50,
):
    return services(request).production.list(actor, q, order_id, offset, limit)


@router.post("", operation_id="createProductionOrder", response_model=ProductionResponse)
def create(
    body: ProductionInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).production.create(actor, idempotency_key, body.model_dump(mode="json"))


@router.get(
    "/{production_id}", operation_id="getProductionOrder", response_model=ProductionResponse
)
def detail(production_id: UUID, request: Request, actor: CurrentActor):
    return services(request).production.get(actor, production_id)


@router.get(
    "/{production_id}/issues",
    operation_id="listProductionIssues",
    response_model=ProductionIssuePage,
)
def issues(
    production_id: UUID,
    request: Request,
    actor: CurrentActor,
    offset: Offset = 0,
    limit: Limit = 50,
):
    return services(request).production.issues(actor, production_id, offset, limit)


@router.post(
    "/{production_id}/issues",
    operation_id="issueProductionMaterial",
    response_model=ProductionMovement,
)
def issue(
    production_id: UUID,
    body: ProductionIssueInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).production.issue(
        actor, idempotency_key, production_id, body.model_dump(mode="json")
    )


@router.post(
    "/{production_id}/issues/{issue_id}/returns",
    operation_id="returnProductionMaterial",
    response_model=ProductionMovement,
)
def return_issue(
    production_id: UUID,
    issue_id: UUID,
    body: ProductionMaterialInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).production.return_issue(
        actor, idempotency_key, production_id, issue_id, body.model_dump(mode="json")
    )


@router.get(
    "/{production_id}/completions",
    operation_id="listProductionCompletions",
    response_model=ProductionCompletionPage,
)
def completions(
    production_id: UUID,
    request: Request,
    actor: CurrentActor,
    offset: Offset = 0,
    limit: Limit = 50,
):
    return services(request).production.completions(actor, production_id, offset, limit)


@router.post(
    "/{production_id}/completions",
    operation_id="completeProduction",
    response_model=ProductionCompletion,
)
def complete(
    production_id: UUID,
    body: ProductionCompletionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).production.complete(
        actor, idempotency_key, production_id, body.model_dump(mode="json")
    )


@router.post(
    "/{production_id}/completions/{completion_id}/void",
    operation_id="voidProductionCompletion",
    response_model=ProductionCompletion,
)
def void(
    production_id: UUID,
    completion_id: UUID,
    body: ProductionTransitionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).production.void(
        actor, idempotency_key, production_id, completion_id, body.model_dump(mode="json")
    )


@router.post(
    "/{production_id}/close", operation_id="closeProductionOrder", response_model=ProductionResponse
)
def close(
    production_id: UUID,
    body: ProductionTransitionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).production.close(
        actor, idempotency_key, production_id, body.model_dump(mode="json")
    )
