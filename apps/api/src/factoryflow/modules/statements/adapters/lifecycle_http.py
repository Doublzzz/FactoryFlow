"""Transport contracts for the existing statement lifecycle."""

from typing import Annotated, Any, Literal
from uuid import UUID

from factoryflow.modules.statements.adapters.http import (
    CommandKey,
    CurrentActor,
    StatementCalculation,
    StatementCorrection,
    StatementDetail,
    StatementSource,
)
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, services
from fastapi import APIRouter, Query, Request, Response
from pydantic import Field

router = APIRouter(tags=["Statement lifecycle"], responses=ERROR_RESPONSES)


class EvidenceInput(StrictDTO):
    person: str = Field(min_length=1, max_length=500)
    occurred_on: str = Field(min_length=10, max_length=10)
    note: str = Field(default="", max_length=500)


class SentInput(EvidenceInput):
    expected_version: int = Field(ge=1, strict=True)
    export_id: UUID


class FeedbackInput(EvidenceInput):
    filename: str | None = Field(default=None, max_length=180)
    media_type: Literal["application/pdf", "image/png", "image/jpeg"] | None = None
    content_base64: str | None = Field(default=None, max_length=13981016)


class LifecycleEntity(StrictDTO):
    id: UUID
    customer_id: UUID
    statement_id: UUID
    actor_id: UUID
    created_at: str


class StatementEvidence(LifecycleEntity):
    kind: Literal["sent", "feedback"]
    export_id: UUID | None
    statement_version: int
    person: str
    occurred_on: str
    note: str
    object_hash: str | None
    media_type: str | None
    filename: str | None


class LifecycleSource(LifecycleEntity):
    external_document_number: str = Field(default="", max_length=120)
    delivery_id: UUID
    order_line_id: UUID
    quantity: str
    version: int
    reason: str
    source: StatementSource


class StatementApproval(LifecycleSource):
    sent_id: UUID
    feedback_id: UUID
    unit_price: str
    target_start: str
    target_end: str
    reserved_quantity: str
    settled_quantity: str
    available_quantity: str
    correction: StatementCorrection | None = None
    review_quantity: str


class StatementReview(LifecycleSource):
    remaining_quantity: str


class StatementAllocation(LifecycleEntity):
    approval_id: UUID
    quantity: str
    unit_price: str
    status: Literal["reserved", "settled", "released", "superseded"]
    version: int
    settlement_version: int | None
    superseded_version: int | None
    reason: str


class ReviewTransfer(LifecycleEntity):
    review_id: UUID
    approval_id: UUID | None
    quantity: str
    status: Literal["claimed", "approved", "released"]
    version: int
    reason: str


class LifecycleHistory(StrictDTO):
    kind: str
    entity_id: UUID
    version: int
    snapshot: dict[str, Any]
    created_at: str


class StatementLifecycleView(StrictDTO):
    evidence: list[StatementEvidence]
    approvals: list[StatementApproval]
    allocations: list[StatementAllocation]
    reviews: list[StatementReview]
    review_transfers: list[ReviewTransfer]
    history: list[LifecycleHistory]


class ApprovalPage(StrictDTO):
    items: list[StatementApproval]
    next_cursor: str | None


class ReviewPage(StrictDTO):
    items: list[StatementReview]
    next_cursor: str | None


class LifecycleInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class ReviewInput(LifecycleInput):
    delivery_id: UUID
    order_line_id: UUID
    quantity: str = Field(min_length=1, max_length=64)


class ApproveInput(ReviewInput):
    sent_id: UUID
    feedback_id: UUID
    unit_price: str = Field(min_length=1, max_length=64)
    target_start: str = Field(min_length=10, max_length=10)
    target_end: str = Field(min_length=10, max_length=10)


class ClaimReviewInput(LifecycleInput):
    review_id: UUID
    review_version: int = Field(ge=1, strict=True)
    quantity: str = Field(min_length=1, max_length=64)
    unit_price: str = Field(min_length=1, max_length=64)


class ReserveInput(LifecycleInput):
    approval_id: UUID
    approval_version: int = Field(ge=1, strict=True)
    quantity: str = Field(min_length=1, max_length=64)


class ReleaseInput(LifecycleInput):
    allocation_id: UUID
    allocation_version: int = Field(ge=1, strict=True)


class SettlementPreviewInput(LifecycleInput):
    fees_confirmed: bool = Field(strict=True)
    reconfirmation: Literal["unknown", "not_required", "received"]


class SettleInput(SettlementPreviewInput):
    preview_token: str = Field(min_length=64, max_length=64)


class LifecyclePreview(StrictDTO):
    token: str
    blockers: list[str]
    calculation: StatementCalculation | None
    affected_allocations: list[StatementAllocation]


class DeferPreviewInput(LifecycleInput):
    target_start: str = Field(min_length=10, max_length=10)
    target_end: str = Field(min_length=10, max_length=10)


class DeferInput(DeferPreviewInput):
    preview_token: str = Field(min_length=64, max_length=64)


class CorrectApprovalPreviewInput(LifecycleInput):
    quantity: str = Field(min_length=1, max_length=64)
    unit_price: str = Field(min_length=1, max_length=64)
    disposition: Literal["review"]
    evidence_id: UUID
    cause: Literal["entry_error", "customer_change"]


class CorrectApprovalInput(CorrectApprovalPreviewInput):
    preview_token: str = Field(min_length=64, max_length=64)


class CorrectSettlementPreviewInput(LifecycleInput):
    allocation_id: UUID
    quantity: str = Field(min_length=1, max_length=64)
    unit_price: str = Field(min_length=1, max_length=64)
    disposition: Literal["review", "pending"]
    evidence_id: UUID
    cause: Literal["entry_error", "customer_change", "return"]
    no_downstream_effects: bool = Field(strict=True)


