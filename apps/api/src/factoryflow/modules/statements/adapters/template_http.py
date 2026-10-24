from typing import Annotated
from uuid import UUID

from factoryflow.modules.statements.adapters.http import CommandKey, CurrentActor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, services
from fastapi import APIRouter, Query, Request
from pydantic import Field

router = APIRouter(tags=["Statement templates"], responses=ERROR_RESPONSES)


class TemplateMapping(StrictDTO):
    sheet_name: str = Field(min_length=1, max_length=31)
    detail_start_row: int = Field(ge=2, le=300, strict=True)
    detail_end_row: int = Field(ge=2, le=300, strict=True)
    columns: dict[str, str] = Field(max_length=14)
    cells: dict[str, str] = Field(max_length=9)


class TemplateFileInput(StrictDTO):
    filename: str = Field(min_length=1, max_length=180)
    content_base64: str = Field(min_length=1, max_length=2796204)


class TemplateMappedInput(TemplateFileInput):
    inspected_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    mapping: TemplateMapping


class TemplateImportInput(TemplateMappedInput):
    name: str = Field(min_length=1, max_length=80)


class TemplatePreviewInput(TemplateMappedInput):
    statement_id: UUID
    expected_version: int = Field(ge=1, strict=True)


class TemplateInspection(StrictDTO):
    file_hash: str
    sheet_name: str
    rows: int
    columns: int
    grid: list[list[str]]
    suggested_mapping: TemplateMapping | None


class TemplatePreview(StrictDTO):
    content_base64: str
    grid: list[list[str]]
    statement_version: int


class TemplateDetail(StrictDTO):
    id: UUID
    customer_id: UUID
    name: str
    version: int
    file_hash: str
    mapping: TemplateMapping
    created_at: str


class TemplatePage(StrictDTO):
    items: list[TemplateDetail]
    next_cursor: str | None


@router.post(
    "/customers/{customer_id}/statement-templates/inspect",
    operation_id="inspectStatementTemplate",
    response_model=TemplateInspection,
)
def inspect(customer_id: UUID, body: TemplateFileInput, request: Request, actor: CurrentActor):
    return services(request).statement_templates.inspect(actor, customer_id, body.model_dump())


@router.post(
    "/customers/{customer_id}/statement-templates/preview",
    operation_id="previewStatementTemplate",
    response_model=TemplatePreview,
)
def preview(customer_id: UUID, body: TemplatePreviewInput, request: Request, actor: CurrentActor):
    return services(request).statement_templates.preview(
        actor, customer_id, body.model_dump(mode="json")
    )


@router.post(
    "/customers/{customer_id}/statement-templates",
    operation_id="importStatementTemplate",
    response_model=TemplateDetail,
)
def import_template(
    customer_id: UUID,
    body: TemplateImportInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).statement_templates.import_template(
        actor, idempotency_key, customer_id, body.model_dump()
    )


@router.get(
    "/customers/{customer_id}/statement-templates",
    operation_id="listStatementTemplates",
    response_model=TemplatePage,
)
def listing(
    customer_id: UUID,
    request: Request,
    actor: CurrentActor,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).statement_templates.listing(actor, customer_id, cursor, limit)


@router.get(
    "/customers/{customer_id}/statement-templates/{template_id}",
    operation_id="getStatementTemplate",
    response_model=TemplateDetail,
)
def detail(customer_id: UUID, template_id: UUID, request: Request, actor: CurrentActor):
    return services(request).statement_templates.detail(actor, customer_id, template_id)
