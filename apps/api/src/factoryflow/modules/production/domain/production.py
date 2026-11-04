"""Small production facts: exact quantities, explicit dates, no inferred consumption."""

from datetime import date
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity


def number(value):
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def text_value(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > 500 or (required and not value.strip()):
        raise BusinessError("INVALID_INPUT")
    return value.strip() or None


def identifier(value):
    try:
        return str(UUID(str(value)))
    except ValueError, TypeError:
        raise BusinessError("INVALID_INPUT") from None


def business_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return value
    except ValueError, TypeError:
        raise BusinessError("INVALID_INPUT", field="business_date") from None


def expected_version(value):
    if type(value) is not int or value < 1:
        raise BusinessError("INVALID_INPUT", field="expected_version")
    return value


def quantity(value, unit=None, *, positive=False):
    result = confirm_quantity(value, unit)
    if unit is not None and result.policy.canonical_unit is None:
        raise BusinessError("INVENTORY_UNIT_REQUIRED", 409)
    if positive and result.value <= 0:
        raise BusinessError("PRODUCTION_POSITIVE_QUANTITY_REQUIRED")
    return result


def create_request(payload):
    return {
        **{
            key: identifier(payload.get(key))
            for key in ("order_id", "revision_id", "order_line_id")
        },
        "expected_order_version": expected_version(payload.get("expected_order_version")),
        "planned_quantity": quantity(payload.get("planned_quantity"), positive=True).canonical,
        "business_date": business_date(payload.get("business_date")),
        "note": text_value(payload.get("note")),
    }


def completion_request(payload):
    good = quantity(payload.get("quantity"))
    scrap = quantity(payload.get("scrap_quantity", "0"))
    if good.value == 0 and scrap.value == 0:
        raise BusinessError("PRODUCTION_EMPTY_COMPLETION")
    return {
        "quantity": good.canonical,
        "scrap_quantity": scrap.canonical,
        "business_date": business_date(payload.get("business_date")),
        "note": text_value(payload.get("note")),
    }


def material_request(payload):
    return {
        "quantity": quantity(payload.get("quantity"), positive=True).canonical,
        "business_date": business_date(payload.get("business_date")),
        "reason": text_value(payload.get("reason"), required=True),
    }


def transition_request(payload):
    return {
        "expected_version": expected_version(payload.get("expected_version")),
        "reason": text_value(payload.get("reason"), required=True),
    }


def page_arguments(offset, limit):
    if type(offset) is not int or offset < 0 or type(limit) is not int or not 1 <= limit <= 100:
        raise BusinessError("INVALID_INPUT")
