"""Catalog identity is optional business metadata, never inventory or order evidence."""

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity


def text_value(value, field, maximum, *, required=False):
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


def prepare_material(payload):
    return {
        "own_code": text_value(payload.get("own_code"), "own_code", 100),
        "name": text_value(payload.get("name"), "name", 500, required=True),
        "specification": text_value(payload.get("specification"), "specification", 1000),
        "unit": text_value(payload.get("unit"), "unit", 40),
    }


def signature(line):
    """Only fields explicitly remembered from this customer's source can match."""
    unit = line.get("source_unit", line.get("unit"))
    return {
        "item_name": text_value(line.get("item_name"), "item_name", 500),
        "specification": text_value(line.get("specification"), "specification", 1000),
        "canonical_unit": confirm_quantity("0", unit).policy.canonical_unit,
    }
