"""Synthetic bounded header recovery; original OCR evidence is never rewritten."""

import copy
import io

import pytest
from factoryflow.modules.documents.adapters import ocr_worker
from factoryflow.modules.documents.domain.candidate import propose
from PIL import Image


def original_layout():
    return [
        {
            "words": [
                {"text": "规格", "x": 200, "y": 60, "width": 60, "height": 20},
                {"text": "数量", "x": 400, "y": 60, "width": 40, "height": 20},
            ]
        },
        {
            "words": [
                {"text": "SYN-A", "x": 40, "y": 140, "width": 60, "height": 20},
                {"text": "合成甲", "x": 200, "y": 140, "width": 60, "height": 20},
                {"text": "12", "x": 400, "y": 140, "width": 30, "height": 20},
            ]
        },
    ]


def grid():
    return {"x_edges": [20, 160, 360, 480], "y_edges": [40, 100, 200]}


def header_word(text="料号", **changes):
    word = {"text": text, "x": 64, "y": 64, "width": 80, "height": 40}
    return word | changes


def recover(monkeypatch, tmp_path, words, original=None):
    original = original_layout() if original is None else original
    snapshot = copy.deepcopy(original)
    raw = {"lines": [{"words": words}], "text": "synthetic header", "language": "zh"}
    calls = []

    def recognize(image, *args):
        assert image.width <= 2400 and image.height <= 512
        assert image.width * image.height <= 1_000_000
        assert image.getpixel((0, 0)) == (255, 255, 255)
        calls.append(args)
        return raw

    monkeypatch.setattr(ocr_worker, "recognize", recognize)
    layout, records = ocr_worker.recover_headers(
        Image.new("RGB", (900, 400), "white"), original, [grid()], tmp_path, 0, {"remaining": 2}
    )
    assert original == snapshot
    assert len(calls) == 1
    assert records[0]["raw"] == raw
    return layout, records


def test_missing_header_maps_back_without_changing_observed_label_or_original(
    monkeypatch, tmp_path
):
    layout, records = recover(
        monkeypatch, tmp_path, [header_word("料", width=38), header_word("号", x=106, width=38)]
    )
    # Use genuinely non-overlapping OCR character boxes for the known exact label.
    assert [w["text"] for w in records[0]["accepted_words"]] == ["料", "号"]
    assert records[0]["accepted_words"][0]["x"] == 40
    assert records[0]["accepted_words"][0]["y"] == 60
    assert records[0]["transform"]["padding"] == 12
    page = {"lines": original_layout(), "layout_lines": layout, "table_grids": [grid()]}
    assert propose([], pages=[page])["lines"][0]["description"] == "SYN-A 合成甲"


def test_occupied_header_cell_is_not_overridden(monkeypatch, tmp_path):
    layout, records = recover(monkeypatch, tmp_path, [header_word(), header_word("名称", x=384)])
    assert [w["text"] for w in records[0]["accepted_words"]] == ["料号"]
    assert layout[0] == original_layout()[0]


def test_unknown_label_is_ignored(monkeypatch, tmp_path):
    layout, records = recover(monkeypatch, tmp_path, [header_word("料码")])
    assert layout == original_layout()
    assert records[0]["accepted_words"] == []


def test_recovered_label_conflicting_with_existing_quantity_column_is_rejected(
    monkeypatch, tmp_path
):
    layout, records = recover(monkeypatch, tmp_path, [header_word("数量")])
    assert layout == original_layout()
    assert records[0]["accepted_words"] == []


def test_fully_occupied_header_does_not_call_supplemental_engine(monkeypatch, tmp_path):
    original = original_layout()
    original[0]["words"].append({"text": "料号", "x": 40, "y": 60, "width": 40, "height": 20})

    def forbidden(*args):
        pytest.fail("occupied header must not trigger optional OCR")

    monkeypatch.setattr(ocr_worker, "recognize", forbidden)
    layout, records = ocr_worker.recover_headers(
        Image.new("RGB", (900, 400), "white"), original, [grid()], tmp_path, 0, {"remaining": 2}
    )
    assert layout == original and records == []


@pytest.mark.parametrize(
    "changes",
    [
        {"x": float("nan")},
        {"width": -1},
        {"height": 0},
        {"y": 150},
        {"x": 0},
        {"x": "64"},
        {"width": 400},
    ],
)
def test_invalid_or_outside_boxes_are_ignored(monkeypatch, tmp_path, changes):
    layout, records = recover(monkeypatch, tmp_path, [header_word(**changes)])
    assert layout == original_layout()
    assert records[0]["accepted_words"] == []


