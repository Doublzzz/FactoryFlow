"""Real local OCR acceptance, separate from transaction tests using a stub."""

import io
import os

import pytest
from factoryflow.modules.documents.adapters.ocr import LocalExtractor
from factoryflow.modules.documents.adapters.ocr_worker import run, supplement_numbers
from factoryflow.modules.documents.domain.candidate import propose
from PIL import Image, ImageDraw, ImageFont


def synthetic_image():
    image = Image.new("RGB", (1600, 800), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 40)
    for index, line in enumerate(
        [
            "Order No: SYN-OCR-ABC",
            "Date: 2026-10-02",
            "Currency: CNY",
            "Synthetic material   1.125   KG",
            "Synthetic part   2   PCS",
        ]
    ):
        draw.text((50, 50 + index * 120), line, fill="black", font=font)
    return image


@pytest.mark.skipif(os.name != "nt", reason="Windows native OCR requires a prepared Windows host")
def test_real_image_and_two_page_pdf_produce_trace_and_preview():
    image = synthetic_image()
    png = io.BytesIO()
    image.save(png, format="PNG")
    result = LocalExtractor().extract(png.getvalue(), "image/png")
    assert result["status"] == "ready", result.get("error_code")
    assert "Synthetic" in result["pages"][0]["text"]
    assert result["pages"][0]["lines"][0]["words"]
    pdf = io.BytesIO()
    image.save(pdf, format="PDF", save_all=True, append_images=[image], resolution=150)
    result = LocalExtractor().extract(pdf.getvalue(), "application/pdf")
    assert result["status"] == "ready", result.get("error_code")
    assert len(result["pages"]) == 2
    assert all("Synthetic" in page["text"] and page["preview_base64"] for page in result["pages"])


def test_dimensions_are_rejected_before_pixel_decode(tmp_path, monkeypatch):
    # This large, compressible image is deliberately below the upload byte limit.
    image = Image.new("RGB", (6000, 6000), "white")
    image.save(tmp_path / "source", format="PNG")
    image.close()

    def forbidden(*args, **kwargs):
        pytest.fail("oversized image must not reach pixel decode")

    monkeypatch.setattr(Image.Image, "load", forbidden)
    with (
        pytest.warns(Image.DecompressionBombWarning),
        pytest.raises(ValueError, match="FILE_DIMENSIONS_EXCEEDED"),
    ):
        run(tmp_path, "image/png")


def test_corrupt_file_is_a_safe_failed_result():
    result = LocalExtractor().extract(b"%PDF-synthetic-corrupt", "application/pdf")
    assert result == {"status": "failed", "error_code": "FILE_DECODE_FAILED", "pages": []}


def test_excess_pdf_pages_are_not_rendered(tmp_path, monkeypatch):
    import pypdfium2

    document = pypdfium2.PdfDocument.new()
    for _ in range(6):
        document.new_page(100, 100).close()
    document.save(tmp_path / "source")
    document.close()

    def forbidden(*args, **kwargs):
        pytest.fail("excess pages must not render")

    monkeypatch.setattr(pypdfium2.PdfPage, "render", forbidden)
    with pytest.raises(ValueError, match="PDF_PAGE_LIMIT"):
        run(tmp_path, "application/pdf")


@pytest.mark.skipif(os.name != "nt", reason="Windows native OCR requires a prepared Windows host")
def test_real_chinese_table_generates_rows_despite_extra_price_columns():
    image = Image.new("RGB", (2000, 800), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 36)
    columns = [50, 180, 620, 950, 1140, 1410, 1680]
    rows = [
        ["序号", "产品名称", "规格", "单位", "数量", "单价", "金额"],
        ["1", "合成材料甲", "M8-20", "KG", "12", "12.00", "144.00"],
        ["2", "合成零件乙", "B-200", "PCS", "25", "2.00", "50.00"],
    ]
    for row_index, cells in enumerate(rows):
        for x, cell in zip(columns, cells, strict=True):
            draw.text((x, 70 + row_index * 140), cell, fill="black", font=font)
    png = io.BytesIO()
    image.save(png, format="PNG")
    result = LocalExtractor().extract(png.getvalue(), "image/png")
    assert result["status"] == "ready", result.get("error_code")
    proposal = propose(
        [row for page in result["pages"] for row in page["rows"]], pages=result["pages"]
    )
    assert [(row["quantity"], row["unit"]) for row in proposal["lines"]] == [
        ("12", "KG"),
        ("25", "PCS"),
    ], [(page["language"], page["rows"]) for page in result["pages"]]
    assert "合成材料甲" in proposal["lines"][0]["description"]


