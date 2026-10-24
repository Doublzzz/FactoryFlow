"""Synthetic layouts expose lost columns independently of OCR character accuracy."""

from copy import deepcopy

import pytest
from factoryflow.modules.documents.domain.candidate import propose
from factoryflow.modules.documents.domain.table_candidate import (
    _columns,
    _grid_lines,
    _header_at,
    _quantity_unit_parts,
)


def page(rows):
    lines = []
    for index, cells in enumerate(rows):
        words = [
            {"text": text, "x": x, "y": 40 * index, "width": width, "height": 20}
            for x, width, text in cells
        ]
        lines.append({"words": words})
    return {"lines": lines, "rows": [" ".join(w["text"] for w in r["words"]) for r in lines]}


def extract(layout):
    return propose(layout["rows"], pages=[layout])["lines"]


def subword(text, start, x, width, y=40):
    return {
        "text": text,
        "start": start,
        "end": start + len(text),
        "x": x,
        "y": y,
        "width": width,
        "height": 20,
        "confidence": 0.9,
        "polygon": [[x, y], [x + width, y], [x + width, y + 20], [x, y + 20]],
    }


def merged_layout(number="12", unit="KG", physical=True):
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量"), (500, 40, "单位")],
            [(40, 60, "SYN-A"), (200, 80, "合成材料"), (400, 140, f"{number} {unit}")],
        ]
    )
    word = layout["lines"][1]["words"][2]
    word["subwords"] = [subword(number, 0, 400, 30), subword(unit, len(number) + 1, 500, 40)]
    if physical:
        layout["table_grids"] = [{"x_edges": [20, 160, 360, 480, 600], "y_edges": [-10, 30, 70]}]
    return layout


@pytest.mark.parametrize("physical", [True, False])
@pytest.mark.parametrize("number", ["12", "1,200", "- 1 · 25", "+1.25"])
def test_observed_quantity_unit_parts_in_distinct_columns_preserve_source(physical, number):
    layout = merged_layout(number=number, physical=physical)
    before = deepcopy(layout)
    result = candidate_from(layout)
    assert [(line["quantity"], line["unit"]) for line in result["lines"]] == [(number, "KG")]
    assert result["warnings"] == []
    assert layout == before


def test_quantity_subtokens_union_preserves_numeric_punctuation():
    layout = merged_layout(number="1,200")
    word = layout["lines"][1]["words"][2]
    word["subwords"] = [
        subword("1", 0, 400, 10),
        subword(",", 1, 411, 5),
        subword("200", 2, 420, 30),
        subword("KG", 6, 500, 40),
    ]
    parts = _quantity_unit_parts(
        word, [20, 160, 360, 480, 600], ["item_code", "specification", "quantity", "unit"]
    )
    assert parts[0] == {"text": "1,200", "x": 400, "y": 40, "width": 50, "height": 20}
    assert extract(layout)[0]["quantity"] == "1,200"


@pytest.mark.parametrize(
    "mutation",
    [
        "no-parts",
        "wrong-span",
        "unknown-unit",
        "spec-cell",
        "boundary-overlap",
        "nonfinite",
        "out-of-block",
        "extra-digits",
        "extra-text",
        "missing-punctuation",
        "wrong-polygon",
        "incomplete-unit",
        "reordered",
        "bad-confidence",
    ],
)
def test_unsafe_optional_parts_retain_existing_failure_behavior(mutation):
    layout = merged_layout()
    word = layout["lines"][1]["words"][2]
    if mutation == "no-parts":
        word.pop("subwords")
    elif mutation == "wrong-span":
        word["subwords"][1]["start"] = 2
    elif mutation == "unknown-unit":
        word["text"] = "12 BOXES"
        word["subwords"][1] = subword("BOXES", 3, 500, 40)
    elif mutation == "spec-cell":
        word["x"], word["width"] = 200, 120
        word["subwords"] = [subword("12", 0, 200, 30), subword("KG", 3, 280, 40)]
    elif mutation == "boundary-overlap":
        word["subwords"][0] = subword("12", 0, 460, 30)
    elif mutation == "nonfinite":
        word["subwords"][0]["x"] = float("nan")
    elif mutation == "out-of-block":
        word["subwords"][1] = subword("KG", 3, 550, 40)
    elif mutation == "extra-digits":
        word["text"] = "12 34 KG"
    elif mutation == "extra-text":
        word["text"] = "12 KG extra"
    elif mutation == "missing-punctuation":
        word["text"] = "1,200 KG"
        word["subwords"] = [
            subword("1", 0, 400, 10),
            subword("200", 2, 420, 30),
            subword("KG", 6, 500, 40),
        ]
    elif mutation == "wrong-polygon":
        word["subwords"][0]["polygon"][0][0] = 999
    elif mutation == "incomplete-unit":
        word["subwords"][1] = subword("K", 3, 500, 40)
    elif mutation == "reordered":
        word["subwords"].reverse()
    elif mutation == "bad-confidence":
        word["subwords"][0]["confidence"] = float("inf")
    raw = deepcopy(layout)
    raw["lines"][1]["words"][2].pop("subwords", None)
    assert candidate_from(layout) == candidate_from(raw)


@pytest.mark.parametrize(
    "kinds,xs",
    [
        (["item_code", "quantity", "quantity", "unit"], [20, 160, 360, 480, 600]),
        (["item_code", "specification", "unit", "quantity"], [20, 160, 360, 480, 600]),
        (["item_code", "specification", "quantity", "unit"], [20, 160, 480, 360, 600]),
    ],
)
def test_ambiguous_or_opposite_columns_not_split(kinds, xs):
    word = merged_layout()["lines"][1]["words"][2]
    assert _quantity_unit_parts(word, xs, kinds) is None