def test_optional_failure_preserves_original_and_records_error(monkeypatch, tmp_path):
    raw = {"lines": [], "text": "", "error_code": "OCR_TIMEOUT"}
    monkeypatch.setattr(ocr_worker, "recognize", lambda *args: raw)
    original = original_layout()
    layout, records = ocr_worker.recover_headers(
        Image.new("RGB", (900, 400), "white"), original, [grid()], tmp_path, 0, {"remaining": 2}
    )
    assert layout == original and records[0]["raw"] == raw


def test_optional_engine_exception_does_not_fail_original(monkeypatch, tmp_path):
    def failed(*args):
        raise RuntimeError("synthetic engine exception")

    monkeypatch.setattr(ocr_worker, "recognize", failed)
    original = original_layout()
    layout, records = ocr_worker.recover_headers(
        Image.new("RGB", (900, 400), "white"), original, [grid()], tmp_path, 0, {"remaining": 2}
    )
    assert layout == original
    assert records[0]["raw"]["error_code"] == "OCR_UNAVAILABLE"


def test_wide_header_is_resized_within_supplemental_pixel_caps(monkeypatch, tmp_path):
    observed_sizes = []

    def recognize(image, *args):
        observed_sizes.append(image.size)
        return {"lines": [], "text": ""}

    monkeypatch.setattr(ocr_worker, "recognize", recognize)
    wide_grid = {"x_edges": [0, 2000, 4000, 6000], "y_edges": [0, 200, 400]}
    original = [
        {
            "words": [
                {"text": "规格", "x": 2400, "y": 60, "width": 60, "height": 20},
                {"text": "数量", "x": 4400, "y": 60, "width": 40, "height": 20},
            ]
        }
    ]
    _, records = ocr_worker.recover_headers(
        Image.new("RGB", (6000, 400), "white"), original, [wide_grid], tmp_path, 0, {"remaining": 2}
    )
    width, height = observed_sizes[0]
    assert width == 2400 and height <= 512 and width * height <= 1_000_000
    assert records[0]["transform"]["scale_x"] <= 2


def test_supplemental_timeout_keeps_worker_status_and_original_fields(monkeypatch, tmp_path):
    original = original_layout()
    image = Image.new("RGB", (900, 400), "white")
    image.save(tmp_path / "source", format="PNG")

    def recognize(image, root, index, language=""):
        if isinstance(index, str):
            return {"lines": [], "text": "", "error_code": "OCR_TIMEOUT"}
        return {"lines": original, "text": "合成甲", "language": "en"}

    monkeypatch.setattr(ocr_worker, "recognize", recognize)
    monkeypatch.setattr(ocr_worker, "detect_table_grids", lambda image: [grid()])
    result = ocr_worker.run(tmp_path, "image/png")
    assert result["status"] == "ready" and result["error_code"] is None
    page = result["pages"][0]
    assert page["lines"] == original and page["layout_lines"] == original
    assert page["rows"] == ocr_worker.read_rows(original) and page["text"] == "合成甲"
    assert page["header_ocr"][0]["raw"]["error_code"] == "OCR_TIMEOUT"


def test_document_budget_is_shared_across_pages(monkeypatch, tmp_path):
    image = Image.new("RGB", (900, 400), "white")
    pdf = io.BytesIO()
    image.save(pdf, format="PDF", save_all=True, append_images=[image, image], resolution=150)
    (tmp_path / "source").write_bytes(pdf.getvalue())
    original = original_layout()
    supplemental_calls = []

    def recognize(image, root, index, language=""):
        if isinstance(index, str):
            supplemental_calls.append(index)
            return {"lines": [{"words": [header_word()]}], "text": "料号", "language": "en"}
        return {"lines": copy.deepcopy(original), "text": "合成甲", "language": "en"}

    monkeypatch.setattr(ocr_worker, "recognize", recognize)
    monkeypatch.setattr(ocr_worker, "detect_table_grids", lambda image: [grid()])
    result = ocr_worker.run(tmp_path, "application/pdf")
    assert result["status"] == "ready"
    assert len(supplemental_calls) == 2
    assert [len(page["header_ocr"]) for page in result["pages"]] == [1, 1, 0]
    assert all(page["lines"] == original for page in result["pages"])
    assert all(page["rows"] == ocr_worker.read_rows(original) for page in result["pages"])
    assert all(page["text"] == "合成甲" for page in result["pages"])
