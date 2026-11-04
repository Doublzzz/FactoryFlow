"""Confirmed purchase quantities and optional source amounts; no stock opening."""

import re
from datetime import date
from decimal import Decimal, localcontext

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import QuantityError, confirm_quantity


def text_value(value, field, maximum=500, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > maximum:
        raise BusinessError("INVALID_INPUT", field=field)
    value = value.strip()
    if not value:
        if required:
            raise BusinessError("INVALID_INPUT", field=field)
        return None
    return value


def quantity(value, unit):
    try:
        result = confirm_quantity(value, unit)
    except QuantityError as exc:
        raise BusinessError(exc.code, field="quantity") from exc
    if result.value <= 0 or result.policy.canonical_unit is None:
        raise BusinessError("PURCHASE_QUANTITY_INVALID", field="quantity")
    return result


def supplier_input(payload):
    return {
        key: text_value(payload.get(key), key, maximum, key == "full_name")
        for key, maximum in [
            ("full_name", 200),
            ("contact", 200),
            ("phone", 100),
            ("address", 500),
            ("note", 1000),
        ]
    }


def document_input(payload):
    try:
        business_date = date.fromisoformat(payload["business_date"]).isoformat()
    except (KeyError, TypeError, ValueError) as exc:
        raise BusinessError("INVALID_INPUT", field="business_date") from exc
    if not isinstance(payload.get("lines"), list) or not 1 <= len(payload["lines"]) <= 200:
        raise BusinessError("INVALID_INPUT", field="lines")
    return {
        "business_date": business_date,
        "number": text_value(payload.get("number"), "number", 100),
        "note": text_value(payload.get("note"), "note", 1000),
    }


def source_money(value, field):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,18}(?:\.[0-9]{1,6})?", value):
        raise BusinessError("SOURCE_DECIMAL_INVALID", field=field)
    return value


def order_input(payload):
    header = document_input(payload)
    currency = payload.get("currency")
    if currency not in (None, "CNY", "USD"):
        raise BusinessError("CURRENCY_REQUIRED", field="currency")
    if payload.get("extraction_id") and not payload.get("source_id"):
        raise BusinessError("PURCHASE_SOURCE_REQUIRED", field="source_id")
    return {
        **header,
        "currency": currency,
        "buyer_name": text_value(payload.get("buyer_name"), "buyer_name", 200),
        "source_id": payload.get("source_id"),
        "extraction_id": payload.get("extraction_id"),
    }


def total_amount(lines):
    if not lines or any(line.get("source_amount") is None for line in lines):
        return None
    with localcontext() as context:
        context.prec = 80
        return str(sum((Decimal(line["source_amount"]) for line in lines), Decimal(0)))


def request_fingerprint(payload):
    """Keep pre-0018 create fingerprints when all newly optional values are absent."""
    header_fields = {"currency", "buyer_name", "source_id", "extraction_id"}
    line_fields = {"source_unit_price", "source_amount", "expected_material_version"}
    return {
        **{k: v for k, v in payload.items() if k not in header_fields or v is not None},
        "lines": [
            {k: v for k, v in line.items() if k not in line_fields or v is not None}
            for line in payload["lines"]
        ],
    }
