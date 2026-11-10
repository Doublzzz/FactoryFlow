from typing import Annotated
from uuid import UUID

from factoryflow.kernel.contracts import Actor
from factoryflow.platform.http import ERROR_RESPONSES, StrictDTO, require_actor, services
from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import Field

router = APIRouter(prefix="/customers", tags=["Customers"], responses=ERROR_RESPONSES)


class CustomerInput(StrictDTO):
    full_name: str = Field(min_length=1, max_length=200)


class CustomerResponse(StrictDTO):
    id: UUID
    full_name: str


class CustomerSearchResponse(StrictDTO):
    items: list[CustomerResponse]
    next_cursor: UUID | None


@router.get("/search", operation_id="searchCustomers", response_model=CustomerSearchResponse)
def search_customers(
    request: Request,
    actor: Annotated[Actor, Depends(require_actor)],
    name: Annotated[str, Query(min_length=1, max_length=200)],
    cursor: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return services(request).customers.search(actor, name, cursor, limit)


@router.get("", operation_id="listCustomers", response_model=list[CustomerResponse])
def list_customers(request: Request, actor: Annotated[Actor, Depends(require_actor)]):
    return services(request).customers.list(actor)


@router.post("", operation_id="createCustomer", response_model=CustomerResponse)
def create_customer(
    body: CustomerInput,
    request: Request,
    actor: Annotated[Actor, Depends(require_actor)],
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
):
    return services(request).customers.create(actor, idempotency_key, body.full_name)
