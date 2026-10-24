"""Fail when confirmation accepts invalid input or loses the human's source text."""

import importlib.util
from datetime import date

import pytest


def domain():
    name = "factoryflow.modules.orders.domain.order"
    try:
        spec = importlib.util.find_spec(name)
    except ModuleNotFoundError:
        spec = None
    assert spec is not None, "Order confirmation domain is not implemented"
    return __import__(name, fromlist=["prepare_order"])


def payload():
    return {
        "customer_id": "019a0000-0000-7000-8000-000000000001",
        "order_number": " SYN-ORDER-001 ",
        "business_date": "2026-09-30",
        "currency": "CNY",
        "lines": [
            {
                "description": "Synthetic material",
                "quantity": "1.125",
                "unit": "KG",
                "source_unit_price": None,
                "source_amount": "99.00",
            },
            {
                "description": "Synthetic part",
                "quantity": "2.000",
                "unit": "PCS",
                "source_unit_price": "0",
                "source_amount": None,
            },
        ],
    }


def test_confirmation_preserves_source_and_exact_values():
    order = domain().prepare_order(payload())
    assert order.order_number == "SYN-ORDER-001"
    assert order.business_date == date(2026, 9, 30)
    assert order.lines[0].quantity.canonical == "1.125"
    assert order.lines[1].quantity.source_text == "2.000"
    assert order.lines[1].quantity.canonical == "2"
    assert order.lines[0].source_unit_price is None
    assert order.lines[0].source_amount == "99.00"


@pytest.mark.parametrize(
    "quantity,unit,code",
    [
        ("1.125", "PCS", "UNIT_REQUIRES_INTEGER_QUANTITY"),
        ("1.0000", "KG", "QUANTITY_INVALID_FORMAT"),
        (1.125, "KG", "QUANTITY_INVALID_TYPE"),
    ],
)
def test_confirmation_rejects_lossy_quantity(quantity, unit, code):
    data = payload()
    data["lines"][0].update(quantity=quantity, unit=unit)
    with pytest.raises(ValueError) as error:
        domain().prepare_order(data)
    assert error.value.code == code


def test_unknown_unit_warning_is_persistent_evidence():
    data = payload()
    data["lines"][0]["unit"] = ""
    order = domain().prepare_order(data)
    assert order.lines[0].quantity.policy.warning_codes == ("UNIT_PRECISION_UNCONFIRMED",)


@pytest.mark.parametrize(
    "field,value",
    [
        ("customer_id", ""),
        ("currency", ""),
        ("order_number", " "),
        ("lines", []),
        ("business_date", "not-a-date"),
    ],
)
def test_confirmation_requires_explicit_identity_and_content(field, value):
    data = payload()
    data[field] = value
    with pytest.raises(ValueError):
        domain().prepare_order(data)
