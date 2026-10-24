"""Synthetic PDF routing checks with stubbed OCR; no model inference."""

import copy

import pytest
from factoryflow.modules.documents.adapters import ocr_worker


def pdf_bytes(streams, page_extra="", resources_extra="", extra_objects=()):
    """Minimal standalone synthetic PDF, preserving literal source operators."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    objects.extend(extra_objects)
    page_ids = []
    for stream in streams:
        page_id, stream_id = len(objects) + 1, len(objects) + 2
        page_ids.append(page_id)
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] "
                f"/Resources << /Font << /F1 3 0 R >> {resources_extra} >> "
                f"/Contents {stream_id} 0 R {page_extra} >>"
            ).encode()
        )
        content = stream.encode("ascii")
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects[1] = f"<< /Type /Pages /Count {len(page_ids)} /Kids [{kids}] >>".encode()
    data, offsets = bytearray(b"%PDF-1.7\n"), [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(
        f"trailer << /Root 1 0 R /Size {len(offsets)} >>\nstartxref\n{start}\n%%EOF".encode()
    )
    return bytes(data)


def text_at(text, x, y):
    return f"BT /F1 14 Tf {x} {y} Td ({text}) Tj ET\n"


def table_stream():
    return "0 g\n" + "".join(
        text_at(text, x, y)
        for text, x, y in [
            ("Description", 40, 340),
            ("Quantity", 340, 340),
            ("Unit", 470, 340),
            ("Synthetic material", 40, 280),
            ("12.50", 340, 280),
            ("KG", 470, 280),
            ("Synthetic part", 40, 220),
            ("25", 340, 220),
            ("PCS", 470, 220),
        ]
    )


@pytest.mark.parametrize("engine", ["windows", "rapid"])
@pytest.mark.parametrize("streams", [[table_stream()], [table_stream(), ""]])
def test_pdf_always_uses_selected_ocr_even_when_text_layer_exists(
    monkeypatch, tmp_path, engine, streams
):
    calls = []
    raw = {
        "text": "Synthetic OCR output",
        "lines": [],
        "language": "en-US",
        "engine_metadata": {"source": "synthetic-stub"},
    }

    def recognize(image, *args):
        calls.append(image.size)
        return copy.deepcopy(raw)

    monkeypatch.setattr(ocr_worker, "recognize", recognize)
    monkeypatch.setattr(ocr_worker, "recognize_rapid", recognize)
    monkeypatch.setattr(ocr_worker, "recover_headers", lambda image, lines, *args: (lines, []))
    monkeypatch.setattr(
        ocr_worker, "recover_ordinal_header", lambda image, lines, *args: (lines, [])
    )
    (tmp_path / "source").write_bytes(pdf_bytes(streams))
    trace = ocr_worker.run(tmp_path, "application/pdf", engine, "synthetic")
    assert len(calls) == len(streams)
    assert trace["status"] == "ready"
    assert trace["engine"] == ("rapidocr" if engine == "rapid" else "windows-media-ocr")
    assert all(p["text"] == raw["text"] and p["preview_base64"] for p in trace["pages"])
    assert "selection_policy" not in trace
    assert all("source_characters" not in p and "selection" not in p for p in trace["pages"])


def test_pdf_ocr_failure_is_not_hidden_by_native_text(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ocr_worker, "recognize", lambda *args: {"text": "", "lines": [], "error_code": "OCR_FAILED"}
    )
    monkeypatch.setattr(ocr_worker, "recover_headers", lambda image, lines, *args: (lines, []))
    (tmp_path / "source").write_bytes(pdf_bytes([table_stream()]))
    trace = ocr_worker.run(tmp_path, "application/pdf")
    assert trace["status"] == "failed" and trace["error_code"] == "OCR_FAILED"
