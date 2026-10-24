from factoryflow.modules.documents.adapters.http import Candidate
from factoryflow.modules.documents.domain.candidate import propose


def test_proposal_is_partial_and_never_guesses_customer_price_or_missing_date():
    result = propose(["订单号: SYN-OCR-OOI", "币种: CNY", "Synthetic material 1.125 KG"])
    assert result["order_number"] == "SYN-OCR-OOI"
    assert result["business_date"] == ""
    assert "customer_id" not in result
    assert result["lines"] == [
        {
            "description": "Synthetic material",
            "quantity": "1.125",
            "unit": "KG",
            "source_unit_price": None,
            "source_amount": None,
        }
    ]


def test_ambiguous_table_and_extra_price_columns_are_not_invented():
    result = propose(
        ["Synthetic material 1.125 KG 12.00 13.50", "产品 数量 单位", "订单日期: 2026-02-30", "USD"]
    )
    assert result["lines"] == []
    assert result["business_date"] == ""
    assert result["currency"] == ""


def test_ocr_decimal_punctuation_is_never_silently_dropped():
    for quantity in ("1 · 125", "1 ． 125", "1 , 125", "− 1.125"):
        result = propose([f"Synthetic material {quantity} KG"])
        assert result["lines"][0]["quantity"] == quantity
        assert result["lines"][0]["description"] == "Synthetic material"


def test_candidate_warning_defaults_do_not_rewrite_legacy_candidate_input():
    legacy = {"order_number": "", "business_date": "", "currency": "", "lines": []}
    response = Candidate.model_validate(legacy)
    assert response.warnings == []
    assert "warnings" not in legacy
    current = propose([])
    assert current["warnings"] == []


def test_candidate_warning_dto_preserves_page_and_code_without_business_writes():
    result = propose([])
    result["warnings"] = [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 2}]
    assert Candidate.model_validate(result).model_dump()["warnings"] == result["warnings"]