def regional_layout(extra):
    header = [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量"), (500, 40, "单位")]
    rows = [header] + [
        [
            (40, 60, f"SYN-{index}"),
            (200, 80, f"合成材料{index}"),
            (400, 30, str(index * 12)),
            (500, 40, "PCS"),
        ]
        for index in range(1, 8)
    ]
    layout = page([*rows, [], *extra])
    layout["table_grids"] = [
        {"x_edges": [20, 160, 360, 480, 600], "y_edges": [-10 + 40 * i for i in range(10)]}
    ]
    layout["number"] = 1
    return layout


def candidate_from(layout):
    return propose(layout["rows"], pages=[layout])


def test_unruled_left_aligned_specification_tail_keeps_record_reading_order():
    layout = page(
        [
            [(40, 40, "料号"), (320, 40, "品名"), (520, 40, "规格"), (680, 40, "数量")],
            [(40, 70, "SYN-A"), (300, 80, "合成名称甲"), (428, 180, "规格主体甲"), (690, 30, "12")],
            [(424, 150, "规格续行甲")],
            [(420, 39, "尾甲")],
            [(40, 70, "SYN-B"), (320, 30, "窄名称乙"), (426, 180, "规格主体乙")],
            [(422, 20, "尾乙")],
        ]
    )
    for line, y in zip(layout["lines"], [0, 40, 65, 90, 160, 185], strict=True):
        for word in line["words"]:
            word["y"] = y
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"]) for r in result["lines"]] == [
        ("SYN-A 合成名称甲 规格主体甲 规格续行甲 尾甲", "12"),
        ("SYN-B 窄名称乙 规格主体乙 尾乙", ""),
    ]
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_unruled_missing_spec_label_uses_resolved_wide_identity_not_quantity():
    layout = page(
        [
            [
                (40, 40, "料号"),
                (288, 40, "品名"),
                (646, 40, "数量"),
                (750, 40, "单位"),
                (860, 40, "金额"),
            ],
            [
                (40, 70, "SYN-A"),
                (280, 90, "合成甲"),
                (390, 220, "合成宽规格甲"),
                (663, 42, "12"),
                (750, 40, "PCS"),
                (860, 50, "24.00"),
            ],
            [
                (40, 70, "SYN-B"),
                (280, 90, "合成乙"),
                (390, 227, "合成宽规格乙"),
                (663, 42, "24"),
                (750, 40, "KG"),
                (860, 50, "48.00"),
            ],
        ]
    )
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-A 合成甲合成宽规格甲", "12", "PCS"),
        ("SYN-B 合成乙合成宽规格乙", "24", "KG"),
    ]
    assert [r["source_amount"] for r in result["lines"]] == ["24.00", "48.00"]


def test_unruled_wide_identity_without_quantity_keeps_known_record_and_warning():
    layout = page(
        [
            [(40, 40, "料号"), (288, 40, "品名"), (646, 40, "数量"), (750, 40, "单位")],
            [
                (40, 70, "SYN-A"),
                (280, 90, "合成甲"),
                (390, 220, "合成宽规格甲"),
                (663, 42, "12"),
                (750, 40, "PCS"),
            ],
            [(40, 70, "SYN-B"), (280, 90, "合成乙"), (390, 227, "合成宽规格乙"), (750, 40, "KG")],
        ]
    )
    original = deepcopy(layout)
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-A 合成甲合成宽规格甲", "12", "PCS"),
        ("SYN-B 合成乙", "", "KG"),
    ]
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]
    assert layout == original


def test_borrowed_neighbor_geometry_does_not_silently_certify_clause_as_specification():
    layout = page(
        [
            [(160, 40, "料号"), (324, 40, "品名"), (524, 40, "规格"), (678, 40, "数量")],
            [(97, 128, "SYN-A"), (259, 100, "合成名称"), (426, 180, "合成规格"), (695, 42, "12")],
            [(426, 212, "交付约定含24 PCS须核对")],
        ]
    )
    original = deepcopy(layout)
    result = candidate_from(layout)
    assert len(result["lines"]) == 1
    assert result["lines"][0]["quantity"] == "12"
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]
    assert layout == original


def test_wide_description_center_does_not_create_code_anchor_before_lower_real_code():
    layout = page(
        [
            [
                (123, 40, "序号"),
                (268, 40, "料号"),
                (628, 40, "品名"),
                (945.5, 40, "数量"),
                (1056, 40, "单位"),
                (1181, 40, "单价"),
                (1345.5, 40, "金额"),
            ],
            [
                (436, 432, "合成宽名称甲"),
                (956, 26, "12"),
                (1061, 38, "PCS"),
                (212, 159, "SYN-CODE-A"),
            ],
            [
                (450, 414, "合成宽名称乙"),
                (962, 24, "24"),
                (1066, 37, "KG"),
                (211, 172, "SYN-CODE-B"),
            ],
        ]
    )
    for line, geometry in zip(
        layout["lines"][1:],
        [
            [(432, 43), (430, 31), (424, 35), (445, 39)],
            [(578, 43), (574, 32), (568, 36), (588, 40)],
        ],
        strict=True,
    ):
        for word, (y, height) in zip(line["words"], geometry, strict=True):
            word.update(y=y, height=height)
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-CODE-A 合成宽名称甲", "12", "PCS"),
        ("SYN-CODE-B 合成宽名称乙", "24", "KG"),
    ]


def test_unruled_record_preserves_prefix_middle_and_tail_with_adjacent_quantity_evidence():
    layout = page(
        [
            [(160.5, 40, "料号"), (324, 40, "品名"), (524, 40, "规格"), (678.5, 40, "数量")],
            [(262, 102, "名称首行"), (426, 210, "规格首行")],
            [(97, 128, "SYN-A"), (259, 165, "名称中行"), (423, 214, "规格中行"), (695, 42, "12")],
            [(260, 34, "名尾"), (424, 57, "规格尾")],
        ]
    )
    geometries = [
        [(424, 23), (422, 24)],
        [(445, 20), (442, 26), (441, 24), (441, 23)],
        [(461, 24), (461, 24)],
    ]
    for line, geometry in zip(layout["lines"][1:], geometries, strict=True):
        for word, (y, height) in zip(line["words"], geometry, strict=True):
            word.update(y=y, height=height)
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"]) for r in result["lines"]] == [
        ("SYN-A 名称首行 名称中行 名尾 规格首行 规格中行 规格尾", "12")
    ]