def test_supplement_preserves_conflicts_and_accepts_only_uncovered_numbers():
    primary_word = {"text": "1 · 25", "x": 10, "y": 10, "width": 80, "height": 20}
    primary = [{"words": [primary_word]}]
    secondary = [
        {
            "words": [
                {**primary_word, "text": "1.25"},
                {**primary_word, "text": "300", "x": 150},
                {**primary_word, "text": "fake description", "x": 300},
            ]
        }
    ]
    result = supplement_numbers(primary, secondary)
    assert [w["text"] for line in result for w in line["words"]] == ["1 · 25", "300"]
    assert primary == [{"words": [primary_word]}]


def synthetic_wrapped_table():
    image = Image.new("RGB", (2000, 1400), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 30)
    draw.text((70, 40), "SYNTHETIC PURCHASE ORDER", fill="black", font=font)
    draw.text((70, 90), "TEL: 0000-1234567  FAX: 0000-7654321", fill="black", font=font)
    for x, value in [
        (100, "物料编号"),
        (510, "型号规格"),
        (1130, "单位"),
        (1330, "订购数量"),
        (1600, "含税金额"),
    ]:
        draw.text((x, 185), value, fill="black", font=font)
    for index, quantity in enumerate((120, 240, 360, 480)):
        center = 315 + index * 190
        for x, value in [
            (100, f"SYN-A10{index + 1}"),
            (1130, "PCS"),
            (1330, str(quantity)),
            (1600, "10.00"),
        ]:
            draw.text((x, center), value, fill="black", font=font)
        for offset, value in [
            (-48, f"Synthetic wire type {index + 1}"),
            (0, "Insulation size 6 MM"),
            (48, "Synthetic coating"),
        ]:
            draw.text((510, center + offset), value, fill="black", font=font)
    draw.text((510, 1080), "以下空白", fill="black", font=font)
    draw.text((100, 1200), "备注: Synthetic terms 999 PCS", fill="black", font=font)
    for x in (60, 460, 1080, 1280, 1550, 1920):
        draw.line((x, 165, x, 1150), fill="black", width=2)
    for y in (165, 240, 430, 620, 810, 1000, 1150):
        draw.line((60, y, 1920, y), fill="black", width=2)
    return image


@pytest.mark.skipif(os.name != "nt", reason="Windows native OCR requires a prepared Windows host")
def test_real_wrapped_code_spec_table_keeps_four_rows_and_excludes_contact():
    image = synthetic_wrapped_table()
    png = io.BytesIO()
    image.save(png, format="PNG")
    result = LocalExtractor().extract(png.getvalue(), "image/png")
    proposal = propose([row for p in result["pages"] for row in p["rows"]], pages=result["pages"])
    assert [(row["quantity"], row["unit"]) for row in proposal["lines"]] == [
        ("120", "PCS"),
        ("240", "PCS"),
        ("360", "PCS"),
        ("480", "PCS"),
    ], [p["rows"] for p in result["pages"]]
    assert all(
        "TEL" not in r["description"] and "999" not in r["description"] for r in proposal["lines"]
    )
    # Native OCR reads initial I as l on this fixture. Check row association of
    # all three text lines; do not turn a layout test into a perfect-glyph claim.
    assert all(
        "size 6" in r["description"]
        and "coating" in r["description"]
        and f"type {index + 1}" in r["description"]
        for index, r in enumerate(proposal["lines"])
    )
