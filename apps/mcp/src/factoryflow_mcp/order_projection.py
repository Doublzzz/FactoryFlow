"""Validate and whitelist the public order-detail contract without importing the server."""

from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Projection(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)


class QuantityPolicy(Projection):
    mode: Literal["INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"]
    canonical_unit: str | None
    warning_codes: list[str]
    version: str = Field(min_length=1)


class Material(Projection):
    id: UUID
    own_code: str
    name: str
    specification: str | None
    unit: str | None
    version: int = Field(ge=1)
    active: bool
    kind: Literal["finished"] = "finished"


class OrderLine(Projection):
    id: UUID
    line_number: int = Field(ge=1, le=200)
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
    material: Material | None = None

    @field_validator(
        "quantity", "delivered_quantity", "remaining_quantity", "source_unit_price", "source_amount"
    )
    @classmethod
    def exact_nonnegative_decimal(cls, value):
        if value is not None:
            try:
                amount = Decimal(value)
            except InvalidOperation:
                raise ValueError("Invalid decimal string") from None
            if not amount.is_finite() or amount < 0:
                raise ValueError("Invalid decimal string")
        return value

    @model_validator(mode="after")
    def consistent_references(self):
        if self.quantity_policy.canonical_unit != self.canonical_unit:
            raise ValueError("Mismatched quantity policy")
        if self.material is not None and self.material.id != self.material_id:
            raise ValueError("Mismatched material")
        return self


class Revision(Projection):
    revision_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_number: int = Field(ge=1)
    parent_revision_id: UUID | None
    confirmed_at: str = Field(min_length=1)


class OrderDetail(Projection):
    id: UUID
    customer_id: UUID
    customer_name: str = Field(min_length=1)
    order_number: str = Field(min_length=1)
    business_date: str = Field(min_length=1)
    currency: Literal["CNY", "USD"]
    revision_id: UUID
    status: Literal["active", "deleted"]
    version: int = Field(ge=1)
    lines: list[OrderLine] = Field(min_length=1, max_length=200)
    revisions: list[Revision] = Field(min_length=1)

    @model_validator(mode="after")
    def complete_references(self):
        if len({line.id for line in self.lines}) != len(self.lines) or any(
            line.line_number != number for number, line in enumerate(self.lines, 1)
        ):
            raise ValueError("Invalid order lines")
        # History may include a revision committed after the current state was read.
        if self.revision_id not in {revision.revision_id for revision in self.revisions}:
            raise ValueError("Missing current revision")
        return self