def test_unruled_multiple_wrapped_prefixes_and_tails_keep_all_observed_spec_text():
    layout = page(
        [
            [(152, 40, "料号"), (315, 40, "品名"), (512, 40, "规格"), (665, 40, "数量")],
            [(414, 230, "规格前行一")],
            [(417, 222, "规格前行二")],
            [(89, 128, "SYN-A"), (249, 105, "合成名称"), (417, 170, "规格锚行"), (690, 34, "12")],
            [(415, 212, "规格后行一")],
            [(415, 142, "规格后行二")],
        ]
    )
    for line, y in zip(layout["lines"][1:], [920, 942, 962, 980, 998], strict=True):
        for word in line["words"]:
            word["y"] = y
            word["height"] = 24
    assert candidate_from(layout)["lines"][0]["description"] == (
        "SYN-A 合成名称 规格前行一 规格前行二 规格锚行 规格后行一 规格后行二"
    )


@pytest.mark.parametrize("tail_x,tail_width", [(426, 300), (40, 800)])
def test_neighbor_quantity_does_not_authorize_overlapping_or_unaligned_prose(tail_x, tail_width):
    layout = page(
        [
            [(160, 40, "料号"), (324, 40, "品名"), (524, 40, "规格"), (678, 40, "数量")],
            [(97, 128, "SYN-A"), (259, 100, "合成名称"), (426, 180, "合成规格"), (695, 42, "12")],
            [(tail_x, tail_width, "合成约定含24 PCS不能并入商品")],
        ]
    )
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"]) for r in result["lines"]] == [
        ("SYN-A 合成名称 合成规格", "12")
    ]
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


@pytest.mark.parametrize("evidence", ["none", "distant", "competing_description"])
def test_short_description_without_unambiguous_spec_continuity_stays_description(evidence):
    anchor = [(40, 70, "SYN-A"), (690, 30, "12")]
    if evidence != "none":
        anchor.append((428, 180, "规格主体"))
    if evidence == "competing_description":
        anchor.append((420, 20, "名称"))
    layout = page(
        [
            [(40, 40, "料号"), (320, 40, "品名"), (520, 40, "规格"), (680, 40, "数量")],
            anchor,
            [(420, 20, "短名称")],
        ]
    )
    if evidence == "distant":
        layout["lines"][2]["words"][0]["y"] = 150
    expected = "SYN-A " + ("名称 " if evidence == "competing_description" else "") + "短名称"
    if evidence != "none":
        expected += " 规格主体"
    assert candidate_from(layout)["lines"][0]["description"] == expected


def test_wide_name_code_ownership_and_second_unruled_table_survive_numeric_clauses():
    layout = page(
        [
            [
                (40, 40, "料号"),
                (320, 40, "品名"),
                (520, 40, "规格"),
                (680, 40, "数量"),
                (780, 40, "单位"),
            ],
            [
                (40, 160, "SYN-LONG-CODE"),
                (300, 320, "合成宽名称"),
                (690, 30, "12"),
                (780, 40, "PCS"),
            ],
            [(40, 70, "SYN-B"), (320, 30, "窄名称"), (428, 180, "规格主体")],
            [(420, 20, "尾")],
            [(40, 60, "合计"), (690, 30, "12")],
            [(40, 800, "合成条款数字24 KG不可作为业务数量")],
            [(40, 800, "合成条款续行12 PCS仍为约定")],
            [(100, 40, "品名"), (400, 40, "数量"), (600, 40, "单位")],
            [(100, 100, "合成第二表"), (400, 30, "8"), (600, 40, "KG")],
        ]
    )
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-LONG-CODE 合成宽名称", "12", "PCS"),
        ("SYN-B 窄名称 规格主体 尾", "", ""),
        ("合成第二表", "8", "KG"),
    ]


def test_resolved_seven_rows_survive_blank_band_and_continuous_wide_contract_paragraph():
    base = candidate_from(regional_layout([]))["lines"]
    layout = regional_layout(
        [
            [(40, 180, "合成约定说明")],
            [(40, 750, "合成约定第一行包含12 PCS和日期2026-10-04")],
            [(40, 750, "合成约定第二行包含24 KG和数字100")],
        ]
    )
    assert candidate_from(layout)["lines"] == base


def test_independent_table_after_total_and_paragraph_is_parsed_without_duplicates():
    layout = regional_layout(
        [
            [(40, 80, "合计"), (400, 40, "336")],
            [(40, 180, "合成约定说明")],
            [(40, 750, "合成条款12 PCS待核对")],
            [(40, 750, "合成条款24 KG待核对")],
            [(80, 80, "品名"), (400, 40, "数量"), (600, 40, "单位")],
            [(80, 100, "合成后表甲"), (400, 30, "8"), (600, 40, "KG")],
            [(80, 100, "合成后表乙"), (400, 30, "9"), (600, 40, "KG")],
        ]
    )
    result = candidate_from(layout)
    assert len(result["lines"]) == 9
    assert [r["quantity"] for r in result["lines"]] == [
        "12",
        "24",
        "36",
        "48",
        "60",
        "72",
        "84",
        "8",
        "9",
    ]


@pytest.mark.parametrize("quantity", [None, "", "12", "12 34"])
@pytest.mark.parametrize("after_footer", [False, True])
def test_uncovered_code_and_spec_row_is_preserved_including_missing_quantity(
    quantity, after_footer
):
    extra = [[(40, 180, "制单：合成人")]] if after_footer else []
    extra.append(
        [(40, 60, "SYN-EXTRA"), (200, 80, "合成补行")]
        + ([] if quantity is None else [(400, 40, quantity)])
    )
    result = candidate_from(regional_layout(extra))
    if after_footer:
        assert len(result["lines"]) == 7
        assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]
        return
    assert len(result["lines"]) == 8
    assert result["lines"][-1]["description"] == "SYN-EXTRA 合成补行"
    assert result["lines"][-1]["quantity"] == (quantity or "")


