from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field

router = APIRouter(tags=["Materials"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class MaterialInput(StrictDTO):
    own_code: str | None = Field(default=None, max_length=100)
    name: str = Field(min_length=1, max_length=500)
    specification: str | None = Field(default=None, max_length=1000)
    unit: str | None = Field(default=None, max_length=40)


class MaterialUpdate(MaterialInput):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)
    active: bool = Field(strict=True)


class MatchedCustomerCode(StrictDTO):
    customer_name: str
    customer_code: str


class MaterialResponse(MaterialInput):
    id: UUID
    own_code: str
    version: int
    active: bool
    change: dict | None = None
    matched_customer_codes: list[MatchedCustomerCode] = Field(default_factory=list)


class MaterialList(StrictDTO):
    items: list[MaterialResponse]
    next_offset: int | None


class MaterialCodeInput(StrictDTO):
    customer_id: UUID
    customer_code: str = Field(min_length=1, max_length=100)
    material_id: UUID
    expected_material_version: int = Field(ge=1, strict=True)
    expected_mapping_version: int = Field(default=0, ge=0, strict=True)
    item_name: str | None = Field(default=None, max_length=500)
    specification: str | None = Field(default=None, max_length=1000)
    unit: str | None = Field(default=None, max_length=40)
    reason: str | None = Field(default=None, max_length=500)


class MaterialCodeResponse(StrictDTO):
    customer_id: UUID
    customer_code: str
    material_id: UUID
    item_name: str | None
    specification: str | None
    canonical_unit: str | None
    version: int
    change: dict | None = None


class MaterialCodeList(StrictDTO):
    items: list[MaterialCodeResponse]


ImportColumn = Annotated[int, Field(ge=1, le=30, strict=True)]


class MaterialImportFile(StrictDTO):
    filename: str = Field(min_length=1, max_length=180)
    content_base64: str = Field(min_length=1, max_length=2796204)
    header_row: int = Field(default=1, ge=1, le=50, strict=True)


class MaterialImportColumns(StrictDTO):
    name: ImportColumn
    own_code: ImportColumn | None = None
    specification: ImportColumn | None = None
    unit: ImportColumn | None = None
    customer_code: ImportColumn | None = None


class MaterialImportChoice(StrictDTO):
    row_number: int = Field(ge=1, le=2097152, strict=True)
    action: Literal["default", "create", "reuse", "skip"]
    material_id: UUID | None = None
    expected_material_version: int | None = Field(default=None, ge=1, strict=True)
    confirmed_numeric_fields: list[Literal["own_code", "customer_code"]] = Field(
        default_factory=list, max_length=2
    )


class MaterialImportInput(MaterialImportFile):
    columns: MaterialImportColumns
    customer_id: UUID | None = None
    choices: list[MaterialImportChoice] = Field(default_factory=list, max_length=2000)


class MaterialImportConfirm(MaterialImportInput):
    preview_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class MaterialImportColumn(StrictDTO):
    index: int
    label: str


class MaterialImportSample(StrictDTO):
    row_number: int
    values: list[str]


class MaterialImportInspection(StrictDTO):
    file_hash: str
    sheet_name: str
    header_row: int
    columns: list[MaterialImportColumn]
    samples: list[MaterialImportSample]
    data_row_count: int


class MaterialImportValues(StrictDTO):
    own_code: str | None
    name: str
    specification: str | None
    unit: str | None
    customer_code: str | None


class MaterialImportNumeric(StrictDTO):
    field: Literal["own_code", "customer_code"]
    value: str
    number_format: str | None = Field(max_length=256)


class MaterialImportPreviewRow(StrictDTO):
    row_number: int
    source: MaterialImportValues
    action: Literal["create", "reuse", "skip", "pending"]
    material: MaterialResponse | None
    candidates: list[MaterialResponse]
    issues: list[str]
    warnings: list[str]
    numeric_fields: list[MaterialImportNumeric]


class MaterialImportPreview(StrictDTO):
    file_hash: str
    preview_fingerprint: str
    ready: bool
    rows: list[MaterialImportPreviewRow]


class MaterialImportResultRow(StrictDTO):
    row_number: int
    action: Literal["create", "reuse", "skip"]
    reason: str | None
    material: MaterialResponse | None
    change: dict | None
    mapping_change: dict | None


class MaterialImportResult(StrictDTO):
    file_hash: str
    rows: list[MaterialImportResultRow]
    created_count: int
    reused_count: int
    skipped_count: int
    mapping_count: int
    actor_id: UUID
    occurred_at: str


@router.post(
    "/materials/imports/inspect",
    operation_id="inspectMaterialImport",
    response_model=MaterialImportInspection,
)
def inspect_material_import(body: MaterialImportFile, request: Request, actor: CurrentActor):
    return services(request).materials.inspect_import(
        actor, body.model_dump(mode="json", exclude_unset=True)
    )


@router.post(
    "/materials/imports/preview",
    operation_id="previewMaterialImport",
    response_model=MaterialImportPreview,
)
def preview_material_import(body: MaterialImportInput, request: Request, actor: CurrentActor):
    return services(request).materials.preview_import(
        actor, body.model_dump(mode="json", exclude_unset=True)
    )


@router.post(
    "/materials/imports/confirm",
    operation_id="confirmMaterialImport",
    response_model=MaterialImportResult,
)
def confirm_material_import(
    body: MaterialImportConfirm, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).materials.confirm_import(
        actor, idempotency_key, body.model_dump(mode="json", exclude_unset=True)
    )


@router.get("/materials", operation_id="listMaterials", response_model=MaterialList)
def list_materials(
    request: Request,
    actor: CurrentActor,
    q: Annotated[str, Query(max_length=500)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).materials.list(actor, q, offset, limit)


@router.post("/materials", operation_id="createMaterial", response_model=MaterialResponse)
def create_material(
    body: MaterialInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).materials.create(actor, idempotency_key, body.model_dump(mode="json"))


@router.post(
    "/materials/{material_id}", operation_id="updateMaterial", response_model=MaterialResponse
)
def update_material(
    material_id: UUID,
    body: MaterialUpdate,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).materials.update(
        actor, idempotency_key, material_id, body.model_dump(mode="json")
    )


@router.get("/material-codes", operation_id="listMaterialCodes", response_model=MaterialCodeList)
def list_codes(
    request: Request,
    actor: CurrentActor,
    material_id: UUID | None = None,
    customer_id: UUID | None = None,
    customer_code: Annotated[str | None, Query(max_length=100)] = None,
):
    return services(request).materials.codes(actor, material_id, customer_id, customer_code)


@router.post(
    "/material-codes", operation_id="saveMaterialCode", response_model=MaterialCodeResponse
)
def save_code(
    body: MaterialCodeInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).materials.save_code(
        actor, idempotency_key, body.model_dump(mode="json")
    )
