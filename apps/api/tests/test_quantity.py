from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest
from factoryflow.kernel.quantity import QuantityError, confirm_quantity


@pytest.mark.parametrize(
    ("source", "unit", "canonical"),
    [
        ("1", "PCS", "1"),
        ("1.000", "PCS", "1"),
        ("1.125", "KG", "1.125"),
        (" 001.020 ", "m", "1.02"),
        ("0.000", "SET", "0"),
    ],
)
def test_preserves_confirmed_text_and_exact_value(source, unit, canonical):
    result = confirm_quantity(source, unit)
    assert result.source_text == source
    assert result.canonical == canonical
    assert result.value == Decimal(canonical)
    assert result.policy.warning_codes == ()
    with pytest.raises(FrozenInstanceError):
        result.canonical = "2"


@pytest.mark.parametrize("value", [1.125, 1, True, None, Decimal("1.125")])
def test_external_quantity_requires_string(value):
    with pytest.raises(QuantityError, match="QUANTITY_INVALID_TYPE"):
        confirm_quantity(value, "KG")


@pytest.mark.parametrize(
    "value", ["1.2345", "1.0000", "NaN", "Infinity", "1e3", "-1", "+1", "1,000", "", "9" * 80]
)
def test_invalid_source_never_rounds_or_coerces(value):
    with pytest.raises(QuantityError):
        confirm_quantity(value, "KG")


@pytest.mark.parametrize(
    "unit", ["PCS", "PCS.", "PC", "EA", "个", "件", "SET", "套", "台", "箱", "卷"]
)
def test_count_units_reject_fraction(unit):
    with pytest.raises(QuantityError, match="UNIT_REQUIRES_INTEGER_QUANTITY"):
        confirm_quantity("1.125", unit)


@pytest.mark.parametrize("unit", [None, "", "unmapped-unit"])
def test_unknown_unit_is_visible_without_guessing_or_blocking(unit):
    result = confirm_quantity("1.125", unit)
    assert result.policy.mode == "UNKNOWN"
    assert result.policy.canonical_unit is None
    assert result.policy.warning_codes == ("UNIT_PRECISION_UNCONFIRMED",)
    assert result.source_unit == unit


def test_exact_range_boundary():
    assert confirm_quantity("9223372036854775.807", "KG").canonical.endswith(".807")
    with pytest.raises(QuantityError, match="QUANTITY_OUT_OF_RANGE"):
        confirm_quantity("9223372036854775.808", "KG")


def test_unit_revision_revalidates_same_quantity():
    confirmed = confirm_quantity("1.125", None)
    with pytest.raises(QuantityError, match="UNIT_REQUIRES_INTEGER_QUANTITY"):
        confirm_quantity(confirmed.source_text, "PCS")
    assert confirm_quantity("1", "PCS").policy.warning_codes == ()


def test_invalid_unit_type_is_not_stringified():
    with pytest.raises(QuantityError, match="UNIT_INVALID_TYPE"):
        confirm_quantity("1", 42)