def test_true_wide_identity_with_separate_quantity_is_not_contract_prose():
    result = candidate_from(
        regional_layout(
            [
                [(40, 60, "SYN-WIDE"), (200, 190, "合成宽规格材料"), (430, 30, "12")],
            ]
        )
    )
    assert len(result["lines"]) == 8
    assert result["lines"][-1]["description"] == "SYN-WIDE 合成宽规格材料"
    assert result["lines"][-1]["quantity"] == "12"


def test_isolated_ambiguous_identity_surfaces_coverage_warning_without_inventing_row():
    result = candidate_from(regional_layout([[(40, 60, "待核对")]]))
    assert len(result["lines"]) == 7
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_cross_bottom_ocr_box_keeps_resolved_rows_and_reports_uncertainty():
    layout = regional_layout([])
    layout["lines"][-2]["words"][1]["height"] = 110
    result = candidate_from(layout)
    assert result["lines"][:6] == candidate_from(regional_layout([]))["lines"][:6]
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_unruled_header_midpoints_are_not_physical_walls_for_wide_item_code():
    layout = page(
        [
            [(40, 40, "料号"), (200, 40, "规格"), (400, 40, "数量"), (600, 40, "单位")],
            [
                (40, 160, "SYN-WIDE-CODE"),
                (200, 200, "合成宽规格"),
                (420, 30, "12"),
                (600, 40, "PCS"),
            ],
            [
                (40, 160, "SYN-WIDE-NEXT"),
                (200, 200, "合成宽规格乙"),
                (420, 30, "24"),
                (600, 40, "PCS"),
            ],
        ]
    )
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-WIDE-CODE 合成宽规格", "12", "PCS"),
        ("SYN-WIDE-NEXT 合成宽规格乙", "24", "PCS"),
    ]


def test_ignored_amount_box_crossing_only_ignored_price_border_preserves_business_rows():
    layout = page(
        [
            [
                (40, 40, "料号"),
                (200, 40, "规格"),
                (400, 40, "数量"),
                (500, 40, "单位"),
                (620, 40, "单价"),
                (720, 40, "金额"),
            ],
            [
                (40, 80, "SYN-A"),
                (200, 80, "合成甲"),
                (400, 30, "12"),
                (500, 40, "PCS"),
                (620, 40, "2.00"),
                (698, 80, "24.00"),
            ],
            [
                (40, 80, "SYN-B"),
                (200, 80, "合成乙"),
                (400, 30, "24"),
                (500, 40, "PCS"),
                (620, 40, "2.00"),
                (697, 82, "48.00"),
            ],
        ]
    )
    layout["table_grids"] = [
        {"x_edges": [20, 160, 360, 480, 600, 700, 800], "y_edges": [-10, 30, 70, 110]}
    ]
    result = candidate_from(layout)
    assert [(r["description"], r["quantity"], r["unit"]) for r in result["lines"]] == [
        ("SYN-A 合成甲", "12", "PCS"),
        ("SYN-B 合成乙", "24", "PCS"),
    ]
    assert all(
        r["source_unit_price"] is None and r["source_amount"] is None for r in result["lines"]
    )
    layout["lines"][2]["words"][2].update(x=470, width=40)
    ambiguous = candidate_from(layout)
    assert len(ambiguous["lines"]) == 1
    assert ambiguous["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_footer_context_does_not_turn_column_aligned_clause_into_merchandise():
    layout = regional_layout(
        [
            [(40, 180, "制单：合成人")],
            [(40, 60, "交货要求"), (200, 80, "每批发货"), (400, 40, "12"), (500, 40, "PCS")],
        ]
    )
    result = candidate_from(layout)
    assert len(result["lines"]) == 7
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_explicit_grid_item_code_survives_missing_specification_and_quantity():
    layout = regional_layout([])
    layout["lines"][3]["words"] = [layout["lines"][3]["words"][0], layout["lines"][3]["words"][-1]]
    result = candidate_from(layout)
    assert len(result["lines"]) == 7
    assert result["lines"][2]["description"] == "SYN-3"
    assert result["lines"][2]["quantity"] == ""
    assert result["lines"][2]["unit"] == "PCS"
    assert result["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


@pytest.mark.parametrize(
    "identity_header",
    [
        [(100, 80, "品名规格")],
        [(100, 80, "货品规格")],
        [(100, 90, "品名/规格")],
        [(100, 40, "品名"), (143, 40, "规格")],
        [(100, 40, "货品"), (143, 40, "规格")],
        [(100, 20, "货"), (122, 20, "品"), (144, 20, "规"), (166, 20, "格")],
    ],
)
def test_compound_identity_spec_header_is_one_description_column(identity_header):
    layout = page(
        [
            identity_header + [(500, 40, "数量"), (650, 40, "单位"), (800, 40, "金额")],
            [
                (100, 100, "合成材料甲"),
                (220, 100, "M8×20 I/l"),
                (500, 50, "1,125"),
                (650, 40, "PCS"),
                (800, 50, "90.00"),
            ],
        ]
    )
    columns, _, _ = _columns([layout["lines"][0]["words"]])
    assert [kind for kind, _ in columns] == ["description", "quantity", "unit", "source_amount"]
    assert extract(layout) == [
        {
            "description": "合成材料甲 M8×20 I/l",
            "quantity": "1,125",
            "unit": "PCS",
            "source_unit_price": None,
            "source_amount": "90.00",
        }
    ]


def test_separate_identity_and_spec_headers_remain_separate_columns():
    # A 15-pixel gap is permitted for existing split labels, but these are two
    # complete labels rather than tightly spaced parts of a compound heading.
    layout = page(
        [
            [(100, 40, "品名"), (155, 40, "规格"), (500, 40, "数量")],
            [(100, 40, "合成甲"), (155, 40, "M8×20"), (500, 30, "12")],
        ]
    )
    columns, _, _ = _columns([layout["lines"][0]["words"]])
    assert [kind for kind, _ in columns] == ["description", "specification", "quantity"]
    assert extract(layout)[0]["description"] == "合成甲 M8×20"
    assert extract(layout)[0]["unit"] == ""


@pytest.mark.parametrize("observed_quantity", ["1,125", "12 34"])
def test_grid_uses_wide_physical_cells_wraps_rows_and_excludes_external_footer(observed_quantity):
    layout = page(
        [
            [(40, 40, "料号"), (140, 80, "品名规格"), (700, 40, "数量"), (800, 40, "单位")],
            [
                (40, 50, "SYN-A"),
                (140, 100, "合成材料"),
                (700, 40, observed_quantity),
                (800, 30, "PCS"),
            ],
            [(560, 90, "M8×20 I/l")],
            [(40, 50, "SYN-B"), (140, 100, "合成零件"), (800, 30, "KG")],
            [(40, 70, "签收人"), (140, 100, "合成页脚")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 120, 680, 780, 880], "y_edges": [-10, 30, 110, 150]}]
    assert extract(layout) == [
        {
            "description": "SYN-A 合成材料 M8×20 I/l",
            "item_code": "SYN-A",
            "item_name": "合成材料 M8×20 I/l",
            "specification": None,
            "quantity": observed_quantity,
            "unit": "PCS",
            "source_unit_price": None,
            "source_amount": None,
        },
        {
            "description": "SYN-B 合成零件",
            "item_code": "SYN-B",
            "item_name": "合成零件",
            "specification": None,
            "quantity": "",
            "unit": "KG",
            "source_unit_price": None,
            "source_amount": None,
        },
    ]


def test_grid_rejects_duplicate_quantity_and_falls_back_for_ineligible_header():
    layout = page(
        [
            [(40, 40, "品名"), (200, 40, "数量"), (360, 40, "数量")],
            [(40, 80, "合成材料"), (200, 20, "10"), (360, 20, "20")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 160, 320, 480], "y_edges": [-10, 30, 70]}]
    assert extract(layout) == []
    plain = page([[(40, 160, "Synthetic material 3 PCS")]])
    expected = extract(plain)
    plain["table_grids"] = [{"x_edges": [20, 200, 400], "y_edges": [-10, 30, 70]}]
    assert extract(plain) == expected


def test_grid_keeps_truly_separate_name_and_specification_cells():
    layout = page(
        [
            [(40, 40, "品名"), (200, 40, "规格"), (360, 40, "数量")],
            [(40, 80, "合成材料"), (200, 80, "M8×20"), (360, 20, "12")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 160, 320, 480], "y_edges": [-10, 30, 70]}]
    assert extract(layout)[0] == {
        "description": "合成材料 M8×20",
        "item_code": None,
        "item_name": "合成材料",
        "specification": "M8×20",
        "quantity": "12",
        "unit": "",
        "source_unit_price": None,
        "source_amount": None,
    }


@pytest.mark.parametrize("uncovered_quantity", ["24", ""])
def test_partial_manual_grid_preserves_extra_genuine_row(uncovered_quantity):
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量")],
            [(40, 60, "SYN-A"), (200, 80, "合成甲"), (400, 30, "12")],
            [(40, 60, "SYN-B"), (200, 80, "合成乙"), (400, 30, uncovered_quantity)],
        ]
    )
    expected = extract(layout)
    layout["table_grids"] = [{"x_edges": [20, 160, 360, 480], "y_edges": [-10, 30, 70]}]
    assert len(_grid_lines(layout)) == 2
    assert extract(layout) == expected
    assert len(expected) == 2


