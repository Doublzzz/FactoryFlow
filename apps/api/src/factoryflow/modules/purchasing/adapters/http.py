from typing import Annotated, Literal
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.modules.purchasing.adapters.print_renderer import render_purchase
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import Field

router = APIRouter(tags=["Purchasing"], responses=ERROR_RESPONSES)
CurrentActor = Annotated[Actor, Depends(require_actor)]
CommandKey = Annotated[UUID, Header(alias="Idempotency-Key")]


class SupplierInput(StrictDTO):
    full_name: str = Field(min_length=1, max_length=200)
    contact: str | None = Field(default=None, max_length=200)
    phone: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    note: str | None = Field(default=None, max_length=1000)


class SupplierUpdate(SupplierInput):
    active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


class SupplierResponse(SupplierInput):
    id: UUID
    active: bool
    version: int
    created_by: UUID
    updated_by: UUID
    created_at: str
    updated_at: str


class SupplierPage(StrictDTO):
    items: list[SupplierResponse]
    total: int
    offset: int
    limit: int


class PurchaseLineInput(StrictDTO):
    material_id: UUID
    quantity: str = Field(min_length=1, max_length=64)
    source_unit_price: str | None = Field(default=None, max_length=64)
    source_amount: str | None = Field(default=None, max_length=64)
    expected_material_version: int | None = Field(default=None, ge=1, strict=True)


class ReceiptLineInput(StrictDTO):
    purchase_line_id: UUID | None = None
    material_id: UUID | None = None
    quantity: str = Field(min_length=1, max_length=64)


class PurchaseHeaderInput(StrictDTO):
    supplier_id: UUID
    business_date: str = Field(min_length=10, max_length=10)
    number: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=1000)


class PurchaseOrderInput(PurchaseHeaderInput):
    lines: list[PurchaseLineInput] = Field(min_length=1, max_length=200)
    currency: Literal["CNY", "USD"] | None = None
    buyer_name: str | None = Field(default=None, max_length=200)
    source_id: UUID | None = None
    extraction_id: UUID | None = None


class PurchaseReceiptInput(PurchaseHeaderInput):
    purchase_order_id: UUID | None = None
    lines: list[ReceiptLineInput] = Field(min_length=1, max_length=200)


class PurchaseTransitionInput(StrictDTO):
    expected_version: int = Field(ge=1, strict=True)
    reason: str = Field(min_length=1, max_length=500)


class PurchaseLineResponse(StrictDTO):
    id: UUID
    line_number: int
    material_id: UUID
    own_code: str
    material_name: str
    specification: str | None
    canonical_unit: str


class PurchaseOrderLine(PurchaseLineResponse):
    order_id: UUID
    ordered_quantity: str
    received_quantity: str
    remaining_quantity: str
    source_unit_price: str | None = None
    source_amount: str | None = None


class PurchaseReceiptLine(PurchaseLineResponse):
    receipt_id: UUID
    purchase_line_id: UUID | None
    quantity: str


class PurchaseHeaderResponse(StrictDTO):
    id: UUID
    supplier_id: UUID
    number: str
    business_date: str
    supplier_name: str
    note: str | None
    version: int
    created_by: UUID
    created_at: str


class PurchaseOrderHeader(PurchaseHeaderResponse):
    status: Literal["open", "closed"]
    closed_by: UUID | None
    closed_at: str | None
    close_reason: str | None
    currency: Literal["CNY", "USD"] | None = None
    buyer_name: str | None = None
    source_id: UUID | None = None
    extraction_id: UUID | None = None


class PurchaseOrderResponse(PurchaseOrderHeader):
    lines: list[PurchaseOrderLine]
    total_amount: str | None = None


class PurchaseReceiptHeader(PurchaseHeaderResponse):
    status: Literal["active", "void"]
    purchase_order_id: UUID | None
    void_by: UUID | None
    void_at: str | None
    void_reason: str | None


class PurchaseReceiptResponse(PurchaseReceiptHeader):
    lines: list[PurchaseReceiptLine]


class PurchaseOrderPage(StrictDTO):
    items: list[PurchaseOrderHeader]
    total: int
    offset: int
    limit: int


class PurchaseReceiptPage(StrictDTO):
    items: list[PurchaseReceiptHeader]
    total: int
    offset: int
    limit: int


