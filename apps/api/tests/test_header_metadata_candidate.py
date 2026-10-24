"""Synthetic header metadata examples; no OCR inference or business writes."""

import pytest
from factoryflow.modules.documents.domain.candidate import propose


def test_multiple_non_start_headers_keep_raw_rows_and_merchandise():
    rows = [
        "Synthetic supplier 订单编号： Syn_OoI-07.2/A 订单日期：2026-2-3 客户名称：匿名公司",
        "Synthetic material 1.125 KG",
    ]
    original = list(rows)
    result = propose(rows)
    assert result["order_number"] == "Syn_OoI-07.2/A"
    assert result["business_date"] == "2026-02-03"
    assert rows == original
    assert result["lines"] == propose([rows[1]])["lines"]


@pytest.mark.parametrize(
    "label",
    ["订单号", "客户订单号", "采购订单号", "订单编号", "采购单号", "Order No.", "Order Number"],
)
@pytest.mark.parametrize("separator", [": ", "：", "  "])
def test_order_labels_allow_explicit_same_row_value(label, separator):
    assert propose([f"Synthetic header {label}{separator}SYN-007"])["order_number"] == "SYN-007"


@pytest.mark.parametrize(
    "label", ["订单日期", "下单日期", "采购日期", "日期", "Order Date", "Date"]
)
@pytest.mark.parametrize("literal", ["2024-2-29", "2024/2/29", "2024.2.29", "2024年2月29日"])
def test_date_labels_and_calendar_checked_formats(label, literal):
    result = propose([f"Synthetic header {label}: {literal}"])
    assert result["business_date"] == "2024-02-29"


@pytest.mark.parametrize(
    "literal",
    ["2026-2-29", "2026/13/1", "2026.0.3", "2026年4月31日", "2-3", "2026-2-3x", "2026-2-3 4"],
)
def test_invalid_dates_remain_empty(literal):
    assert propose([f"订单日期: {literal}"])["business_date"] == ""


@pytest.mark.parametrize(
    "label", ["交货日期", "送货日期", "签字日期", "发货日期", "预计日期", "Delivery Date", "Update"]
)
def test_other_date_labels_do_not_supply_business_date(label):
    assert propose([f"{label}: 2026-02-03"])["business_date"] == ""


def test_identical_duplicates_allowed_and_conflicts_rejected_globally():
    identical = propose(
        ["订单号: SYN-007", "采购单号: SYN-007", "日期: 2026/2/3", "Order Date: 2026-02-03"]
    )
    assert identical["order_number"] == "SYN-007"
    assert identical["business_date"] == "2026-02-03"
    for rows in (
        ["订单号: SYN-007", "订单号: SYN-008"],
        ["订单号: SYN-007 采购单号: SYN-008"],
    ):
        assert propose(rows)["order_number"] == ""
    for rows in (
        ["日期: 2026-02-03", "订单日期: 2026-02-04"],
        ["订单日期: 2026-02-03 Date: 2026/2/4"],
    ):
        assert propose(rows)["business_date"] == ""


@pytest.mark.parametrize(
    "literal",
    [
        "SYN 007",
        "SYN-007 anonymous customer",
        "SYN-007客户",
        "SYN#007",
        "SYN-007/",
        "-SYN-007",
        "SYN-007;",
        "X" * 101,
    ],
)
def test_malformed_or_continued_codes_are_rejected_without_truncation(literal):
    assert propose([f"订单编号: {literal}"])["order_number"] == ""


def test_bounded_code_and_labeled_following_metadata():
    assert propose([f"订单编号: {'X' * 100}"])["order_number"] == "X" * 100
    assert propose(["订单编号: SYN-007 客户名称: 匿名公司"])["order_number"] == "SYN-007"
    assert propose(["订单编号: SYN-007; 交货日期: 2026-03-01"])["order_number"] == "SYN-007"


def test_no_unlabeled_or_adjacent_row_guesses_or_joined_values():
    result = propose(["SYN-007 2026-02-03", "订单编号:", "SYN-008", "订单日期:", "2026-02-04"])
    assert result["order_number"] == result["business_date"] == ""
    assert propose(["订单编号SYN-007", "订单日期2026-02-03"])["business_date"] == ""
    assert propose(["订单编号SYN-007"])["order_number"] == ""


def test_header_metadata_never_becomes_merchandise_fallback():
    assert propose(["订单编号: SYN-007 12 KG", "订单日期: 2026-02-03 12 KG"])["lines"] == []


def test_whitespace_date_separator_and_page_merchandise_are_preserved():
    rows = ["Synthetic header 订单日期  2026/2/3", "Synthetic material 2 PCS"]
    page = {"number": 1, "rows": rows, "blocks": []}
    result = propose(rows, pages=[page])
    assert result["business_date"] == "2026-02-03"
    assert result["lines"] == propose([rows[1]])["lines"]