def test_mixed_unruled_second_table_is_parsed_as_an_independent_region():
    layout = page(
        [
            [(40, 80, "品名"), (300, 40, "数量"), (500, 40, "单位")],
            [(40, 100, "合成甲"), (300, 30, "12"), (500, 40, "PCS")],
            [(80, 80, "品名"), (400, 40, "数量"), (600, 40, "单位")],
            [(80, 100, "合成乙"), (400, 30, "24"), (600, 40, "KG")],
        ]
    )
    expected = extract(layout)
    layout["table_grids"] = [{"x_edges": [20, 260, 460, 560], "y_edges": [-10, 30, 70]}]
    assert len(_grid_lines(layout)) == 2
    assert extract(layout) == expected
    assert len(expected) == 2


def test_incomplete_grid_band_excludes_merged_summary_and_warns_for_unknown_content():
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量")],
            [(40, 60, "SYN-A"), (200, 80, "合成甲"), (400, 30, "12")],
            [(40, 80, "合计"), (400, 30, "12")],
        ]
    )
    layout["table_grids"] = [
        {
            "x_edges": [20, 160, 360, 480],
            "y_edges": [-10, 30, 70, 110],
            "row_complete": [True, True, False],
        }
    ]
    assert len(extract(layout)) == 1
    layout["lines"][-1]["words"][0]["text"] = "待核对内容"
    layout["lines"][-1]["words"][-1]["x"] = 200
    assert len(_grid_lines(layout)) == 1
    assert candidate_from(layout)["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


def test_grid_coverage_allows_document_title_order_date_and_explicit_footer_region():
    layout = page(
        [
            [(40, 200, "合成采购订单")],
            [(40, 200, "订单号：SYN-2026-001")],
            [(40, 200, "日期：2026-10-04")],
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量")],
            [(40, 60, "SYN-A"), (200, 80, "合成甲"), (400, 30, "12")],
            [(40, 200, "制单：合成人 审核：合成人")],
            [(40, 200, "本页用于合成核对说明")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 160, 360, 480], "y_edges": [110, 150, 190]}]
    assert _grid_lines(layout) == [
        {
            "description": "SYN-A 合成甲",
            "item_code": "SYN-A",
            "item_name": "",
            "specification": "合成甲",
            "quantity": "12",
            "unit": "",
            "source_unit_price": None,
            "source_amount": None,
        }
    ]


def test_grid_coverage_preserves_earlier_genuine_independent_table():
    layout = page(
        [
            [(40, 80, "品名"), (300, 40, "数量"), (500, 40, "单位")],
            [(40, 100, "合成甲"), (300, 30, "12"), (500, 40, "PCS")],
            [(40, 200, "日期：2026-10-04")],
            [(80, 80, "品名"), (400, 40, "数量"), (600, 40, "单位")],
            [(80, 100, "合成乙"), (400, 30, "24"), (600, 40, "KG")],
        ]
    )
    expected = extract(layout)
    layout["table_grids"] = [{"x_edges": [20, 360, 560, 680], "y_edges": [110, 150, 190]}]
    assert len(_grid_lines(layout)) == 2
    assert extract(layout) == expected


def test_independent_table_after_explicit_footer_is_recovered_separately():
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量")],
            [(40, 60, "SYN-A"), (200, 80, "合成甲"), (400, 30, "12")],
            [(40, 200, "制单：合成人 审核：合成人")],
            [(80, 80, "品名"), (400, 40, "数量"), (600, 40, "单位")],
            [(80, 100, "合成乙"), (400, 30, "24"), (600, 40, "KG")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 160, 360, 480], "y_edges": [-10, 30, 70]}]
    assert len(_grid_lines(layout)) == 2