@router.get("/suppliers", operation_id="listSuppliers", response_model=SupplierPage)
def list_suppliers(
    request: Request,
    actor: CurrentActor,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).purchasing.list_suppliers(actor, q, offset, limit)


@router.post("/suppliers", operation_id="createSupplier", response_model=SupplierResponse)
def create_supplier(
    body: SupplierInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).purchasing.create_supplier(
        actor, idempotency_key, body.model_dump(mode="json")
    )


@router.post(
    "/suppliers/{supplier_id}", operation_id="updateSupplier", response_model=SupplierResponse
)
def update_supplier(
    supplier_id: UUID,
    body: SupplierUpdate,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).purchasing.update_supplier(
        actor, idempotency_key, supplier_id, body.model_dump(mode="json")
    )


@router.get("/purchase-orders", operation_id="listPurchaseOrders", response_model=PurchaseOrderPage)
def list_orders(
    request: Request,
    actor: CurrentActor,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).purchasing.list_orders(actor, q, offset, limit)


@router.post(
    "/purchase-orders", operation_id="createPurchaseOrder", response_model=PurchaseOrderResponse
)
def create_order(
    body: PurchaseOrderInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).purchasing.create_order(
        actor, idempotency_key, body.model_dump(mode="json")
    )


@router.get(
    "/purchase-orders/by-source/{source_id}",
    operation_id="getPurchaseOrderBySource",
    response_model=PurchaseOrderResponse,
)
def get_by_source(source_id: UUID, request: Request, actor: CurrentActor):
    return services(request).purchasing.get_order_by_source(actor, source_id)


@router.get(
    "/purchase-orders/{order_id}/print",
    operation_id="printPurchaseOrder",
    response_class=HTMLResponse,
)
def print_order(
    order_id: UUID,
    request: Request,
    actor: CurrentActor,
    locale: Literal["zh-CN", "en"] = "zh-CN",
):
    order = services(request).purchasing.get_order(actor, order_id)
    return HTMLResponse(
        render_purchase(order, locale),
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; "
                "font-src 'self'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"
            ),
        },
    )


@router.get(
    "/purchase-orders/{order_id}",
    operation_id="getPurchaseOrder",
    response_model=PurchaseOrderResponse,
)
def get_order(order_id: UUID, request: Request, actor: CurrentActor):
    return services(request).purchasing.get_order(actor, order_id)


@router.post(
    "/purchase-orders/{order_id}/close",
    operation_id="closePurchaseOrder",
    response_model=PurchaseOrderResponse,
)
def close_order(
    order_id: UUID,
    body: PurchaseTransitionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).purchasing.close_order(
        actor, idempotency_key, order_id, body.model_dump(mode="json")
    )


@router.get(
    "/purchase-receipts", operation_id="listPurchaseReceipts", response_model=PurchaseReceiptPage
)
def list_receipts(
    request: Request,
    actor: CurrentActor,
    q: Annotated[str, Query(max_length=200)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).purchasing.list_receipts(actor, q, offset, limit)


@router.post(
    "/purchase-receipts",
    operation_id="createPurchaseReceipt",
    response_model=PurchaseReceiptResponse,
)
def create_receipt(
    body: PurchaseReceiptInput, request: Request, actor: CurrentActor, idempotency_key: CommandKey
):
    return services(request).purchasing.create_receipt(
        actor, idempotency_key, body.model_dump(mode="json")
    )


@router.get(
    "/purchase-receipts/{receipt_id}",
    operation_id="getPurchaseReceipt",
    response_model=PurchaseReceiptResponse,
)
def get_receipt(receipt_id: UUID, request: Request, actor: CurrentActor):
    return services(request).purchasing.get_receipt(actor, receipt_id)


@router.post(
    "/purchase-receipts/{receipt_id}/void",
    operation_id="voidPurchaseReceipt",
    response_model=PurchaseReceiptResponse,
)
def void_receipt(
    receipt_id: UUID,
    body: PurchaseTransitionInput,
    request: Request,
    actor: CurrentActor,
    idempotency_key: CommandKey,
):
    return services(request).purchasing.void_receipt(
        actor, idempotency_key, receipt_id, body.model_dump(mode="json")
    )
