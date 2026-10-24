"""Synthetic column evidence for separated identities and explicit source prices."""

from copy import deepcopy

import pytest
from factoryflow.modules.documents.domain.candidate import propose
from factoryflow.modules.documents.domain.table_candidate import exact_header_kind


def layout(headers, values, *, physical=False):
    lines = []
    for y, row in [(0, headers), (40, values)]:
        lines.append(
            {
                "words": [
                    {"text": text, "x": 20 + index * 180, "y": y, "width": 100, "height": 20}
                    for index, text in enumerate(row)
                    if text
                ]
            }
        )
    page = {"lines": lines, "rows": [" ".join(w["text"] for w in line["words"]) for line in lines]}
    if physical:
        page["table_grids"] = [
            {
                "x_edges": [index * 180 for index in range(len(headers) + 1)],
                "y_edges": [-10, 30, 70],
            }
        ]
    return page


def extract(page):
    return propose(page["rows"], pages=[page])["lines"]


@pytest.mark.parametrize("code_header", ["货物编号", "货物编码", "货品编号"])
@pytest.mark.parametrize("physical", [False, True])
def test_common_goods_identity_headers_keep_separate_original_columns(code_header, physical):
    rows = extract(
        layout(
            [code_header, "货物名称", "规格", "数量"],
            ["SYN-GOODS", "合成货物", "M8 / blue", "12"],
            physical=physical,
        )
    )
    assert len(rows) == 1
    assert rows[0]["description"] == "SYN-GOODS 合成货物 M8 / blue"
    assert (rows[0]["item_code"], rows[0]["item_name"], rows[0]["specification"]) == (
        "SYN-GOODS",
        "合成货物",
        "M8 / blue",
    )


@pytest.mark.parametrize("physical", [False, True])
def test_separate_identity_and_explicit_prices_keep_original_strings(physical):
    page = layout(
        ["料号", "品名", "规格", "数量", "单位", "含税单价", "含税金额"],
        ["SYN-A", "合成件", "M8 / 20 blue", "12", "PCS", "02.5000", "30.0000"],
        physical=physical,
    )
    before = deepcopy(page)
    assert extract(page) == [
        {
            "description": "SYN-A 合成件 M8 / 20 blue",
            "item_code": "SYN-A",
            "item_name": "合成件",
            "specification": "M8 / 20 blue",
            "quantity": "12",
            "unit": "PCS",
            "source_unit_price": "02.5000",
            "source_amount": "30.0000",
        }
    ]
    assert page == before


def test_code_spec_only_has_empty_name_and_combined_header_is_never_split():
    row = extract(layout(["料号", "规格", "数量"], ["SYN-A", "M8 / blue", "12"]))[0]
    assert (row["item_code"], row["item_name"], row["specification"]) == ("SYN-A", "", "M8 / blue")
    row = extract(layout(["品名规格", "数量"], ["合成件 / M8 blue", "12"]))[0]
    assert row["description"] == "合成件 / M8 blue"
    assert not {"item_code", "item_name", "specification"} & row.keys()


@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.parametrize(
    "headers,values,expected",
    [
        (["单价", "金额"], ["0", "12.00"], ("0", "12.00")),
        (["Unit Price", "Amount"], ["1.200", "14.400"], ("1.200", "14.400")),
        (["单价", "单价", "金额"], ["1.20", "1.30", "14.40"], (None, "14.40")),
        (["单价", "金额", "金额"], ["1.20", "14.40", "15.60"], ("1.20", None)),
    ],
)
def test_explicit_aliases_and_duplicates_only_blank_ambiguous_price(
    physical, headers, values, expected
):
    rows = extract(layout(["品名", "数量", *headers], ["合成件", "12", *values], physical=physical))
    assert len(rows) == 1
    assert (rows[0]["source_unit_price"], rows[0]["source_amount"]) == expected


@pytest.mark.parametrize(
    "text", ["-1", "+1", "1,25", "1．25", "1 · 25", "1 25", "￥1.25", "1.25税", "1e2"]
)
def test_ambiguous_price_text_stays_empty(text):
    row = extract(layout(["品名", "数量", "单价"], ["合成件", "12", text]))[0]
    assert row["source_unit_price"] is None


