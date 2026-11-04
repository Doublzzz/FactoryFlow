"""Observed image whitespace may repair a proposal, never rewrite raw OCR evidence."""

from copy import deepcopy

import pytest
from factoryflow.modules.documents.adapters.ocr_worker import observe_slash_spaces
from factoryflow.modules.documents.domain.candidate import propose
from PIL import Image, ImageDraw


def fixture(left_gap=8, right_gap=8):
    image = Image.new("RGB", (360, 100), "white")
    draw = ImageDraw.Draw(image)
    x, y, height = 130, 45, 20
    boxes = [(x, 10), (x + 10 + left_gap, 7), (x + 17 + left_gap + right_gap, 12)]
    parts = []
    for index, (text, (left, width)) in enumerate(zip("A/蓝", boxes, strict=True)):
        draw.rectangle((left, y, left + width - 1, y + height - 1), fill="black")
        parts.append(
            {
                "text": text,
                "start": index,
                "end": index + 1,
                "x": left,
                "y": y,
                "width": width,
                "height": height,
                "confidence": 0.99,
                "polygon": [
                    [left, y],
                    [left + width, y],
                    [left + width, y + height],
                    [left, y + height],
                ],
            }
        )
    word = {
        "text": "A/蓝",
        "x": x,
        "y": y,
        "width": boxes[-1][0] + 12 - x,
        "height": height,
        "subwords": parts,
    }
    layout = {
        "layout_lines": [
            {
                "words": [
                    {"text": text, "x": xx, "y": 5, "width": 35, "height": 20}
                    for xx, text in [(20, "料号"), (130, "规格"), (270, "数量")]
                ]
            },
            {
                "words": [
                    {"text": "SYN-A", "x": 20, "y": y, "width": 50, "height": 20},
                    word,
                    {"text": "12", "x": 270, "y": y, "width": 25, "height": 20},
                ]
            },
        ],
        "rows": ["料号 规格 数量", "SYN-A A/蓝 12"],
        "table_grids": [{"x_edges": [10, 110, 250, 330], "y_edges": [0, 35, 85]}],
    }
    return image, layout


@pytest.mark.parametrize(
    "left,right,expected",
    [
        (8, 8, "A / 蓝"),
        (1, 2, "A/蓝"),
        (8, 2, "A /蓝"),
        (1, 8, "A/ 蓝"),
    ],
)
def test_only_observed_whitespace_reaches_specification_candidate(left, right, expected):
    image, layout = fixture(left, right)
    before = deepcopy(layout)
    layout["layout_lines"] = observe_slash_spaces(image, layout["layout_lines"])
    result = propose(layout["rows"], pages=[layout])
    assert result["lines"][0]["specification"] == expected
    assert result["lines"][0]["quantity"] == "12"
    assert result["lines"][0]["item_code"] == "SYN-A"
    assert before["layout_lines"][1]["words"][1]["text"] == "A/蓝"
    assert layout["layout_lines"][1]["words"][1]["text"] == "A/蓝"
    assert before["layout_lines"][1]["words"][1].get("observed_space_offsets") is None


@pytest.mark.parametrize("change", ["no_boxes", "invalid_boxes", "blank_image", "mislocated_slash"])
def test_uncertain_evidence_does_not_invent_spaces(change):
    image, layout = fixture()
    word = layout["layout_lines"][1]["words"][1]
    if change == "no_boxes":
        del word["subwords"]
    elif change == "invalid_boxes":
        word["subwords"][1]["start"] = -1
    elif change == "mislocated_slash":
        previous = word["subwords"][0]
        word["subwords"][1].update({key: previous[key] for key in ("x", "width", "polygon")})
    else:
        image.paste("white", (0, 0, image.width, image.height))
    before = deepcopy(layout["layout_lines"])
    assert observe_slash_spaces(image, before) == before


def test_loose_vertical_box_does_not_hide_visible_whitespace():
    image, layout = fixture()
    word = layout["layout_lines"][1]["words"][1]
    word.update(y=35, height=40)
    observed = observe_slash_spaces(image, layout["layout_lines"])
    assert observed[1]["words"][1]["observed_space_offsets"] == [1, 2]


def test_existing_spaces_and_non_specification_fields_are_preserved():
    image, layout = fixture()
    layout["layout_lines"] = observe_slash_spaces(image, layout["layout_lines"])
    # An annotation must never reach an item code, quantity, or general OCR row.
    layout["layout_lines"][0]["words"][1]["text"] = "名称"
    result = propose(layout["rows"], pages=[layout])
    assert "A/蓝" in result["lines"][0]["description"]
    assert "A / 蓝" not in result["lines"][0]["description"]
