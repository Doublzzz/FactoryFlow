"""Human-confirmed order input, independent of transport and persistence."""

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import ConfirmedQuantity, confirm_quantity


@dataclass(frozen=True)
class ConfirmedLine:
    description: str
    quantity: ConfirmedQuantity
    source_unit_price: str | None
    source_amount: str | None
    item_code: str | None = None
    item_name: str | None = None
    specification: str | None = None


@dataclass(frozen=True)
class ConfirmedOrder:
    customer_id: UUID
    order_number: str
    business_date: date
    currency: str
    lines: tuple[ConfirmedLine, ...]


def required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise BusinessError("INVALID_INPUT", field=field)
    return value.strip()


def source_decimal(value: object, field: str) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or len(value) > 64
        or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value)
    ):
        raise BusinessError("SOURCE_DECIMAL_INVALID", field=field)
    return value


def optional_text(value: object, field: str, limit: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > limit:
        raise BusinessError("INVALID_INPUT", field=field)
    return value.strip()


def prepare_order(payload: dict) -> ConfirmedOrder:
    try:
        customer = UUID(str(payload.get("customer_id", "")))
        business_date = date.fromisoformat(payload.get("business_date", ""))
    except ValueError, TypeError:
        raise BusinessError("INVALID_INPUT") from None
    if payload.get("currency") != "CNY":
        raise BusinessError("CURRENCY_REQUIRED", field="currency")
    lines = payload.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 200:
        raise BusinessError("LINES_REQUIRED", field="lines")
    confirmed = []
    for index, line in enumerate(lines):
        if not isinstance(line, dict):
            raise BusinessError("INVALID_INPUT", field=f"lines.{index}")
        item_code = optional_text(line.get("item_code"), f"lines.{index}.item_code", 100)
        item_name = optional_text(line.get("item_name"), f"lines.{index}.item_name", 500)
        specification = optional_text(
            line.get("specification"), f"lines.{index}.specification", 1000
        )
        structured = any(value is not None for value in (item_code, item_name, specification))
        if structured:
            description = " ".join(
                value for value in (item_code, item_name, specification) if value
            )
            if not description:
                raise BusinessError("INVALID_INPUT", field=f"lines.{index}.item_name")
        else:
            description = required_text(line.get("description"), f"lines.{index}.description", 500)
        confirmed.append(
            ConfirmedLine(
                description,
                confirm_quantity(line.get("quantity"), line.get("unit")),
                source_decimal(line.get("source_unit_price"), f"lines.{index}.source_unit_price"),
                source_decimal(line.get("source_amount"), f"lines.{index}.source_amount"),
                item_code,
                item_name,
                specification,
            )
        )
    return ConfirmedOrder(
        customer,
        required_text(payload.get("order_number"), "order_number", 100),
        business_date,
        "CNY",
        tuple(confirmed),
    )
