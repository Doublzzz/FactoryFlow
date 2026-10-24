"""Exact lifecycle quantities and deterministic review fingerprints."""

import hashlib
import json
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity
from factoryflow.modules.statements.domain.draft import price


def quantity(value, source=None, *, allow_zero=False):
    result = confirm_quantity(value, (source or {}).get("source_unit"))
    if result.value == 0 and not allow_zero:
        raise BusinessError("STATEMENT_QUANTITY_REQUIRED")
    return result.value


def confirmed_price(value):
    result = price(value)
    if result is None:
        raise BusinessError("STATEMENT_PRICE_REQUIRED")
    return Decimal(result)


def token(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
