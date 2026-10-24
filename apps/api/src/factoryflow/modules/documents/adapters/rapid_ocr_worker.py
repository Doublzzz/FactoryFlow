"""Standalone isolated-runtime runner; stdlib only until local assets are verified."""

import hashlib
import importlib.metadata
import json
import math
import platform
import sys
from pathlib import Path

MODELS = {
    "det": (
        "PP-OCRv6_det_small.onnx",
        "090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
    ),
    "rec": (
        "PP-OCRv6_rec_small.onnx",
        "6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
    ),
    "cls": (
        "ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        "e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
    ),
}
MAX_RESULT = 4 * 1024 * 1024


def deny_network(event, args):
    if event in {
        "socket.getaddrinfo",
        "socket.connect",
        "socket.sendto",
        "socket.bind",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.exec",
    }:
        raise PermissionError("OCR_OFFLINE_POLICY")


def verify_assets():
    try:
        distribution = importlib.metadata.distribution("rapidocr")
        runtime = importlib.metadata.distribution("onnxruntime")
    except importlib.metadata.PackageNotFoundError:
        raise ValueError("OCR_VERSION_MISMATCH") from None
    if distribution.version != "3.9.2" or runtime.version != "1.30.0":
        raise ValueError("OCR_VERSION_MISMATCH")
    paths = {}
    for kind, (name, digest) in MODELS.items():
        path = Path(distribution.locate_file(f"rapidocr/models/{name}"))
        if not path.is_file() or not 0 < path.stat().st_size <= 100 * 1024 * 1024:
            raise ValueError("OCR_MODEL_MISMATCH")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != digest:
            raise ValueError("OCR_MODEL_MISMATCH")
        paths[kind] = path
    return paths


def valid_subwords(word, parts):
    """Optional evidence must cover source text in order, using finite observed boxes."""
    if not isinstance(parts, list) or not 1 <= len(parts) <= 512:
        return False
    cursor = 0
    try:
        for part in parts:
            start, end = part["start"], part["end"]
            if (
                type(start) is not int
                or type(end) is not int
                or not cursor <= start < end <= len(word["text"])
            ):
                return False
            if word["text"][cursor:start].strip() or part["text"] != word["text"][start:end]:
                return False
            values = [part[key] for key in ("x", "y", "width", "height", "confidence")]
            if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                return False
            x, y, width, height, confidence = values
            if not (0 < width <= 10000 and 0 < height <= 10000 and 0 <= confidence <= 1):
                return False
            if not (
                0 <= word["x"] <= x
                and 0 <= word["y"] <= y
                and x + width <= word["x"] + word["width"] <= 10000
                and y + height <= word["y"] + word["height"] <= 10000
            ):
                return False
            polygon = part["polygon"]
            if (
                not isinstance(polygon, list)
                or len(polygon) != 4
                or any(not isinstance(point, list) or len(point) != 2 for point in polygon)
            ):
                return False
            if not all(
                type(v) in (int, float) and math.isfinite(v) for point in polygon for v in point
            ):
                return False
            if any(
                not x <= point[0] <= x + width or not y <= point[1] <= y + height
                for point in polygon
            ):
                return False
            if not all(
                math.isclose(observed, expected, rel_tol=0, abs_tol=1e-6)
                for observed, expected in zip(
                    (
                        min(p[0] for p in polygon),
                        min(p[1] for p in polygon),
                        max(p[0] for p in polygon),
                        max(p[1] for p in polygon),
                    ),
                    (x, y, x + width, y + height),
                    strict=True,
                )
            ):
                return False
            cursor = end
        return not word["text"][cursor:].strip()
    except KeyError, TypeError, ValueError, OverflowError:
        return False


def attach_subwords(word, tokens):
    if not isinstance(tokens, (list, tuple)) or not 1 <= len(tokens) <= 512:
        return
    parts, cursor = [], 0
    try:
        for token, score, box in tokens:
            if not isinstance(token, str) or not token:
                return
            while cursor < len(word["text"]) and word["text"][cursor].isspace():
                cursor += 1
            if not word["text"].startswith(token, cursor):
                return
            points = box.tolist() if hasattr(box, "tolist") else box
            if (
                not isinstance(points, list)
                or len(points) != 4
                or any(not isinstance(point, list) or len(point) != 2 for point in points)
            ):
                return
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            parts.append(
                {
                    "start": cursor,
                    "end": cursor + len(token),
                    "text": token,
                    "x": min(xs),
                    "y": min(ys),
                    "width": max(xs) - min(xs),
                    "height": max(ys) - min(ys),
                    "polygon": points,
                    "confidence": float(score),
                }
            )
            cursor += len(token)
        if valid_subwords(word, parts):
            word["subwords"] = parts
    except KeyError, ValueError, TypeError, IndexError, OverflowError:
        # Invalid optional evidence must never destroy a valid original block.
        return


