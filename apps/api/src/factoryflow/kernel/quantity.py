"""Exact confirmed quantity policy (PRODUCT-SPEC Q01–Q05).

This module performs no I/O and does not authorize a ledger write.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

_FORMAT = re.compile(r"[0-9]+(?:\.[0-9]{1,3})?")
_MAX = Decimal("9223372036854775.807")
_INTEGER_UNITS = {
    "PCS": "PCS",
    "PCS.": "PCS",
    "PC": "PCS",
    "EA": "PCS",
    "个": "PCS",
    "件": "PCS",
    "SET": "SET",
    "套": "SET",
    "台": "台",
    "箱": "箱",
    "卷": "卷",
}
_DECIMAL_UNITS = {
    "KG": "KG",
    "KGS": "KG",
    "公斤": "KG",
    "千克": "KG",
    "G": "G",
    "克": "G",
    "LB": "LB",
    "LBS": "LB",
    "磅": "LB",
    "OZ": "OZ",
    "盎司": "OZ",
    "M": "M",
    "米": "M",
    "MM": "MM",
    "毫米": "MM",
    "CM": "CM",
    "厘米": "CM",
    "KM": "KM",
    "千米": "KM",
    "公里": "KM",
}


class QuantityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class UnitPolicy:
    mode: Literal["INTEGER_ONLY", "DECIMAL_ALLOWED", "UNKNOWN"]
    canonical_unit: str | None
    warning_codes: tuple[str, ...] = ()
    version: str = "unit-policy-v1"


@dataclass(frozen=True)
class ConfirmedQuantity:
    source_text: str
    source_unit: str | None
    value: Decimal
    canonical: str
    policy: UnitPolicy


def confirm_quantity(source_text: str, unit: str | None) -> ConfirmedQuantity:
    """Validate the final human-submitted text without replacing its representation."""
    if not isinstance(source_text, str):
        raise QuantityError("QUANTITY_INVALID_TYPE")
    if unit is not None and not isinstance(unit, str):
        raise QuantityError("UNIT_INVALID_TYPE")
    text = source_text.strip()
    if len(source_text) > 64 or not _FORMAT.fullmatch(text):
        raise QuantityError("QUANTITY_INVALID_FORMAT")
    value = Decimal(text)
    if value > _MAX:
        raise QuantityError("QUANTITY_OUT_OF_RANGE")
    canonical = format(value, "f")
    if "." in canonical:
        canonical = canonical.rstrip("0").rstrip(".")
    alias = unit.strip().upper() if unit is not None else ""
    if alias in _INTEGER_UNITS:
        if value != value.to_integral_value():
            raise QuantityError("UNIT_REQUIRES_INTEGER_QUANTITY")
        policy = UnitPolicy("INTEGER_ONLY", _INTEGER_UNITS[alias])
    elif alias in _DECIMAL_UNITS:
        policy = UnitPolicy("DECIMAL_ALLOWED", _DECIMAL_UNITS[alias])
    else:
        policy = UnitPolicy("UNKNOWN", None, ("UNIT_PRECISION_UNCONFIRMED",))
    return ConfirmedQuantity(source_text, unit, value, canonical, policy)
