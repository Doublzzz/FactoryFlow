from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import Response
from pydantic import Field

router = APIRouter(tags=["Work archives"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]
Rule = Literal["date", "customer", "month_customer"]


class ArchiveSettings(StrictDTO):
    version: int
    rule: Rule
    updated_at: str | None
    root_configured: bool


class SaveArchiveSettings(StrictDTO):
    expected_version: int = Field(ge=0, strict=True)
    rule: Rule


class ArchiveSource(StrictDTO):
    key: str
    kind: Literal["source", "delivery", "statement_export"]
    source_id: str
    title: str
    customer_id: str | None
    customer_name: str | None
    business_date: str | None
    period_end: str | None
    version_label: str
    state_label: str
    extension: str
    current: bool
    available: bool
    byte_size: int | None
    token: str


class ArchiveSources(StrictDTO):
    items: list[ArchiveSource]
    next_cursor: str | None


class ArchiveSelection(StrictDTO):
    key: str = Field(pattern=r"^(source|delivery|statement_export):[0-9a-fA-F-]{36}$")
    token: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArchivePreviewRequest(StrictDTO):
    rule: Rule
    selections: list[ArchiveSelection] = Field(min_length=1, max_length=50)


class ArchiveCreateRequest(ArchivePreviewRequest):
    preview_token: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArchiveItem(ArchiveSource):
    byte_size: int
    path: str
    sha256: str


class ArchivePreview(StrictDTO):
    items: list[ArchiveItem]
    total_bytes: int
    preview_token: str


class ArchiveBatch(StrictDTO):
    id: str
    rule: Rule
    status: Literal["pending", "failed", "ready"]
    current: bool
    file_hash: str | None
    error_code: str | None
    created_at: str
    items: list[ArchiveItem]
    total_bytes: int
    local_available: bool | None
    local_error: str | None
    relative_directory: str


class ArchiveBatches(StrictDTO):
    items: list[ArchiveBatch]
    next_cursor: str | None


@router.get("/archive-settings", operation_id="getArchiveSettings", response_model=ArchiveSettings)
def settings(request: Request, actor: CurrentActor):
    return services(request).archives.settings(actor)


@router.post(
    "/archive-settings", operation_id="saveArchiveSettings", response_model=ArchiveSettings
)
def save_settings(
    body: SaveArchiveSettings, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).archives.save_settings(
        actor, idempotency_key, body.expected_version, body.rule
    )


@router.get("/archive-sources", operation_id="listArchiveSources", response_model=ArchiveSources)
def sources(
    request: Request,
    actor: CurrentActor,
    kind: Literal["source", "delivery", "statement_export"],
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=50),
):
    return services(request).archives.catalog(actor, kind, cursor, limit)


@router.post("/archives/preview", operation_id="previewArchive", response_model=ArchivePreview)
def preview(body: ArchivePreviewRequest, request: Request, actor: CurrentActor):
    return services(request).archives.preview(
        actor, body.rule, [i.model_dump() for i in body.selections]
    )


@router.post("/archives", operation_id="createArchive", response_model=ArchiveBatch)
def create(
    body: ArchiveCreateRequest, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).archives.create(
        actor,
        idempotency_key,
        body.rule,
        [i.model_dump() for i in body.selections],
        body.preview_token,
    )


@router.get("/archives", operation_id="listArchives", response_model=ArchiveBatches)
def listing(
    request: Request,
    actor: CurrentActor,
    cursor: UUID | None = None,
    limit: int = Query(25, ge=1, le=50),
):
    return services(request).archives.listing(actor, cursor, limit)


@router.get("/archives/{identifier}", operation_id="getArchive", response_model=ArchiveBatch)
def detail(identifier: UUID, request: Request, actor: CurrentActor):
    return services(request).archives.detail(actor, identifier)


@router.post(
    "/archives/{identifier}/generate", operation_id="generateArchive", response_model=ArchiveBatch
)
def generate(identifier: UUID, request: Request, actor: CurrentActor):
    return services(request).archives.generate(actor, identifier)


@router.get("/archives/{identifier}/file", operation_id="downloadArchive", response_class=Response)
def download(identifier: UUID, request: Request, actor: CurrentActor, historical: bool = False):
    return Response(
        services(request).archives.download(actor, identifier, historical),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="work-archive-{identifier}.zip"'},
    )