def blocks(output):
    boxes, texts, scores = output.boxes, output.txts, output.scores
    if boxes is None and texts is None:
        return {"text": "", "lines": [], "language": ""}
    if (
        boxes is None
        or texts is None
        or scores is None
        or not (len(boxes) == len(texts) == len(scores) <= 10000)
    ):
        raise ValueError("OCR_RESULT_INVALID")
    lines = []
    for box, text, score in zip(boxes, texts, scores, strict=True):
        points = box.tolist() if hasattr(box, "tolist") else box
        if not isinstance(text, str) or len(text) > 10000 or len(points) != 4:
            raise ValueError("OCR_RESULT_INVALID")
        if any(len(point) != 2 for point in points):
            raise ValueError("OCR_RESULT_INVALID")
        values = [value for point in points for value in point]
        if not all(
            type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 10000 for v in values
        ):
            raise ValueError("OCR_RESULT_INVALID")
        confidence = float(score)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("OCR_RESULT_INVALID")
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if max(xs) <= min(xs) or max(ys) <= min(ys):
            raise ValueError("OCR_RESULT_INVALID")
        lines.append(
            {
                "words": [
                    {
                        "text": text,
                        "x": min(xs),
                        "y": min(ys),
                        "width": max(xs) - min(xs),
                        "height": max(ys) - min(ys),
                        "polygon": points,
                        "confidence": confidence,
                    }
                ]
            }
        )
    token_rows = getattr(output, "word_results", None)
    if (
        isinstance(token_rows, (tuple, list))
        and len(token_rows) == len(lines)
        and all(isinstance(row, (list, tuple)) for row in token_rows)
        and sum(len(row) for row in token_rows) <= 10000
    ):
        for line, tokens in zip(lines, token_rows, strict=True):
            attach_subwords(line["words"][0], tokens)
    return {"text": "\n".join(texts), "lines": lines, "language": ""}


def run(page):
    paths = verify_assets()
    from rapidocr import RapidOCR
    from rapidocr.utils.typings import EngineType

    params = {
        "Global.log_level": "critical",
        "Global.return_word_box": True,
        "Global.return_single_char_box": False,
        "EngineConfig.onnxruntime.intra_op_num_threads": 2,
        "EngineConfig.onnxruntime.inter_op_num_threads": 1,
    }
    for provider in ("cuda", "dml", "cann", "coreml"):
        params[f"EngineConfig.onnxruntime.use_{provider}"] = False
    for kind, path in paths.items():
        params[f"{kind.title()}.model_path"] = str(path)
        params[f"{kind.title()}.engine_type"] = EngineType.ONNXRUNTIME
    engine = RapidOCR(params=params)
    # Confirm actual sessions before inference; provider availability alone is insufficient.
    for component in (engine.text_det, engine.text_rec, engine.text_cls):
        if component.session.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("OCR_RUNTIME_MISMATCH")
    result = blocks(engine(str(page), return_word_box=True, return_single_char_box=False))
    result["engine_metadata"] = {
        "engine": "rapidocr",
        "engine_version": "3.9.2",
        "runtime": "onnxruntime",
        "runtime_version": "1.30.0",
        "providers": ["CPUExecutionProvider"],
        "python_version": platform.python_version(),
        "model_sha256": {kind: value[1] for kind, value in MODELS.items()},
    }
    return result


def main():
    sys.addaudithook(deny_network)
    page, destination = Path(sys.argv[1]), Path(sys.argv[2])
    try:
        result = run(page)
        data = json.dumps(result, ensure_ascii=False).encode("utf-8")
        if len(data) > MAX_RESULT:
            raise ValueError("OCR_RESULT_INVALID")
    except Exception as error:
        safe = {
            "OCR_VERSION_MISMATCH",
            "OCR_MODEL_MISMATCH",
            "OCR_RUNTIME_MISMATCH",
            "OCR_RESULT_INVALID",
        }
        code = str(error) if type(error) is ValueError and str(error) in safe else "OCR_FAILED"
        data = json.dumps({"text": "", "lines": [], "error_code": code}).encode("utf-8")
    destination.write_bytes(data)


if __name__ == "__main__":
    main()