class CorrectSettlementInput(CorrectSettlementPreviewInput):
    preview_token: str = Field(min_length=64, max_length=64)


@router.get(
    "/statements/{statement_id}/lifecycle",
    operation_id="getStatementLifecycle",
    response_model=StatementLifecycleView,
)
def view(statement_id: UUID, request: Request, actor: CurrentActor):
    return services(request).statement_lifecycle.view(actor, statement_id)


@router.get(
    "/statement-approvals", operation_id="listStatementApprovals", response_model=ApprovalPage
)
def approvals(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statement_lifecycle.listing(
        actor, "approvals", customer_id, cursor, limit
    )


@router.get("/statement-reviews", operation_id="listStatementReviews", response_model=ReviewPage)
def reviews(
    request: Request,
    actor: CurrentActor,
    customer_id: UUID,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statement_lifecycle.listing(
        actor, "reviews", customer_id, cursor, limit
    )


@router.post(
    "/statements/{statement_id}/sent",
    operation_id="recordStatementSent",
    response_model=StatementEvidence,
)
def sent(
    statement_id: UUID,
    body: SentInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.evidence(
        actor, idempotency_key, statement_id, "sent", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/feedback",
    operation_id="recordStatementFeedback",
    response_model=StatementEvidence,
)
def feedback(
    statement_id: UUID,
    body: FeedbackInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.evidence(
        actor, idempotency_key, statement_id, "feedback", body.model_dump(mode="json")
    )


@router.get(
    "/statement-evidence/{evidence_id}/file",
    operation_id="downloadStatementEvidence",
    response_class=Response,
)
def evidence_file(evidence_id: UUID, request: Request, actor: CurrentActor):
    row, content = services(request).statement_lifecycle.download_evidence(actor, evidence_id)
    return Response(
        content,
        media_type=row["media_type"],
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="feedback-{evidence_id}"',
        },
    )


@router.post(
    "/statements/{statement_id}/approve",
    operation_id="approveStatementQuantity",
    response_model=StatementApproval,
)
def approve(
    statement_id: UUID,
    body: ApproveInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "approve", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/review",
    operation_id="reviewStatementQuantity",
    response_model=StatementReview,
)
def review(
    statement_id: UUID,
    body: ReviewInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "review", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/claim-review",
    operation_id="claimStatementReview",
    response_model=StatementDetail,
)
def claim_review(
    statement_id: UUID,
    body: ClaimReviewInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "claim_review", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/reserve",
    operation_id="reserveStatementApproval",
    response_model=StatementAllocation,
)
def reserve(
    statement_id: UUID,
    body: ReserveInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "reserve", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/release",
    operation_id="releaseStatementAllocation",
    response_model=StatementAllocation,
)
def release(
    statement_id: UUID,
    body: ReleaseInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "release", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/settlement-preview",
    operation_id="previewStatementSettlement",
    response_model=LifecyclePreview,
)
def preview(
    statement_id: UUID, body: SettlementPreviewInput, request: Request, actor: CurrentActor
):
    return services(request).statement_lifecycle.preview(
        actor, statement_id, body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/settle",
    operation_id="settleStatement",
    response_model=StatementDetail,
)
def settle(
    statement_id: UUID,
    body: SettleInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "settle", body.model_dump(mode="json")
    )


@router.post(
    "/statement-approvals/{approval_id}/defer-preview",
    operation_id="previewStatementDefer",
    response_model=LifecyclePreview,
)
def defer_preview(
    approval_id: UUID, body: DeferPreviewInput, request: Request, actor: CurrentActor
):
    return services(request).statement_lifecycle.change_approval(
        actor, None, approval_id, "defer", body.model_dump(mode="json"), preview=True
    )


@router.post(
    "/statement-approvals/{approval_id}/defer",
    operation_id="deferStatementApproval",
    response_model=StatementApproval,
)
def defer(
    approval_id: UUID,
    body: DeferInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.change_approval(
        actor, idempotency_key, approval_id, "defer", body.model_dump(mode="json")
    )


@router.post(
    "/statement-approvals/{approval_id}/correct-preview",
    operation_id="previewApprovalCorrection",
    response_model=LifecyclePreview,
)
def correct_approval_preview(
    approval_id: UUID, body: CorrectApprovalPreviewInput, request: Request, actor: CurrentActor
):
    return services(request).statement_lifecycle.change_approval(
        actor, None, approval_id, "correct_approval", body.model_dump(mode="json"), preview=True
    )


@router.post(
    "/statement-approvals/{approval_id}/correct",
    operation_id="correctStatementApproval",
    response_model=StatementApproval,
)
def correct_approval(
    approval_id: UUID,
    body: CorrectApprovalInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.change_approval(
        actor, idempotency_key, approval_id, "correct_approval", body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/correction-preview",
    operation_id="previewSettlementCorrection",
    response_model=LifecyclePreview,
)
def correction_preview(
    statement_id: UUID, body: CorrectSettlementPreviewInput, request: Request, actor: CurrentActor
):
    return services(request).statement_lifecycle.correction_preview(
        actor, statement_id, body.model_dump(mode="json")
    )


@router.post(
    "/statements/{statement_id}/correct",
    operation_id="correctStatementSettlement",
    response_model=StatementDetail,
)
def correct_settlement(
    statement_id: UUID,
    body: CorrectSettlementInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_lifecycle.command(
        actor, idempotency_key, statement_id, "correct_settlement", body.model_dump(mode="json")
    )
