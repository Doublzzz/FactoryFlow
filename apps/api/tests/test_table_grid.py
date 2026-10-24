"""Only synthetic closed raster grids qualify for coordinate metadata."""

import io

import pytest
from factoryflow.modules.documents.adapters import ocr_worker
from factoryflow.modules.documents.adapters.table_grid import detect_table_grids
from factoryflow.modules.documents.domain.candidate import propose
from PIL import Image, ImageDraw


def raster(scale=1, incomplete=False):
    image = Image.new("RGB", (800 * scale, 400 * scale), "white")
    draw = ImageDraw.Draw(image)
    for y in (40, 100, 220, 320):
        draw.line((40 * scale, y * scale, 740 * scale, y * scale), fill="black", width=scale)
    for x in (40, 400, 600, 740):
        bottom = 200 if incomplete and x == 600 else 320
        draw.line((x * scale, 40 * scale, x * scale, bottom * scale), fill="black", width=scale)
    return image


@pytest.mark.parametrize("scale", [1, 3])
def test_closed_grid_edges_use_original_image_pixels(scale):
    grids = detect_table_grids(raster(scale))
    assert len(grids) == 1
    for key, expected in (("x_edges", [40, 400, 600, 740]), ("y_edges", [40, 100, 220, 320])):
        assert len(grids[0][key]) == len(expected)
        assert all(
            abs(actual - edge * scale) <= 3
            for actual, edge in zip(grids[0][key], expected, strict=True)
        )


def test_unruled_image_and_incomplete_interior_line_are_rejected():
    assert detect_table_grids(Image.new("RGB", (800, 400), "white")) == []
    assert detect_table_grids(raster(incomplete=True)) == []


def test_partial_horizontal_border_and_merged_header_are_not_claimed_complete():
    image = raster()
    ImageDraw.Draw(image).line((40, 160, 400, 160), fill="black")
    assert detect_table_grids(image) == []
    image = raster()
    ImageDraw.Draw(image).line((400, 41, 400, 99), fill="white")
    grids = detect_table_grids(image)
    assert grids[0]["y_edges"] == [100, 220, 320]


def test_open_header_missing_interior_row_and_merged_summary_keep_only_supported_body():
    image = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 100, 740, 160), fill=(220, 235, 250))
    for y in (160, 260, 360, 460, 520):
        draw.line((40, y, 740, y), fill="black")
    for x in (40, 740):
        draw.line((x, 160, x, 580), fill="black")
    for x in (200, 400, 600):
        draw.line((x, 100, x, 260), fill="black")
        draw.line((x, 360, x, 460), fill="black")
    assert detect_table_grids(image) == [
        {
            "x_edges": [40, 200, 400, 600, 740],
            "y_edges": [100, 160, 260, 360, 460, 520],
            "row_complete": [True, True, False, True, False],
        }
    ]


def test_last_closed_band_without_inner_lines_is_retained_for_domain_identity_check():
    image = raster()
    draw = ImageDraw.Draw(image)
    for x in (400, 600):
        draw.line((x, 221, x, 319), fill="white")
    grids = detect_table_grids(image)
    assert grids[0]["y_edges"] == [40, 100, 220, 320]
    assert grids[0]["row_complete"] == [True, True, False]
    rows = [
        [(60, "料号"), (420, "品名规格"), (620, "数量")],
        [(60, "SYN-A"), (420, "合成甲"), (620, "12")],
        [(60, "SYN-B"), (420, "合成乙"), (620, "24")],
    ]
    lines = [
        {"words": [{"x": x, "y": y, "width": 80, "height": 20, "text": text} for x, text in row]}
        for y, row in zip((60, 140, 260), rows, strict=True)
    ]
    layout = {"lines": lines, "table_grids": grids}
    result = propose([], pages=[layout])["lines"]
    assert [(r["description"], r["quantity"]) for r in result] == [
        ("SYN-A 合成甲", "12"),
        ("SYN-B 合成乙", "24"),
    ]


def test_one_pixel_lines_survive_bounded_resize_without_accepting_pale_fill():
    image = Image.new("RGB", (4800, 2400), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((241, 241, 4441, 601), fill=(220, 235, 250))
    for y in (241, 601, 1321, 1921):
        draw.line((241, y, 4441, y), fill="black")
    for x in (241, 2401, 3601, 4441):
        draw.line((x, 241, x, 1921), fill="black")
    grids = detect_table_grids(image)
    assert len(grids) == 1
    assert len(grids[0]["x_edges"]) == 4
    assert len(grids[0]["y_edges"]) == 4
    assert (
        max(abs(a - b) for a, b in zip(grids[0]["x_edges"], [241, 2401, 3601, 4441], strict=True))
        <= 6
    )


def test_worker_adds_grid_without_changing_original_ocr_lines(tmp_path, monkeypatch):
    original = [{"words": [{"text": "合成", "x": 50, "y": 110, "width": 40, "height": 20}]}]
    monkeypatch.setattr(
        ocr_worker, "recognize", lambda *args: {"lines": original, "text": "合成", "language": "en"}
    )
    data = io.BytesIO()
    raster().save(data, format="PNG")
    (tmp_path / "source").write_bytes(data.getvalue())
    result = ocr_worker.run(tmp_path, "image/png")
    assert result["pages"][0]["lines"] == original
    assert result["pages"][0]["layout_lines"] == original
    assert result["pages"][0]["table_grids"] == detect_table_grids(raster())


@pytest.mark.parametrize("shade", [170, 190])
def test_gray_rules_survive_without_using_pale_header_fill(shade):
    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 740, 100), fill=(225, 235, 245))
    for y in (40, 100, 220, 320):
        draw.line((40, y, 740, y), fill=(shade,) * 3)
    for x in (40, 400, 600, 740):
        draw.line((x, 40, x, 320), fill=(shade,) * 3)
    grids = detect_table_grids(image)
    assert len(grids) == 1
    assert grids[0]["x_edges"] == [40, 400, 600, 740]
    assert grids[0]["row_complete"] == [True, True, True]


@pytest.mark.parametrize("shade", [180, 220, 240])
def test_solid_cell_fills_without_rules_are_not_a_grid(shade):
    image = Image.new("RGB", (800, 400), "white")
    draw = ImageDraw.Draw(image)
    for x in (40, 400, 600):
        draw.rectangle((x, 40, x + 60, 320), fill=(shade,) * 3)
    assert detect_table_grids(image) == []
