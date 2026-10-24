from decimal import Decimal

import pytest
from factoryflow.kernel.contracts import BusinessError


def calculator():
    from factoryflow.modules.statements.domain.draft import calculate

    return calculate


def line(quantity, price, status="included"):
    return {"quantity": quantity, "unit_price": price, "status": status}


def test_amounts_round_lines_before_total_and_do_not_treat_missing_as_zero():
    calc = calculator()
    result = calc([line("1.125", "2.3456"), line("2", "1.0050")], "untaxed_final", "0", [])
    assert result["line_amounts"] == ["2.64", "2.01"]
    assert result["total"] == "4.65"
    missing = calc([line("2", None), line("1", "0")], "untaxed_final", "0", [])
    assert missing["line_amounts"] == [None, "0.00"]
    assert missing["total"] is None
    assert missing["priced_subtotal"] == "0.00"
    assert "PRICE_REQUIRED" in missing["warnings"]


def test_tax_adjustments_and_inactive_source():
    calc = calculator()
    adjustments = [
        {"stage": "before_tax", "amount": "-10.00", "status": "active"},
        {"stage": "after_tax", "amount": "-2.00", "status": "active"},
    ]
    assert calc([line("1", "100")], "add_tax", "10", adjustments)["total"] == "97.00"
    assert calc([line("1", "100")], "included", "10", adjustments)["total"] == "88.00"
    result = calc([line("1", "100", "source_void")], "add_tax", "10", [])
    assert result["total"] == "0.00"
    adjustments[0]["status"] = "needs_review"
    assert "ADJUSTMENT_REVIEW_REQUIRED" in calc([], "add_tax", "10", adjustments)["warnings"]


def test_price_precision_and_extreme_multiplication_are_exact():
    from factoryflow.modules.statements.domain.draft import price

    assert price("1.2300") == "1.23"
    for value in ["0.12345", "NaN", "1e2", True, 0.1, "-1", "1000000000000"]:
        with pytest.raises(BusinessError):
            price(value)
    result = calculator()(
        [line("9223372036854775.807", "999999999999.9999")], "untaxed_final", "0", []
    )
    assert Decimal(result["total"]) > Decimal("9e27")
