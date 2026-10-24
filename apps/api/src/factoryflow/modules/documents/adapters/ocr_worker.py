"""One job per subprocess isolates PDFium, image decode and native OCR from API threads."""

import base64
import io
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from factoryflow.modules.documents.adapters.ordinal_header import recover_ordinal_header
from factoryflow.modules.documents.adapters.rapid_ocr_worker import valid_subwords
from factoryflow.modules.documents.adapters.table_grid import detect_table_grids
from factoryflow.modules.documents.domain.table_candidate import (
    exact_header_kind,
    header_recovery_cells,
)


def recognize(image, root, index, language=""):
    import PIL

    path = root / f"page-{index}.png"
    image.save(path, format="PNG")
    executable = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    if os.name != "nt" or not executable.is_file():
        return {"text": "", "lines": [], "language": "", "error_code": "OCR_UNAVAILABLE"}
    try:
        result = subprocess.run(
            [
                str(executable),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(Path(__file__).with_name("windows_ocr.ps1")),
                str(path),
                language,
            ],
            capture_output=True,
            timeout=12,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if result.returncode:
            return {"text": "", "lines": [], "language": "", "error_code": "OCR_UNAVAILABLE"}
        data = json.loads(result.stdout.decode("utf-8-sig"))
        data["decoder_version"] = PIL.__version__
        return data
    except subprocess.TimeoutExpired:
        return {"text": "", "lines": [], "language": "", "error_code": "OCR_TIMEOUT"}


def supplement_numbers(primary, secondary):
    """Fill only uncovered digit boxes; never overwrite or combine conflicting readings."""
    original = [w for line in primary for w in line["words"]]
    extra = []
    for line in secondary:
        for word in line["words"]:
            if not re.fullmatch(r"[+\-]?[0-9]+(?:[.,][0-9]+)?", word["text"]):
                continue
            if any(
                min(word["x"] + word["width"], other["x"] + other["width"])
                > max(word["x"], other["x"])
                and min(word["y"] + word["height"], other["y"] + other["height"])
                > max(word["y"], other["y"])
                for other in original + extra
            ):
                continue
            extra.append(word)
    return [*primary, {"words": extra}]


def read_rows(lines):
    # Native OCR can separate columns into different lines. Group words by vertical centers.
    words = [word for line in lines for word in line["words"]]
    groups = []
    for word in sorted(words, key=lambda w: w["y"] + w["height"] / 2):
        center = word["y"] + word["height"] / 2
        group = next(
            (g for g in groups if abs(g[0] - center) <= max(5, max(g[2], word["height"]) * 0.55)),
            None,
        )
        if group is None:
            groups.append([center, [word], word["height"]])
        else:
            group[1].append(word)
    return [" ".join(w["text"] for w in sorted(g[1], key=lambda w: w["x"])) for g in groups]


def recover_headers(image, layout_lines, grids, root, page_index, budget):
    """Optional bounded header-strip OCR, filling only exactly recognized empty cells."""
    from PIL import Image, ImageOps

    result, records = layout_lines, []
    for grid_index, grid in enumerate(grids[:8]):
        if budget["remaining"] <= 0:
            break
        empty = header_recovery_cells(result, grid)
        if not empty:
            continue
        xs, ys = grid["x_edges"], grid["y_edges"]
        box = (math.floor(xs[0]), math.floor(ys[0]), math.ceil(xs[-1]), math.ceil(ys[1]))
        if not (0 <= box[0] < box[2] <= image.width and 0 <= box[1] < box[3] <= image.height):
            continue
        if box[3] - box[1] > 512:
            continue
        padded = ImageOps.expand(image.crop(box), border=12, fill="white")
        scale = min(
            2,
            2400 / padded.width,
            512 / padded.height,
            math.sqrt(1_000_000 / (padded.width * padded.height)),
        )
        size = (max(1, math.floor(padded.width * scale)), max(1, math.floor(padded.height * scale)))
        crop = padded.resize(size, Image.Resampling.LANCZOS)
        scale_x, scale_y = size[0] / padded.width, size[1] / padded.height
        transform = {
            "crop_box": list(box),
            "padding": 12,
            "scale_x": scale_x,
            "scale_y": scale_y,
            "ocr_size": list(size),
        }
        budget["remaining"] -= 1
        try:
            raw = recognize(crop, root, f"{page_index}-header-{grid_index}")
        except Exception:
            # Optional-engine diagnostics can contain material; keep only a safe code.
            raw = {"text": "", "lines": [], "error_code": "OCR_UNAVAILABLE"}
        accepted, mapped = [], [[] for _ in empty]
        if not raw.get("error_code"):
            for line in raw.get("lines", []):
                for word in line.get("words", []):
                    if not isinstance(word.get("text"), str) or not word["text"].strip():
                        continue
                    values = [word.get(key) for key in ("x", "y", "width", "height")]
                    if not all(
                        type(value) in (int, float) and math.isfinite(value) for value in values
                    ):
                        continue
                    x, y, width, height = values
                    if (
                        width <= 0
                        or height <= 0
                        or x < 0
                        or y < 0
                        or x + width > size[0]
                        or y + height > size[1]
                    ):
                        continue
                    observed = word | {
                        "x": box[0] + x / scale_x - 12,
                        "y": box[1] + y / scale_y - 12,
                        "width": width / scale_x,
                        "height": height / scale_y,
                    }
                    for index, (left, top, right, bottom) in enumerate(empty):
                        if (
                            left <= observed["x"]
                            and top <= observed["y"]
                            and observed["x"] + observed["width"] <= right
                            and observed["y"] + observed["height"] <= bottom
                        ):
                            mapped[index].append(observed)
                            break
        original_words = [w for line in result for w in line.get("words", [])]
        existing_kinds = [
            exact_header_kind(
                [
                    w
                    for w in original_words
                    if min(right, w["x"] + w["width"]) > max(left, w["x"])
                    and min(ys[1], w["y"] + w["height"]) > max(ys[0], w["y"])
                ]
            )
            for left, right in zip(xs, xs[1:], strict=False)
        ]
        recovered_kinds = [exact_header_kind(words) for words in mapped]
        for words, kind in zip(mapped, recovered_kinds, strict=True):
            if kind is None:
                continue
            if kind in ("description", "item_code", "quantity", "unit") and (
                kind in existing_kinds or recovered_kinds.count(kind) > 1
            ):
                continue
            accepted.extend(words)
        records.append({"raw": raw, "transform": transform, "accepted_words": accepted})
        if accepted:
            result = [*result, {"words": accepted}]
    return result, records


def recognize_rapid(image, root, index, python, deadline):
    path = root / f"page-{index}.png"
    destination = root / f"rapid-{index}.json"
    image.save(path, format="PNG")
    failure = {"text": "", "lines": [], "language": ""}
    if not Path(python).is_file():
        return failure | {"error_code": "OCR_INTERPRETER_UNAVAILABLE"}
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return failure | {"error_code": "OCR_TIMEOUT"}
        result = subprocess.run(
            [
                python,
                "-I",
                str(Path(__file__).with_name("rapid_ocr_worker.py")),
                str(path),
                str(destination),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=min(remaining, 75),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if (
            result.returncode
            or not destination.is_file()
            or destination.stat().st_size > 4 * 1024 * 1024
        ):
            raise ValueError("invalid result")
        data = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("text"), str):
            raise ValueError("invalid result")
        lines = data["lines"]
        if not isinstance(lines, list) or len(lines) > 10000:
            raise ValueError("invalid result")
        for line in lines:
            if not isinstance(line, dict) or len(line["words"]) != 1:
                raise ValueError("invalid result")
            word = line["words"][0]
            if not isinstance(word["text"], str) or len(word["text"]) > 10000:
                raise ValueError("invalid result")
            values = [word[key] for key in ("x", "y", "width", "height")]
            if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                raise ValueError("invalid result")
            x, y, width, height = values
            if (
                x < 0
                or y < 0
                or width <= 0
                or height <= 0
                or x + width > image.width
                or y + height > image.height
            ):
                raise ValueError("invalid result")
            if "subwords" in word and not valid_subwords(word, word["subwords"]):
                word.pop("subwords")
        if sum(len(line["words"][0].get("subwords", [])) for line in lines) > 10000:
            for line in lines:
                line["words"][0].pop("subwords", None)
        if data.get("error_code") not in {
            None,
            "OCR_VERSION_MISMATCH",
            "OCR_MODEL_MISMATCH",
            "OCR_RUNTIME_MISMATCH",
            "OCR_RESULT_INVALID",
            "OCR_FAILED",
        }:
            raise ValueError("invalid result")
        return data
    except subprocess.TimeoutExpired:
        return failure | {"error_code": "OCR_TIMEOUT"}
    except Exception:
        return failure | {"error_code": "OCR_RESULT_INVALID"}


def run(root, media_type, engine="windows", python=None):
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = 20_000_000
    pages = []
    total_pixels = 0
    preview_bytes = 0
    header_budget = {"remaining": 2}
    deadline = time.monotonic() + 80

    def add(image):
        nonlocal total_pixels, preview_bytes
        if image.width * image.height > 20_000_000 or max(image.size) > 10000:
            raise ValueError("FILE_DIMENSIONS_EXCEEDED")
        total_pixels += image.width * image.height
        if total_pixels > 40_000_000:
            raise ValueError("FILE_DIMENSIONS_EXCEEDED")
        image = image.convert("RGB")
        raw = (
            recognize_rapid(image, root, len(pages), python, deadline)
            if engine == "rapid"
            else recognize(image, root, len(pages))
        )
        layout_lines = raw["lines"]
        if (
            engine == "windows"
            and raw.get("language", "").startswith("zh")
            and not raw.get("error_code")
        ):
            secondary = recognize(image, root, len(pages), "en-US")
            raw["supplemental_ocr"] = secondary
            layout_lines = supplement_numbers(layout_lines, secondary["lines"])
        preview = io.BytesIO()
        image.save(preview, format="PNG")
        preview_bytes += preview.tell()
        if preview_bytes > 25 * 1024 * 1024:
            raise ValueError("FILE_PREVIEW_LIMIT")
        grids = detect_table_grids(image)
        original_rows = read_rows(layout_lines)
        header_ocr = []
        if engine == "windows":
            layout_lines, header_ocr = recover_headers(
                image, layout_lines, grids, root, len(pages), header_budget
            )
        if engine == "rapid" and not raw.get("error_code"):
            layout_lines, header_ocr = recover_ordinal_header(
                image,
                layout_lines,
                root,
                len(pages),
                python,
                deadline,
                header_budget,
                recognize_rapid,
            )
        pages.append(
            {
                "number": len(pages) + 1,
                "width": image.width,
                "height": image.height,
                "preview_base64": base64.b64encode(preview.getvalue()).decode("ascii"),
                "rows": original_rows,
                "layout_lines": layout_lines,
                **raw,
                "table_grids": grids,
                "header_ocr": header_ocr,
            }
        )

    content = (root / "source").read_bytes()
    if not 0 < len(content) <= 10 * 1024 * 1024:
        raise ValueError("FILE_TOO_LARGE")
    if media_type == "application/pdf":
        import pypdfium2 as pdfium

        with pdfium.PdfDocument(content) as document:
            if not 1 <= len(document) <= 5:
                raise ValueError("PDF_PAGE_LIMIT")
            for page in document:
                try:
                    width, height = page.get_size()
                    if (
                        width * height * (150 / 72) ** 2 > 20_000_000
                        or max(width, height) * 150 / 72 > 10000
                    ):
                        raise ValueError("FILE_DIMENSIONS_EXCEEDED")
                    bitmap = page.render(scale=150 / 72)
                    try:
                        add(bitmap.to_pil())
                    finally:
                        bitmap.close()
                finally:
                    page.close()
    else:
        with Image.open(io.BytesIO(content)) as original:
            if original.width * original.height > 20_000_000 or max(original.size) > 10000:
                raise ValueError("FILE_DIMENSIONS_EXCEEDED")
            if original.format not in {"PNG", "JPEG"} or getattr(original, "n_frames", 1) != 1:
                raise ValueError("FILE_TYPE_UNSUPPORTED")
            add(ImageOps.exif_transpose(original))
    errors = [page.get("error_code") for page in pages if page.get("error_code")]
    has_text = any(page["text"].strip() for page in pages)
    result = {
        "status": "ready" if has_text and not errors else "failed",
        "error_code": errors[0] if errors else None if has_text else "NO_TEXT_FOUND",
        "engine": "rapidocr" if engine == "rapid" else "windows-media-ocr",
        "engine_version": "3.9.2"
        if engine == "rapid"
        else sys.getwindowsversion().build
        if os.name == "nt"
        else None,
        **({"engine_metadata": pages[0].get("engine_metadata")} if engine == "rapid" else {}),
        "pages": pages,
    }
    return result


if __name__ == "__main__":

    def deny_network(event, args):
        if event in {"socket.getaddrinfo", "socket.connect", "socket.sendto"}:
            raise PermissionError("Local extraction does not use network connections")

    sys.addaudithook(deny_network)
    directory = Path(sys.argv[1])
    try:
        config = (
            json.loads((directory / "engine.json").read_text(encoding="utf-8"))
            if (directory / "engine.json").is_file()
            else {}
        )
        outcome = run(directory, sys.argv[2], **config)
    except Exception:
        # Decoder exceptions can include file contents; never forward them to logs or HTTP.
        outcome = {"status": "failed", "error_code": "FILE_DECODE_FAILED", "pages": []}
    (directory / "result.json").write_text(
        json.dumps(outcome, ensure_ascii=False), encoding="utf-8"
    )
