import base64
from typing import Annotated, Literal
from urllib.parse import unquote
from uuid import UUID

from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request, Response
from pydantic import Field
from starlette.concurrency import run_in_threadpool

router = APIRouter(tags=["Extraction"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class SourceResult(StrictDTO):
    source_id: UUID
    original_sha256: str


class ExtractionResult(StrictDTO):
    extraction_id: UUID
    status: Literal["ready", "failed"]


class CandidateLine(StrictDTO):
    description: str
    item_code: str | None = None
    item_name: str | None = None
    specification: str | None = None
    quantity: str
    unit: str | None
    source_unit_price: str | None
    source_amount: str | None


class CandidateWarning(StrictDTO):
    code: Literal["TABLE_COVERAGE_UNRESOLVED"]
    page: Annotated[int, Field(ge=1, le=5)]


class Candidate(StrictDTO):
    order_number: str
    business_date: str
    currency: str
    lines: list[CandidateLine]
    warnings: list[CandidateWarning] = Field(default_factory=list)


class ExtractionPage(StrictDTO):
    number: int
    width: int
    height: int
    text: str
    rows: list[str]


class ExtractionDetail(ExtractionResult):
    source_id: UUID
    trace_hash: str
    original_sha256: str
    error_code: str | None
    candidate: Candidate
    pages: list[ExtractionPage]


class SourceSummary(StrictDTO):
    source_id: UUID
    filename: str
    media_type: str
    created_at: str
    extraction_id: UUID | None
    order_id: UUID | None


class SourceList(StrictDTO):
    items: list[SourceSummary]
    next_cursor: str | None


@router.post(
    "/sources",
    operation_id="uploadSource",
    response_model=SourceResult,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                media: {"schema": {"type": "string", "format": "binary", "maxLength": 10485760}}
                for media in ("image/png", "image/jpeg", "application/pdf")
            },
        }
    },
)
async def upload_source(
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
    filename: Annotated[str, Header(alias="X-Filename", max_length=2200)],
    content_type: Annotated[str, Header()],
):
    actor.require_write()
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > 10 * 1024 * 1024:
            raise BusinessError("FILE_TOO_LARGE", 413)
        chunks.extend(chunk)
    return await run_in_threadpool(
        services(request).extraction.upload,
        actor,
        idempotency_key,
        unquote(filename),
        content_type,
        bytes(chunks),
    )


@router.get("/sources", operation_id="listSources", response_model=SourceList)
def sources(
    request: Request,
    actor: CurrentActor,
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
):
    return services(request).extraction.list(actor, cursor, limit)


@router.get("/sources/{source_id}/download", operation_id="downloadSource")
def original(source_id: UUID, request: Request, actor: CurrentActor):
    row, content = services(request).extraction.original(actor, source_id)
    extension = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}[
        row["media_type"]
    ]
    return Response(
        content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="source-{source_id}.{extension}"',
            "ETag": f'"{row["original_sha256"]}"',
        },
    )


@router.post(
    "/sources/{source_id}/extractions",
    operation_id="extractSource",
    response_model=ExtractionResult,
)
def extract(source_id: UUID, request: Request, actor: CurrentActor, idempotency_key: CommandKey):
    return services(request).extraction.extract(actor, idempotency_key, source_id)


@router.get(
    "/extractions/{extraction_id}", operation_id="getExtraction", response_model=ExtractionDetail
)
def extraction(extraction_id: UUID, request: Request, actor: CurrentActor):
    detail = services(request).extraction.detail(actor, extraction_id)
    return {key: detail[key] for key in ExtractionDetail.model_fields if key != "pages"} | {
        "pages": [
            {key: page[key] for key in ExtractionPage.model_fields} for page in detail["pages"]
        ]
    }


@router.get("/extractions/{extraction_id}/pages/{number}", operation_id="getSourcePage")
def preview(
    extraction_id: UUID,
    number: Annotated[int, Field(ge=1, le=5)],
    request: Request,
    actor: CurrentActor,
):
    detail = services(request).extraction.detail(actor, extraction_id)
    if number > len(detail["pages"]):
        raise BusinessError("SOURCE_PAGE_NOT_FOUND", 404)
    return Response(
        base64.b64decode(detail["pages"][number - 1]["preview_base64"], validate=True),
        media_type="image/png",
    )
