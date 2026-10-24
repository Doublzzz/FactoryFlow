from typing import Annotated, Any, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import Field

router = APIRouter(tags=["Statements"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]
TaxMode = Literal["included", "untaxed_final", "add_tax"]


class StatementLineInput(StrictDTO):
    external_document_number: str = Field(default="", max_length=120)
    delivery_id: UUID
    order_line_id: UUID
    quantity: str = Field(min_length=1, max_length=64)
    unit_price: str | None = Field(default=None, max_length=64)
    reason: str = Field(default="", max_length=500)


class AdjustmentInput(StrictDTO):
    stage: Literal["before_tax", "after_tax"]
    kind: str = Field(min_length=1, max_length=80)
    amount: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)
    delivery_id: UUID | None = None
    order_line_id: UUID | None = None


class DraftInput(StrictDTO):
    customer_id: UUID
    period_start: str = Field(min_length=10, max_length=10)
    period_end: str = Field(min_length=10, max_length=10)
    tax_mode: TaxMode
    tax_rate: str = Field(min_length=1, max_length=64)
    lines: list[StatementLineInput] = Field(default_factory=list, max_length=200)
    adjustments: list[AdjustmentInput] = Field(default_factory=list, max_length=100)
    reason: str = Field(default="", max_length=500)


class SaveDraftInput(DraftInput):
    expected_version: int = Field(ge=1, strict=True)


class AbandonDraftInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class StatementCalculation(StrictDTO):
    line_amounts: list[str | None]
    priced_subtotal: str
    tax_base: str | None
    tax_amount: str | None
    total: str | None
    warnings: list[str]


class StatementUnitPolicy(StrictDTO):
    mode: Literal["INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"]
    canonical_unit: str | None
    warning_codes: list[str]
    version: str


class StatementSource(StrictDTO):
    delivery_id: UUID
    order_line_id: UUID
    order_id: UUID
    revision_id: UUID
    customer_id: UUID
    delivery_date: str
    order_number: str | None = None
    line_number: int
    description: str
    item_code: str | None
    item_name: str | None
    specification: str | None
    quantity: str
    source_unit: str | None
    canonical_unit: str | None
    quantity_policy: StatementUnitPolicy
    source_unit_price: str | None
    source_amount: str | None
    currency: Literal["CNY"]


class StatementCandidate(StatementSource):
    available_quantity: str
    cross_period: bool


class StatementLine(StatementLineInput):
    status: Literal["included", "deferred", "source_void", "released"]
    source: StatementSource


class StatementAdjustment(AdjustmentInput):
    status: Literal["active", "needs_review"]


class SettlementLine(StatementLine):
    allocation_id: UUID
    approval_id: UUID
    allocation_status: Literal["reserved", "settled"]
    approval_version: int


class StatementEvent(StrictDTO):
    version: int
    action: str
    reason: str
    snapshot: dict[str, Any]


class StatementCorrection(StrictDTO):
    evidence_id: UUID
    cause: Literal["entry_error", "customer_change"]
    disposition: Literal["review", "pending"]
    previous_quantity: str
    quantity: str
    previous_unit_price: str
    unit_price: str
    reason: str
    actor_id: UUID
    recorded_at: str
    no_downstream_effects: bool


class StatementApprovalRef(StrictDTO):
    approval_id: UUID
    version: int
    sent_id: UUID
    feedback_id: UUID


class StatementDetail(StrictDTO):
    id: UUID
    customer_id: UUID
    customer_name: str
    period_start: str
    period_end: str
    status: Literal["draft", "abandoned", "void", "confirmed"]
    version: int
    tax_mode: TaxMode
    tax_rate: str
    lines: list[StatementLine]
    settlement_lines: list[SettlementLine]
    fees_confirmed: bool
    reconfirmation: Literal["unknown", "not_required", "received"]
    adjustments: list[StatementAdjustment]
    calculation: StatementCalculation
    history: list[StatementEvent]
    correction: StatementCorrection | None = None
    approval_refs: list[StatementApprovalRef] = Field(default_factory=list)
    confirmation_evidence_ids: list[UUID] = Field(default_factory=list)


class StatementPage(StrictDTO):
    items: list[StatementDetail]
    next_cursor: str | None


class StatementCandidatePage(StrictDTO):
    items: list[StatementCandidate]
    next_cursor: str | None
    overlapping_statements: list[UUID]


class StatementSettingsInput(StrictDTO):
    template_id: Literal["standard-v1", "delivery-v1", "customer-v1"] = "standard-v1"
    customer_template_id: UUID | None = None
    expected_version: int = Field(ge=0, strict=True)
    cycle_day: int | None = Field(default=None, ge=1, le=31, strict=True)
    tax_mode: TaxMode
    tax_rate: str = Field(min_length=1, max_length=64)
    reason: str = Field(min_length=1, max_length=500)


class StatementSettingsDetail(StrictDTO):
    template_id: Literal["standard-v1", "delivery-v1", "customer-v1"]
    customer_template_id: UUID | None = None
    version: int
    cycle_day: int | None
    tax_mode: TaxMode
    tax_rate: str


@router.get(
    "/customers/{customer_id}/statement-settings",
    operation_id="getStatementSettings",
    response_model=StatementSettingsDetail | None,
)
def get_settings(customer_id: UUID, request: Request, actor: CurrentActor):
    return services(request).statements.settings.get(actor, customer_id)