def test_identity_and_specification_after_footer_are_unresolved_without_new_header():
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量")],
            [(40, 60, "SYN-A"), (200, 80, "合成甲"), (400, 30, "12")],
            [(40, 200, "制单：合成人 审核：合成人")],
            [(40, 60, "SYN-B"), (200, 80, "合成乙"), (400, 30, "24")],
        ]
    )
    layout["table_grids"] = [{"x_edges": [20, 160, 360, 480], "y_edges": [-10, 30, 70]}]
    assert len(_grid_lines(layout)) == 1
    assert candidate_from(layout)["warnings"] == [{"code": "TABLE_COVERAGE_UNRESOLVED", "page": 1}]


@pytest.mark.parametrize("metadata", ["日期：2026-10-04", "币种：CNY", "订单号：SYN-2026-001"])
@pytest.mark.parametrize("metadata_position", [(40, 200), (1100, 100)])
def test_metadata_row_does_not_swallow_stronger_complete_header(metadata, metadata_position):
    x, width = metadata_position
    layout = page(
        [
            [(x, width, metadata)],
            [
                (40, 80, "料号"),
                (200, 80, "品名"),
                (360, 80, "规格"),
                (520, 40, "数量"),
                (660, 40, "单位"),
                (780, 40, "单价"),
                (900, 40, "金额"),
            ],
            [
                (40, 80, "SYN-A"),
                (200, 80, "合成甲"),
                (360, 80, "M8×20"),
                (520, 30, "12"),
                (660, 40, "PCS"),
                (780, 40, "2.00"),
                (900, 40, "24.00"),
            ],
        ]
    )
    rows = [line["words"] for line in layout["lines"]]
    assert _header_at(rows, 0)[0] is None
    header, _ = _header_at(rows, 1)
    assert header[1] == 1
    assert extract(layout) == [
        {
            "description": "SYN-A 合成甲 M8×20",
            "item_code": "SYN-A",
            "item_name": "合成甲",
            "specification": "M8×20",
            "quantity": "12",
            "unit": "PCS",
            "source_unit_price": "2.00",
            "source_amount": "24.00",
        }
    ]


def test_table_uses_headers_not_last_number_with_price_and_amount_columns():
    layout = page(
        [
            [
                (0, 40, "序号"),
                (100, 80, "产品名称"),
                (320, 40, "规格"),
                (500, 40, "单位"),
                (600, 40, "数量"),
                (720, 40, "单价"),
                (850, 40, "金额"),
            ],
            [
                (0, 10, "1"),
                (100, 120, "合成材料甲"),
                (320, 70, "M8×20"),
                (500, 25, "KG"),
                (600, 50, "1.125"),
                (720, 50, "12.00"),
                (850, 50, "13.50"),
            ],
            [
                (0, 10, "2"),
                (100, 120, "合成零件乙"),
                (320, 70, "B-200"),
                (500, 30, "PCS"),
                (600, 20, "25"),
                (720, 50, "2.00"),
                (850, 50, "50.00"),
            ],
            [(100, 40, "合计"), (600, 60, "26.125"), (850, 50, "63.50")],
        ]
    )
    assert extract(layout) == [
        {
            "description": "合成材料甲 M8×20",
            "item_code": None,
            "item_name": "合成材料甲",
            "specification": "M8×20",
            "quantity": "1.125",
            "unit": "KG",
            "source_unit_price": "12.00",
            "source_amount": "13.50",
        },
        {
            "description": "合成零件乙 B-200",
            "item_code": None,
            "item_name": "合成零件乙",
            "specification": "B-200",
            "quantity": "25",
            "unit": "PCS",
            "source_unit_price": "2.00",
            "source_amount": "50.00",
        },
    ]


def test_split_chinese_headers_and_decimal_punctuation_are_preserved():
    layout = page(
        [
            [
                (40, 20, "品"),
                (61, 20, "名"),
                (300, 20, "数"),
                (321, 20, "量"),
                (500, 20, "单"),
                (521, 20, "位"),
            ],
            [
                (40, 90, "合成材料"),
                (300, 10, "1"),
                (313, 8, "·"),
                (324, 30, "125"),
                (500, 25, "KG"),
            ],
        ]
    )
    result = extract(layout)
    assert len(result) == 1
    assert result[0]["quantity"] == "1 · 125"
    assert result[0]["description"] == "合成材料"


