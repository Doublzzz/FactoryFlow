import json
from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import Field

router = APIRouter(tags=["Orders"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class OrderLineInput(StrictDTO):
    description: str = Field(default="", max_length=1602)
    item_code: str | None = Field(default=None, max_length=100)
    item_name: str | None = Field(default=None, max_length=500)
    specification: str | None = Field(default=None, max_length=1000)
    quantity: str = Field(min_length=1, max_length=64)
    unit: str | None = Field(default=None, max_length=40)
    source_unit_price: str | None = Field(default=None, max_length=64)
    source_amount: str | None = Field(default=None, max_length=64)


class MaterialMappingChoice(StrictDTO):
    customer_id: UUID
    customer_code: str = Field(min_length=1, max_length=100)
    expected_mapping_version: int = Field(ge=1, strict=True)


class OrderMaterialChoice(StrictDTO):
    line_number: int = Field(ge=1, le=200, strict=True)
    material_id: UUID
    expected_material_version: int = Field(ge=1, strict=True)
    mapping: MaterialMappingChoice | None = None


class OrderInput(StrictDTO):
    extraction_id: UUID | None = None
    customer_id: UUID
    order_number: str = Field(min_length=1, max_length=100)
    business_date: str = Field(min_length=10, max_length=10)
    currency: Literal["CNY", "USD"]
    lines: list[OrderLineInput] = Field(min_length=1, max_length=200)
    material_choices: list[OrderMaterialChoice] = Field(default_factory=list, max_length=200)


class RevisionInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)
    order: OrderInput


class StatusInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class QuantityPolicy(StrictDTO):
    mode: Literal["INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"]
    canonical_unit: str | None
    warning_codes: list[str]
    version: str


class OrderMaterialSummary(StrictDTO):
    id: UUID
    own_code: str
    name: str
    specification: str | None
    unit: str | None
    version: int
    active: bool


class OrderLineResponse(StrictDTO):
    id: UUID
    line_number: int
    description: str
    item_code: str | None = None
    item_name: str | None = None
    specification: str | None = None
    quantity: str
    delivered_quantity: str
    remaining_quantity: str
    source_quantity_text: str
    source_unit: str | None
    canonical_unit: str | None
    quantity_policy: QuantityPolicy
    source_unit_price: str | None
    source_amount: str | None
    material_id: UUID | None = None
    material: OrderMaterialSummary | None = None


class OpenLine(OrderLineResponse):
    order_id: UUID
    order_number: str
    business_date: str
    customer_id: UUID
    customer_name: str
    version: int


class OpenLinesResponse(StrictDTO):
    items: list[OpenLine]
    next_cursor: str | None


class RevisionSummary(StrictDTO):
    revision_id: UUID
    sha256: str
    revision_number: int
    parent_revision_id: UUID | None
    confirmed_at: str


class OrderDetail(StrictDTO):
    id: UUID
    customer_id: UUID
    customer_name: str
    order_number: str
    business_date: str
    currency: str
    revision_id: UUID
    status: Literal["active", "deleted"]
    version: int
    lines: list[OrderLineResponse]
    revisions: list[RevisionSummary]


class OrderResult(StrictDTO):
    order_id: UUID
    version: int
    status: Literal["active", "deleted"]
    revision_id: UUID
    sha256: str | None = None
    revision_number: int | None = None
    material_links: list[dict] = Field(default_factory=list)


class OrderNewMaterial(StrictDTO):
    own_code: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    specification: str | None = Field(default=None, max_length=1000)
    unit: str | None = Field(default=None, max_length=40)


class OrderMaterialLink(StrictDTO):
    line_id: UUID
    material_id: UUID | None = None
    expected_material_version: int | None = Field(default=None, ge=1, strict=True)
    new_material: OrderNewMaterial | None = None
    remember_code: bool = Field(default=False, strict=True)
    customer_code: str | None = Field(default=None, max_length=100)
    expected_mapping_version: int = Field(default=0, ge=0, strict=True)


class OrderMaterialLinksInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str | None = Field(default=None, max_length=500)
    lines: list[OrderMaterialLink] = Field(min_length=1, max_length=200)


class OrderMaterialLinksResult(OrderResult):
    changes: list[dict]


class EvidenceLine(StrictDTO):
    line_number: int
    description: str
    item_code: str | None = None
    item_name: str | None = None
    specification: str | None = None
    source_quantity_text: str
    canonical_quantity: str
    source_unit: str | None
    quantity_policy: QuantityPolicy
    source_unit_price: str | None
    source_amount: str | None


class EvidenceOrder(StrictDTO):
    order_number: str
    business_date: str
    currency: str
    lines: list[EvidenceLine]


class OrderMaterialSuggestion(StrictDTO):
    line_number: int
    material: OrderMaterialSummary
    automatic: bool
    mapping: MaterialMappingChoice


class OrderPreview(StrictDTO):
    customer_id: UUID
    customer_name: str
    order: EvidenceOrder
    material_suggestions: list[OrderMaterialSuggestion] = Field(default_factory=list)


class EvidenceSource(StrictDTO):
    source_id: UUID
    extraction_id: UUID
    original_sha256: str
    source_hash: str
    trace_hash: str


class EvidenceContent(StrictDTO):
    source: EvidenceSource | None = None
    schema_version: int
    revision_id: UUID
    organization_id: UUID
    customer_id: UUID
    order_id: UUID
    parent_revision_id: UUID | None
    revision_number: int
    actor_id: UUID
    confirmed_at: str
    order: EvidenceOrder


class EvidenceResponse(StrictDTO):
    revision_id: UUID
    sha256: str
    content: EvidenceContent


@router.get("/orders/open-lines", operation_id="listOpenLines", response_model=OpenLinesResponse)
def open_lines(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    status: Literal["active", "deleted"] = "active",
):
    return services(request).orders.open_lines(actor, customer_id, cursor, limit, status)


@router.post("/orders", operation_id="confirmOrder", response_model=OrderResult)
def confirm_order(
    body: OrderInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).orders.confirm(actor, idempotency_key, body.model_dump(mode="json"))


@router.post("/orders/preview", operation_id="previewOrder", response_model=OrderPreview)
def preview_order(body: OrderInput, request: Request, actor: CurrentActor):
    return services(request).orders.preview(actor, body.model_dump(mode="json"))


@router.get("/orders/{order_id}", operation_id="getOrder", response_model=OrderDetail)
def get_order(order_id: UUID, request: Request, actor: CurrentActor):
    return services(request).orders.detail(actor, order_id)


@router.post("/orders/{order_id}/revisions", operation_id="reviseOrder", response_model=OrderResult)
def revise_order(
    order_id: UUID,
    body: RevisionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).orders.revise(
        actor,
        idempotency_key,
        order_id,
        body.expected_version,
        body.order.model_dump(mode="json"),
        body.reason,
    )


@router.post(
    "/orders/{order_id}/material-links",
    operation_id="linkOrderMaterials",
    response_model=OrderMaterialLinksResult,
)
def link_order_materials(
    order_id: UUID,
    body: OrderMaterialLinksInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).orders.material_links(
        actor, idempotency_key, order_id, body.model_dump(mode="json")
    )


@router.post("/orders/{order_id}/delete", operation_id="deleteOrder", response_model=OrderResult)
def delete_order(
    order_id: UUID,
    body: StatusInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).orders.change_status(
        actor, idempotency_key, order_id, body.expected_version, "deleted", body.reason
    )


@router.post("/orders/{order_id}/restore", operation_id="restoreOrder", response_model=OrderResult)
def restore_order(
    order_id: UUID,
    body: StatusInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).orders.change_status(
        actor, idempotency_key, order_id, body.expected_version, "active", body.reason
    )


@router.get(
    "/documents/{revision_id}",
    operation_id="getEvidence",
    response_model=EvidenceResponse,
    response_model_exclude_unset=True,
)
def get_evidence(revision_id: UUID, request: Request, actor: CurrentActor):
    return services(request).orders.evidence(actor, revision_id)


@router.get("/documents/{revision_id}/download", operation_id="downloadEvidence")
def download_evidence(revision_id: UUID, request: Request, actor: CurrentActor):
    evidence = services(request).orders.evidence(actor, revision_id)
    data = (
        json.dumps(evidence["content"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return Response(
        data,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="confirmed-{revision_id}.json"',
            "ETag": f'"{evidence["sha256"]}"',
        },
    )