@router.post(
    "/customers/{customer_id}/statement-settings",
    operation_id="saveStatementSettings",
    response_model=StatementSettingsDetail,
)
def save_settings(
    customer_id: UUID,
    body: StatementSettingsInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statements.settings.save(
        actor, idempotency_key, customer_id, body.expected_version, body.model_dump()
    )


@router.get(
    "/statement-candidates",
    operation_id="getStatementCandidates",
    response_model=StatementCandidatePage,
)
def candidates(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID,
    period_start: str,
    period_end: str,
    statement_id: UUID | None = None,
    cursor: Annotated[str | None, Query(max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statements.candidates(
        actor, customer_id, period_start, period_end, cursor, limit, statement_id
    )


@router.post("/statements", operation_id="createStatementDraft", response_model=StatementDetail)
def create(body: DraftInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey):
    return services(request).statements.create(
        actor, idempotency_key, body.model_dump(mode="json", exclude_unset=True)
    )


@router.get("/statements", operation_id="listStatementDrafts", response_model=StatementPage)
def listing(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statements.list(actor, customer_id, cursor, limit)


@router.get(
    "/statements/{statement_id}", operation_id="getStatementDraft", response_model=StatementDetail
)
def detail(statement_id: UUID, request: Request, actor: CurrentActor):
    return services(request).statements.detail(actor, statement_id)


@router.post(
    "/statements/{statement_id}/save",
    operation_id="saveStatementDraft",
    response_model=StatementDetail,
)
def save(
    statement_id: UUID,
    body: SaveDraftInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statements.save(
        actor,
        idempotency_key,
        statement_id,
        body.expected_version,
        body.model_dump(mode="json", exclude_unset=True),
    )


@router.post(
    "/statements/{statement_id}/reopen",
    operation_id="reopenStatementDraft",
    response_model=StatementDetail,
)
def reopen(
    statement_id: UUID,
    body: SaveDraftInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statements.save(
        actor,
        idempotency_key,
        statement_id,
        body.expected_version,
        body.model_dump(mode="json", exclude_unset=True),
        reopen=True,
    )


@router.post(
    "/statements/{statement_id}/abandon",
    operation_id="abandonStatementDraft",
    response_model=StatementDetail,
)
def abandon(
    statement_id: UUID,
    body: AbandonDraftInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statements.abandon(
        actor, idempotency_key, statement_id, body.expected_version, body.reason
    )


@router.post(
    "/statements/{statement_id}/void",
    operation_id="voidStatementDraft",
    response_model=StatementDetail,
)
def void_statement(
    statement_id: UUID,
    body: AbandonDraftInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statements.abandon(
        actor, idempotency_key, statement_id, body.expected_version, body.reason, exported=True
    )


class StatementExportInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    template_id: Literal["standard-v1", "delivery-v1", "customer-v1"] | None = None
    customer_template_id: UUID | None = None
    locale: Literal["zh-CN", "en"] = "zh-CN"


class StatementExportDetail(StrictDTO):
    id: UUID
    statement_id: UUID
    statement_version: int
    statement_status: Literal["draft", "confirmed"] = "draft"
    template_id: str
    template_version: int
    customer_template_id: UUID | None = None
    template_name: str
    locale: Literal["zh-CN", "en", "source"] = "zh-CN"
    status: Literal["pending", "failed", "ready"]
    current: bool
    file_hash: str | None
    error_code: str | None
    created_at: str


class StatementExportPage(StrictDTO):
    items: list[StatementExportDetail]
    next_cursor: str | None


@router.post(
    "/statements/{statement_id}/exports",
    operation_id="createStatementExport",
    response_model=StatementExportDetail,
)
def create_export(
    statement_id: UUID,
    body: StatementExportInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_exports.create(
        actor,
        idempotency_key,
        statement_id,
        body.expected_version,
        body.template_id,
        body.customer_template_id,
        body.locale,
    )


@router.get(
    "/statements/{statement_id}/exports",
    operation_id="listStatementExports",
    response_model=StatementExportPage,
)
def list_exports(
    statement_id: UUID,
    request: Request,
    actor: CurrentActor,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statement_exports.listing(actor, statement_id, cursor, limit)


@router.post(
    "/statement-exports/{export_id}/generate",
    operation_id="generateStatementExport",
    response_model=StatementExportDetail,
)
def generate_export(export_id: UUID, request: Request, actor: CurrentActor):
    return services(request).statement_exports.generate(actor, export_id)


@router.get(
    "/statement-exports/{export_id}/file",
    operation_id="downloadStatementExport",
    response_class=Response,
    responses={
        200: {
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {"type": "string", "format": "binary"}
                }
            }
        }
    },
)
def download_export(
    export_id: UUID, request: Request, actor: CurrentActor, historical: bool = False
):
    content, record = services(request).statement_exports.download(actor, export_id, historical)
    suffix = record.get("statement_status", "draft") if record["current"] else "historical-invalid"
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="statement-v{record["statement_version"]}'
                f'-{export_id}-{suffix}.xlsx"'
            ),
            "Cache-Control": "no-store",
        },
    )