def test_missing_unit_stays_empty_and_repeated_headers_are_not_items():
    header = [(40, 100, "Description"), (400, 40, "Qty"), (600, 70, "Amount")]
    layout = page(
        [
            header,
            [(40, 150, "Synthetic part"), (400, 20, "12"), (600, 50, "90.00")],
            header,
            [(40, 150, "Synthetic material"), (400, 30, "2.5"), (600, 50, "20.00")],
        ]
    )
    result = extract(layout)
    assert [(r["quantity"], r["unit"]) for r in result] == [("12", ""), ("2.5", "")]


def test_duplicate_quantity_columns_are_ambiguous_not_last_column_wins():
    layout = page(
        [
            [(40, 50, "品名"), (250, 50, "数量"), (400, 50, "数量"), (600, 50, "单位")],
            [(40, 80, "合成材料"), (250, 20, "10"), (400, 20, "20"), (600, 20, "KG")],
        ]
    )
    assert extract(layout) == []


def test_table_coordinates_do_not_leak_into_next_page_without_a_header():
    first = page(
        [
            [(40, 50, "品名"), (300, 50, "数量"), (500, 50, "单位")],
            [(40, 80, "合成材料"), (300, 20, "10"), (500, 20, "KG")],
        ]
    )
    second = page([[(40, 120, "Synthetic part 3 PCS")]])
    result = propose(first["rows"] + second["rows"], pages=[first, second])
    assert [r["quantity"] for r in result["lines"]] == ["10", "3"]


def test_contact_and_unknown_unit_are_not_fallback_items():
    assert (
        propose(
            [
                "TEL: 0000 - 1234567 FAX: 0000 PCS",
                "联系电话: 0000 1234567 KG",
                "Synthetic wire UL999 007 红",
                "Synthetic coating 2 皿镀",
            ]
        )["lines"]
        == []
    )


def test_unrecognized_table_never_scans_specification_lines_as_free_text_items():
    layout = page(
        [
            [(20, 100, "物料编号"), (250, 100, "型号规格"), (500, 50, "单位")],
            [(20, 100, "SYN-A"), (250, 170, "Synthetic wire 8 MM"), (500, 30, "PCS")],
            [(250, 170, "Synthetic wire 8 MM")],
        ]
    )
    assert extract(layout) == []


def test_code_spec_table_wraps_four_business_rows_and_skips_contact_and_footer():
    layout = page(
        [
            [(20, 350, "TEL: 0000 - 1234567 FAX: 0000 PCS")],
            [
                (20, 80, "物料编号"),
                (250, 80, "型号规格"),
                (500, 20, "单"),
                (620, 80, "订购数量"),
                (800, 40, "含税"),
            ],
            [(500, 20, "位"), (800, 40, "金额")],
            [(250, 150, "Synthetic wire alpha")],
            [
                (20, 100, "SYN-A101"),
                (250, 150, "insulation 6 MM"),
                (500, 30, "PCS"),
                (620, 40, "120"),
                (800, 50, "60.00"),
            ],
            [(250, 150, "red coating")],
            [(250, 150, "Synthetic wire beta")],
            [
                (20, 100, "SYN-A102"),
                (250, 150, "insulation 7 MM"),
                (500, 30, "PCS"),
                (620, 40, "240"),
                (800, 50, "80.00"),
            ],
            [(250, 150, "black coating")],
            [(250, 150, "Synthetic wire gamma")],
            [
                (20, 100, "SYN-A103"),
                (250, 150, "insulation 9 MM"),
                (500, 30, "PCS"),
                (620, 40, "360"),
                (800, 50, "90.00"),
            ],
            [(250, 150, "blue coating")],
            [(250, 150, "Synthetic wire delta")],
            [
                (20, 100, "SYN-A104"),
                (250, 150, "insulation 3 MM"),
                (500, 30, "PCS"),
                (620, 40, "480"),
                (800, 50, "100.00"),
            ],
            [(250, 150, "yellow coating")],
            [(250, 100, "以下空白")],
            [(250, 100, "合计"), (800, 50, "330.00")],
            [(20, 350, "备注: Synthetic terms 999 PCS")],
        ]
    )
    result = extract(layout)
    assert [(r["quantity"], r["unit"]) for r in result] == [
        ("120", "PCS"),
        ("240", "PCS"),
        ("360", "PCS"),
        ("480", "PCS"),
    ]
    assert result[0]["description"] == "SYN-A101 Synthetic wire alpha insulation 6 MM red coating"
    assert (
        result[3]["description"] == "SYN-A104 Synthetic wire delta insulation 3 MM yellow coating"
    )
    assert [r["source_amount"] for r in result] == ["60.00", "80.00", "90.00", "100.00"]


def test_missing_quantity_does_not_merge_an_identified_row_into_its_neighbor():
    layout = page(
        [
            [(20, 100, "物料编号"), (250, 100, "型号规格"), (500, 50, "数量"), (700, 40, "单位")],
            [(20, 100, "SYN-A"), (250, 100, "Synthetic red"), (500, 40, "12"), (700, 30, "PCS")],
            [(20, 100, "SYN-B"), (250, 100, "Synthetic blue"), (700, 30, "PCS")],
            [(20, 100, "SYN-C"), (250, 100, "Synthetic gold"), (500, 40, "36"), (700, 30, "PCS")],
        ]
    )
    result = extract(layout)
    assert [(r["description"], r["quantity"]) for r in result] == [
        ("SYN-A Synthetic red", "12"),
        ("SYN-B Synthetic blue", ""),
        ("SYN-C Synthetic gold", "36"),
    ]


