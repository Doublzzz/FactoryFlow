"""Optional registered header-strip recognition; never infer business numbers."""

import math
import time

from factoryflow.modules.documents.domain.table_candidate import ordinal_header_regions


def _overlap(a, b):
    width = max(0, min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"]))
    height = max(0, min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"]))
    return width * height


def _accepted(raw, region, top, crop_size):
    if raw.get("error_code"):
        return []
    mapped = []
    try:
        words = [w for line in raw["lines"] for w in line["words"]]
        if len(words) > 128:
            return []
        for w in words:
            values = [w[k] for k in ("x", "y", "width", "height")]
            if not isinstance(w["text"], str) or not all(
                type(v) in (int, float) and math.isfinite(v) for v in values
            ):
                return []
            x, y, width, height = values
            if not (0 <= x < x + width <= crop_size[0] and 0 <= y < y + height <= crop_size[1]):
                return []
            mapped.append(
                {"text": w["text"], "x": x, "y": y + top, "width": width, "height": height}
            )
        ordinal = [w for w in mapped if w["text"].strip() == "序号"]
        if len(ordinal) != 1:
            return []
        observed = ordinal[0]
        if not (
            observed["x"] + observed["width"] < region["left"]
            and region["top"] - 2 <= observed["y"]
            and observed["y"] + observed["height"] <= region["bottom"] + 2
        ):
            return []
        if any(_overlap(observed, a) > 0 for a in region["original_words"]):
            return []
        matched = set()
        for anchor in region["anchors"]:
            matches = [
                w
                for w in mapped
                if w["text"].strip() == anchor["text"].strip()
                and _overlap(w, anchor)
                >= 0.5 * max(w["width"] * w["height"], anchor["width"] * anchor["height"])
            ]
            if len(matches) == 1:
                matched.add(anchor["text"].strip())
        return ordinal if len(matched) >= 2 else []
    except KeyError, TypeError, ValueError, OverflowError:
        return []


def recover_ordinal_header(
    image, layout_lines, root, page_index, python, deadline, budget, recognize
):
    result, records = list(layout_lines), []
    for index, region in enumerate(ordinal_header_regions(layout_lines)):
        if budget["remaining"] <= 0 or time.monotonic() >= deadline:
            break
        margin = region["bottom"] - region["top"]
        top = max(0, math.floor(region["top"] - margin))
        bottom = min(image.height, math.ceil(region["bottom"] + margin))
        if bottom <= top or image.width * (bottom - top) > 4_000_000:
            continue
        budget["remaining"] -= 1
        crop = None
        try:
            crop = image.crop((0, top, image.width, bottom))
            raw = recognize(
                crop,
                root,
                f"{page_index}-ordinal-{index}",
                python,
                min(deadline, time.monotonic() + 12),
            )
            accepted = _accepted(raw, region, top, crop.size)
        except Exception:
            raw = {"error_code": "OCR_HEADER_RECOVERY_UNAVAILABLE"}
            accepted = []
        finally:
            if crop is not None:
                try:
                    crop.close()
                except Exception:
                    raw = {"error_code": "OCR_HEADER_RECOVERY_UNAVAILABLE"}
                    accepted = []
        records.append(
            {
                "method": "rapid-ordinal-header-v1",
                "crop": [0, top, image.width, bottom],
                "raw": raw,
                "accepted_words": accepted,
            }
        )
        result.extend({"words": [w]} for w in accepted)
    return result, records
