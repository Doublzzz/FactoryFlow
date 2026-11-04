"""Synthetic regressions for explicit headers and physical-cell wrapped identities."""

from copy import deepcopy
from io import BytesIO

import pytest
from factoryflow.modules.documents.adapters.purchase_spreadsheet import inspect_purchase_spreadsheet
from factoryflow.modules.documents.domain.candidate import propose
from openpyxl import Workbook


def test_explicit_short_number_label_in_mixed_header():
    rows = ["单号: SYN-MIXED-001 日期:2026-10-28", "供应商: 合成供应商 币种: CNY"]
    original = list(rows)
    candidate = propose(rows)
    assert candidate["order_number"] == "SYN-MIXED-001"
    assert candidate["business_date"] == "2026-10-28"
    assert candidate["currency"] == "CNY"
    assert rows == original


@pytest.mark.parametrize(
    "row",
    [
        "Date: 2026-10-28 Currency: USD",
        "供应商: 合成供应商 币种: CNY",
        "Currency USD Date 2026-10-28",
    ],
)
def test_currency_is_a_complete_explicit_field_with_neighbors(row):
    assert propose([row])["currency"] == ("CNY" if "CNY" in row else "USD")


@pytest.mark.parametrize(
    "rows",
    [
        ["Currency: USD extra"],
        ["Currency:", "USD"],
        ["币种: EUR"],
        ["Currency: USD", "币种: CNY"],
        ["Currency: USD", "币种: EUR"],
        ["Payment Currency: USD"],
        ["备注: 币种: USD"],
        ["Notes: Currency: USD"],
        ["Total amount: USD 25.00"],
    ],
)
def test_currency_is_not_guessed_from_partial_other_or_conflicting_fields(rows):
    assert propose(rows)["currency"] == ""


def test_short_number_does_not_capture_delivery_or_cross_line_codes():
    assert propose(["送货单号: SYN-DELIVERY-001", "单号:", "SYN-NEXT-LINE"])["order_number"] == ""


def test_currency_product_name_is_not_dropped_as_a_header():
    result = propose(["Currency USD Date 2026-10-28", "Currency converter 2 PCS"])
    assert result["currency"] == "USD"
    assert result["business_date"] == "2026-10-28"
    assert len(result["lines"]) == 1
    assert result["lines"][0]["description"] == "Currency converter"
    assert result["lines"][0]["quantity"] == "2"


def test_english_product_name_header_after_metadata_preserves_exact_numeric_text():
    book = Workbook()
    sheet = book.active
    sheet.append(["SYNTHETIC PURCHASE ORDER"])
    sheet.append(["Order No", "SYN-SHEET-001"])
    sheet.append(["Date", "2026-10-28", "", "Currency", "USD"])
    sheet.append(["Supplier", "Synthetic supplier"])
    sheet.append([])
    sheet.append(
        ["Code", "Product Name", "Specification", "Unit", "Quantity", "Unit Price", "Amount"]
    )
    sheet.append(["SYN-A", "Synthetic powder", "Fine", "KG", "0.125", "2.50", "0.31"])
    sheet.append(["SYN-B", "Synthetic sample", "Free sample", "PCS", "2", "0", "0"])
    data = BytesIO()
    book.save(data)
    result = inspect_purchase_spreadsheet(data.getvalue())
    assert result["spreadsheet"]["suggested_mapping"]["header_row"] == 6
    candidate = result["candidate"]
    assert (candidate["order_number"], candidate["business_date"], candidate["currency"]) == (
        "SYN-SHEET-001",
        "2026-10-28",
        "USD",
    )
    assert [
        (line["quantity"], line["source_unit_price"], line["source_amount"])
        for line in candidate["lines"]
    ] == [("0.125", "2.50", "0.31"), ("2", "0", "0")]


def wrapped_page(*, code="SYN-WRAPPED-0", code_width=185, name="合成工业缓冲连接组"):
    def word(text, x, y, width=100, height=22):
        return dict(text=text, x=x, y=y, width=width, height=height)

    xs = [0, 210, 700, 1150, 1270, 1450]
    lines = [
        {
            "words": [
                word(text, xs[i] + 10, 8)
                for i, text in enumerate(["料号", "品名", "规格", "单位", "数量"])
            ]
        }
    ]
    for index, top in enumerate([50, 190]):
        lines.extend(
            [
                {
                    "words": [
                        word(code, 10, top, code_width),
                        word(name, 220, top, 455),
                        word("尺寸 120 x 40 mm", 710, top, 230),
                        word("PCS", 1160, top),
                        word(str(index + 2), 1280, top),
                    ]
                },
                {
                    "words": [
                        word("1", 10, top + 36, 18),
                        word("件", 220, top + 36, 22),
                        word("表面：蓝色", 710, top + 36, 180),
                    ]
                },
                {"words": [word("包装：独立袋", 710, top + 72, 180)]},
            ]
        )
    return {
        "lines": lines,
        "rows": [" ".join(w["text"] for w in line["words"]) for line in lines],
        "table_grids": [{"x_edges": xs, "y_edges": [0, 40, 180, 320]}],
    }


def test_physical_cell_wrap_restores_identity_and_spec_lines_without_merging_records():
    page = wrapped_page()
    original = deepcopy(page)
    lines = propose(page["rows"], pages=[page])["lines"]
    assert len(lines) == 2
    assert [line["quantity"] for line in lines] == ["2", "3"]
    for line in lines:
        assert line["item_code"] == "SYN-WRAPPED-01"
        assert line["item_name"] == "合成工业缓冲连接组件"
        assert line["specification"] == "尺寸 120 x 40 mm\n表面：蓝色\n包装：独立袋"
    assert page == original


def test_short_or_spaced_codes_and_ascii_names_do_not_lose_legitimate_spaces():
    page = wrapped_page(code="AB 12", code_width=75, name="Synthetic washer")
    lines = propose(page["rows"], pages=[page])["lines"]
    assert len(lines) == 2
    assert all(line["item_code"] == "AB 12 1" for line in lines)
    assert all(line["item_name"] == "Synthetic washer 件" for line in lines)