@pytest.mark.parametrize("physical", [False, True])
def test_merged_price_cell_does_not_remove_merchandise(physical):
    page = layout(["品名", "数量", "单价", "金额"], ["合成件", "12", "1.25", ""], physical=physical)
    page["lines"][1]["words"][-1]["width"] = 300
    rows = extract(page)
    assert len(rows) == 1
    assert rows[0]["quantity"] == "12"
    assert rows[0]["source_unit_price"] is None and rows[0]["source_amount"] is None


def test_price_only_heading_and_free_text_keep_existing_shape():
    assert extract(layout(["单价", "金额"], ["1.25", "15.00"])) == []
    assert propose(["Synthetic part / M8 12 PCS"])["lines"] == [
        {
            "description": "Synthetic part / M8",
            "quantity": "12",
            "unit": "PCS",
            "source_unit_price": None,
            "source_amount": None,
        }
    ]


def test_header_recovery_helpers_keep_ignored_price_semantics():
    for text in ["单价", "金额", "含税单价"]:
        assert (
            exact_header_kind([{"text": text, "x": 0, "y": 0, "width": 100, "height": 20}])
            == "ignored"
        )


def test_overlong_identity_does_not_silently_truncate_structured_fields():
    row = extract(layout(["料号", "品名", "规格", "数量"], ["S" * 101, "合成件", "M8", "12"]))[0]
    assert not {"item_code", "item_name", "specification"} & row.keys()


@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.parametrize("separate_price", [False, True])
def test_vertically_merged_price_is_not_assigned_to_either_item(physical, separate_price):
    page = layout(
        ["料号", "规格", "数量", "单价"], ["SYN-A", "M8", "12", "1.2500"], physical=physical
    )
    page["lines"][1]["words"][-1]["height"] = 80
    if separate_price:
        page["lines"][1]["words"].append(
            {"text": "2.5000", "x": 560, "y": 40, "width": 100, "height": 20}
        )
    page["lines"].append(
        {
            "words": [
                {"text": text, "x": 20 + index * 180, "y": 80, "width": 100, "height": 20}
                for index, text in enumerate(["SYN-B", "M9", "24"])
            ]
        }
    )
    if physical:
        page["table_grids"][0]["y_edges"].append(110)
    rows = extract(page)
    assert [row["quantity"] for row in rows] == ["12", "24"]
    assert [row["source_unit_price"] for row in rows] == [None, None]


@pytest.mark.parametrize("index,limit", [(0, 100), (1, 500), (2, 1000)])
def test_separated_field_limits_preserve_all_source_characters(index, limit):
    values = ["SYN-A", "合成件", "M8", "12"]
    values[index] = "S" * limit
    row = extract(layout(["料号", "品名", "规格", "数量"], values))[0]
    key = ["item_code", "item_name", "specification"][index]
    assert row[key] == values[index]
    values[index] += "S"
    row = extract(layout(["料号", "品名", "规格", "数量"], values))[0]
    assert not {"item_code", "item_name", "specification"} & row.keys()


def test_unruled_price_crossing_quantity_border_stays_empty_without_losing_item():
    page = layout(["品名", "数量", "单价"], ["合成件", "12", "1.25"])
    # Observed header centers are 70, 250, 430; the quantity/price boundary is 340.
    page["lines"][1]["words"][-1]["x"] = 330
    rows = extract(page)
    assert len(rows) == 1
    assert (rows[0]["description"], rows[0]["quantity"]) == ("合成件", "12")
    assert rows[0]["source_unit_price"] is None


def test_successful_structured_fields_keep_full_legacy_description_projection():
    specification = "S" * 1000
    row = extract(
        layout(["料号", "品名", "规格", "数量"], ["SYN-A", "合成件", specification, "12"])
    )[0]
    assert row["specification"] == specification
    assert row["description"] == f"SYN-A 合成件 {specification}"
    # Plain text retains its existing projection limit.
    assert len(propose([f"{'S' * 600} 12 PCS"])["lines"][0]["description"]) == 500
