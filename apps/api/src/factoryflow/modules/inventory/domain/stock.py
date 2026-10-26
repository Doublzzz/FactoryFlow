"""Exact stock quantities; no unit conversion or automatic receipt inference."""

from datetime import date
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity

MAX_QUANTITY = Decimal("9223372036854775.807")


def number(value):
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def reason_text(value, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or len(value) > 500 or (required and not value.strip()):
        raise BusinessError("INVALID_INPUT", field="reason")
    return value.strip() or None


def prepare(payload, *, count=False):
    quantity = confirm_quantity(payload.get("quantity"), None)
    try:
        value = payload["business_date"]
        day = date.fromisoformat(value)
        if not isinstance(value, str) or day.isoformat() != value:
            raise ValueError
    except KeyError, TypeError, ValueError:
        raise BusinessError("INVALID_INPUT", field="business_date") from None
    result = {
        "quantity": quantity.canonical,
        "business_date": day.isoformat(),
        "reason": reason_text(payload.get("reason"), required=count),
    }
    if count:
        expected = payload.get("expected_version")
        if type(expected) is not int or expected < 1:
            raise BusinessError("INVALID_INPUT", field="expected_version")
        result["expected_version"] = expected
    return result


def validate_quantity(quantity, unit, *, positive=False):
    result = confirm_quantity(quantity, unit)
    if result.policy.canonical_unit is None:
        raise BusinessError("INVENTORY_UNIT_REQUIRED", 409)
    if positive and result.value <= 0:
        raise BusinessError("INVENTORY_POSITIVE_QUANTITY_REQUIRED")
    return result


def validate_range(*quantities):
    if any(abs(value) > MAX_QUANTITY for value in quantities):
        raise BusinessError("QUANTITY_OUT_OF_RANGE")