def test_tall_heading_cannot_chain_neighboring_text_rows_into_one():
    layout = page(
        [
            [(40, 90, "物料编号"), (280, 90, "型号规格"), (550, 50, "数量"), (730, 40, "单位")],
            [(40, 90, "SYN-A"), (280, 90, "Synthetic red"), (550, 30, "12"), (730, 30, "PCS")],
            [(40, 90, "SYN-B"), (280, 90, "Synthetic blue"), (550, 30, "24"), (730, 30, "PCS")],
            [(40, 90, "SYN-C"), (280, 90, "Synthetic gold"), (550, 30, "36"), (730, 30, "PCS")],
        ]
    )
    for index, line in enumerate(layout["lines"]):
        line["words"].append(
            {
                "text": "金额" if index == 0 else "90.00",
                "x": 900,
                "y": index * 40,
                "width": 50,
                "height": 20,
            }
        )
    layout["rows"] = [" ".join(w["text"] for w in line["words"]) for line in layout["lines"]]
    for line in layout["lines"]:
        for word in line["words"]:
            word["y"] += 160
    layout["lines"].insert(
        0, {"words": [{"text": "SYNTHETIC HEADING", "x": 40, "y": 0, "width": 300, "height": 240}]}
    )
    result = extract(layout)
    assert [(r["description"], r["quantity"]) for r in result] == [
        ("SYN-A Synthetic red", "12"),
        ("SYN-B Synthetic blue", "24"),
        ("SYN-C Synthetic gold", "36"),
    ]


def test_unlabelled_total_and_prose_after_table_do_not_become_or_join_items():
    layout = page(
        [
            [
                (40, 90, "存货编码"),
                (280, 90, "存货名称"),
                (500, 90, "规格/型号"),
                (730, 40, "数量"),
                (900, 40, "金额"),
            ],
            [
                (40, 90, "SYN-A"),
                (280, 90, "合成材料甲"),
                (500, 90, "Synthetic red"),
                (730, 40, "12"),
                (900, 40, "90.00"),
            ],
            [
                (40, 90, "SYN-B"),
                (280, 90, "合成材料乙"),
                (500, 90, "Synthetic blue"),
                (730, 40, "24"),
                (900, 40, "90.00"),
            ],
            [(730, 40, "36"), (900, 40, "180.00")],
            [(40, 90, "条款说明")],
            [
                (40, 120, "请核对"),
                (190, 90, "存货编码"),
                (340, 120, "并且填写"),
                (490, 90, "名称"),
                (640, 120, "以及检查"),
                (790, 90, "数量"),
                (940, 150, "再交付签收"),
            ],
            [(40, 90, "其他约定"), (730, 40, "999")],
        ]
    )
    result = extract(layout)
    assert [(r["description"], r["quantity"]) for r in result] == [
        ("SYN-A 合成材料甲 Synthetic red", "12"),
        ("SYN-B 合成材料乙 Synthetic blue", "24"),
    ]


def single_token_layout():
    layout = page(
        [
            [(40, 40, "料号"), (200, 80, "规格"), (400, 40, "数量"), (500, 40, "单位")],
            [(40, 60, "SYN-A"), (200, 80, "合成材料"), (445, 40, "12"), (474, 60, "KG")],
        ]
    )
    words = layout["lines"][1]["words"]
    words[2]["subwords"] = [subword("12", 0, 448, 25)]
    words[3]["subwords"] = [subword("KG", 0, 495, 30)]
    layout["table_grids"] = [{"x_edges": [20, 160, 360, 480, 600], "y_edges": [-10, 30, 70]}]
    return layout


def test_full_source_token_recovers_physical_cell_without_rewriting():
    layout = single_token_layout()
    before = deepcopy(layout)
    result = extract(layout)
    assert [(r["quantity"], r["unit"]) for r in result] == [("12", "KG")]
    assert layout == before


@pytest.mark.parametrize(
    "mutation", ["missing", "crossing", "span", "polygon", "confidence", "partial", "outside"]
)
def test_invalid_single_token_keeps_physical_uncertainty(mutation):
    layout = single_token_layout()
    word = layout["lines"][1]["words"][3]
    part = word["subwords"][0]
    if mutation == "missing":
        word.pop("subwords")
    elif mutation == "crossing":
        word["subwords"] = [subword("KG", 0, 476, 30)]
    elif mutation == "span":
        part["start"] = 1
    elif mutation == "polygon":
        part["polygon"] = [{"x": 0}] * 4
    elif mutation == "confidence":
        part["confidence"] = float("nan")
    elif mutation == "partial":
        part["text"] = "K"
        part["end"] = 1
    else:
        word["subwords"] = [subword("KG", 0, 540, 30)]
    assert extract(layout) == []


def test_single_numeric_token_in_specification_stays_in_specification():
    from factoryflow.modules.documents.domain.table_candidate import _regional_fields

    word = {"text": "125", "x": 200, "y": 40, "width": 50, "height": 20}
    word["subwords"] = [subword("125", 0, 210, 30)]
    fields, uncertain = _regional_fields(
        [20, 160, 360, 480, 600], ["item_code", "specification", "quantity", "unit"], [word]
    )
    assert "quantity" not in fields
    assert fields["specification"][0]["text"] == "125"
    assert uncertain == []


def test_single_token_duplicate_target_column_does_not_project():
    from factoryflow.modules.documents.domain.table_candidate import _single_cell_token

    word = single_token_layout()["lines"][1]["words"][2]
    assert (
        _single_cell_token(
            word, [20, 160, 360, 480, 600], ["item_code", "quantity", "quantity", "unit"]
        )
        is word
    )


def test_single_token_projection_not_used_for_inferred_columns(monkeypatch):
    from factoryflow.modules.documents.domain import table_candidate

    monkeypatch.setattr(
        table_candidate,
        "_single_cell_token",
        lambda *args: pytest.fail("Physical-only token route used"),
    )
    layout = single_token_layout()
    layout.pop("table_grids")
    extract(layout)


def test_token_cannot_move_a_wide_specification_block_into_quantity():
    from factoryflow.modules.documents.domain.table_candidate import _single_cell_token

    word = {"text": "125", "x": 200, "y": 40, "width": 270, "height": 20}
    word["subwords"] = [subword("125", 0, 410, 30)]
    assert (
        _single_cell_token(
            word, [20, 160, 360, 480, 600], ["item_code", "specification", "quantity", "unit"]
        )
        is word
    )
