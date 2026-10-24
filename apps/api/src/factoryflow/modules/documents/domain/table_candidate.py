"""Header-guided proposals from OCR coordinates; never infer missing business values."""

import math
import re
from bisect import bisect_right
from statistics import mean, median

from factoryflow.kernel.quantity import confirm_quantity

_LABELS = {
    "description": (
        "品名",
        "品名规格",
        "货品规格",
        "名称",
        "产品名称",
        "物料名称",
        "存货名称",
        "商品名称",
        "货品名称",
        "货物名称",
        "description",
        "itemdescription",
        "productname",
        "itemname",
    ),
    # Common aliases/eligibility adapted from OrderMVP parsers/common.py, without
    # its private template dispatch, numeric conversion, models or debug output.
    "item_code": (
        "物料编号",
        "物料编码",
        "物料代码",
        "货物编号",
        "货物编码",
        "货品编号",
        "料号",
        "货号",
        "产品编码",
        "产品编号",
        "存货编码",
        "sku",
        "partno",
        "code",
        "itemcode",
    ),
    "specification": ("规格", "型号", "规格型号", "型号规格", "spec", "specification", "model"),
    "quantity": ("数量", "订购数量", "订单数量", "采购数量", "quantity", "qty"),
    "unit": ("单位", "计量单位", "unit", "uom"),
    "source_unit_price": ("单价", "含税单价", "price", "unitprice"),
    "source_amount": ("金额", "含税金额", "amount", "total"),
    "ignored": (
        "序号",
        "编号",
        "物料号",
        "税率",
        "备注",
        "交期",
        "交货日期",
        "no",
        "itemno",
        "remarks",
    ),
}
_KINDS = {label: kind for kind, labels in _LABELS.items() for label in labels}
_PRICE_KINDS = {"source_unit_price", "source_amount"}
_PRICE_TEXT = re.compile(r"[0-9]+(?:\.[0-9]+)?")
_COMPOUND_IDENTITY_HEADERS = {"品名规格", "货品规格"}
_NUMBER = re.compile(r"[+\-−＋－]?\s*[0-9]+(?:\s*[.,·．，。]\s*[0-9]+)?")
_FOOTER = re.compile(
    r"^(?:合计|总计|小计|备注|说明|条款|其他条款|以下空白|(?:subtotal|grand\s*total|total|notes?)\b)",
    re.I,
)


def _compact(text):
    return re.sub(r"[\s.:：/_\-]", "", text).lower()


def _text(words):
    value = " ".join(w["text"] for w in words).strip()
    return re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", value)


def _rows(page):
    # Port of legacy ocr_parser._group_line_tokens_by_y_coordinate: stable input
    # ties, X order and retained boxes. Accept native rectangles; keep tiny dots
    # with their taller row instead of converting any business number to float.
    lines = page.get("layout_lines", page.get("lines", []))
    words = [w for line in lines for w in line.get("words", [])]
    typical_height = median(w["height"] for w in words) if words else 1
    groups = []
    positioned = sorted(
        enumerate(words),
        key=lambda pair: (pair[1]["y"] + pair[1]["height"] / 2, pair[1]["x"], pair[0]),
    )
    for input_index, word in positioned:
        center = word["y"] + word["height"] / 2
        target = next(
            (
                g
                for g in reversed(groups)
                if abs(g[0] - center)
                <= max(5, min(max(g[2], word["height"]), typical_height) * 0.65)
            ),
            None,
        )
        if target is None:
            target = [center, [], word["height"]]
            groups.append(target)
        target[1].append((word["x"], input_index, word))
        # Keep the row anchor fixed: a tall heading plus a moving center otherwise
        # lets successive neighboring rows chain across an entire document.
        target[2] = max(target[2], word["height"])
    return [
        [word for _, _, word in sorted(group, key=lambda w: (w[0], w[1]))] for _, group, _ in groups
    ]


def _header_cells(words):
    cells = []
    index = 0
    while index < len(words):
        found = None
        for end in range(index + 1, min(index + 6, len(words)) + 1):
            # Join split characters only inside one plausible header cell.
            if end > index + 1:
                previous, current = words[end - 2], words[end - 1]
                if current["x"] - previous["x"] - previous["width"] > max(
                    previous["height"], current["height"]
                ):
                    break
            label = _compact("".join(w["text"] for w in words[index:end]))
            if label in _COMPOUND_IDENTITY_HEADERS and any(
                current["x"] - previous["x"] - previous["width"]
                > min(previous["height"], current["height"]) * 0.35
                for previous, current in zip(words[index:end], words[index + 1 : end], strict=False)
            ):
                # Two complete, spaced-out 品名/规格 labels remain separate columns.
                # A compound split by OCR must have tightly adjacent fragments.
                continue
            kind = _KINDS.get(label)
            if kind:
                found = (end, kind)
        if found:
            end, kind = found
        else:
            end, kind = index + 1, "ignored"
        cells.append(words[index:end])
        index = end
    return cells


def _cell_bounds(words):
    return min(w["x"] for w in words), max(w["x"] + w["width"] for w in words)


def _columns(header_rows):
    cells = []
    for row in header_rows:
        for cell in _header_cells(row):
            left, right = _cell_bounds(cell)
            overlaps = [
                old
                for old in cells
                if min(right, _cell_bounds(old)[1]) - max(left, _cell_bounds(old)[0])
                > min(right - left, _cell_bounds(old)[1] - _cell_bounds(old)[0]) * 0.3
            ]
            for old in overlaps:
                cells.remove(old)
                cell = old + cell
            cells.append(cell)
    columns = []
    score = 0
    for cell in sorted(cells, key=lambda c: _cell_bounds(c)[0]):
        label = _compact("".join(_text(row) for row in _rows({"lines": [{"words": cell}]})))
        kind = _KINDS.get(label, "ignored")
        score += label in _KINDS
        left, right = _cell_bounds(cell)
        columns.append((kind, (left + right) / 2))
    kinds = [kind for kind, _ in columns]
    core = set(kinds) & {"description", "item_code", "specification", "quantity", "unit"}
    hint = len(core) >= 2
    # Mentioning field names inside a paragraph is not a table header. Most
    # cells must actually be recognized labels, including price/date columns.
    if score < len(columns) / 2:
        return None, score, hint
    if "quantity" not in core or not core & {"description", "item_code", "specification"}:
        return None, score, hint
    if any(kinds.count(kind) > 1 for kind in ("description", "item_code", "quantity", "unit")):
        return [], score, True
    return (
        [
            (kind if kind not in _PRICE_KINDS or kinds.count(kind) == 1 else "ignored", center)
            for kind, center in columns
        ],
        score,
        True,
    )


def _header_at(rows, start):
    best = None
    hint = False
    for count in range(1, min(3, len(rows) - start) + 1):
        columns, score, detected = _columns(rows[start : start + count])
        hint |= detected
        if columns is not None and count > 1:
            later_is_stronger = False
            for offset in range(1, count):
                for later_count in range(1, count - offset + 1):
                    later_columns, later_score, _ = _columns(
                        rows[start + offset : start + offset + later_count]
                    )
                    if later_columns is not None and later_score >= score:
                        later_is_stronger = True
            if later_is_stronger:
                # Do not consume a complete later header through an overlapping
                # metadata row. True split headers survive when their first
                # row contributes necessary recognized label fragments.
                continue
        if columns is not None and (best is None or score > best[2]):
            best = columns, count, score
    return best, hint


def _fields(columns, words):
    # Header-midpoint alignment from legacy _align_row_tokens_to_header_columns.
    boundaries = [(a[1] + b[1]) / 2 for a, b in zip(columns, columns[1:], strict=False)]
    fields = {}
    for word in words:
        kind = columns[bisect_right(boundaries, word["x"] + word["width"] / 2)][0]
        if kind != "ignored":
            fields.setdefault(kind, []).append(word)
    return fields


def _cell_text(words):
    return " ".join(_text(row) for row in _rows({"lines": [{"words": words}]}))


def exact_header_kind(words):
    """Classify only an observed finite header label; do not correct characters."""
    kind = _KINDS.get(_compact(_cell_text(words)))
    # Recovery adapters use prices as known non-business header helpers.
    return "ignored" if kind in _PRICE_KINDS else kind


def header_recovery_cells(layout_lines, grid):
    """Empty first-band cells of a table already eligible from observed labels."""
    xs, ys = grid.get("x_edges", []), grid.get("y_edges", [])
    if not 3 <= len(xs) <= 33 or not 3 <= len(ys) <= 201:
        return []
    if any(b <= a for edges in (xs, ys) for a, b in zip(edges, edges[1:], strict=False)):
        return []
    words = [w for line in layout_lines for w in line.get("words", [])]
    cells, rectangles = [], []
    for left, right in zip(xs, xs[1:], strict=False):
        rectangle = left, ys[0], right, ys[1]
        rectangles.append(rectangle)
        cells.append(
            [
                w
                for w in words
                if min(right, w["x"] + w["width"]) > max(left, w["x"])
                and min(ys[1], w["y"] + w["height"]) > max(ys[0], w["y"])
            ]
        )
    kinds = [exact_header_kind(cell) for cell in cells]
    if "quantity" not in kinds or not set(kinds) & {"description", "item_code", "specification"}:
        return []
    if sum(kind is not None for kind in kinds) < len(cells) / 2:
        return []
    if any(kinds.count(kind) > 1 for kind in ("description", "item_code", "quantity", "unit")):
        return []
    return [rectangle for rectangle, cell in zip(rectangles, cells, strict=True) if not cell]


def _specification_continuations(record):
    """Keep short left-aligned wrapped tails with an observed specification.

    Header midpoints are weak evidence. Reassignment needs a preceding spec
    line in this same anchored record, close vertical continuity and left
    alignment; an independently populated business row is never a tail.
    """
    specification = record.get("specification", [])
    description = record.get("description", [])
    reassigned = []
    for word in sorted(description[:], key=lambda w: w["y"]):
        center = word["y"] + word["height"] / 2
        if any(
            abs(other["y"] + other["height"] / 2 - center)
            <= min(other["height"], word["height"]) * 0.65
            for kind in ("item_code", "quantity")
            for other in record.get(kind, [])
        ):
            continue
        previous = [
            other
            for other in specification
            if 0
            < center - other["y"] - other["height"] / 2
            <= max(other["height"], word["height"]) * 2.5
            and abs(other["x"] - word["x"]) <= min(other["height"], word["height"]) * 0.5
        ]
        if not previous:
            continue
        # A competing observed description alignment leaves ownership ambiguous.
        if any(
            other is not word
            and other["y"] < word["y"]
            and abs(other["x"] - word["x"]) <= min(other["height"], word["height"]) * 0.5
            for other in description
        ):
            continue
        description.remove(word)
        specification.append(word)
        reassigned.append(word)
    return reassigned


def _business_rows(columns, body, resolved_fields=None, unresolved_regions=None):
    if not columns:
        return []
    fields = []
    last_anchor_has_quantity = False
    for index, words in enumerate(body):
        if _FOOTER.match(_text(words)):
            break
        field = resolved_fields[index] if resolved_fields is not None else _fields(columns, words)
        quantity = _text(field.get("quantity", []))
        has_identity = any(field.get(k) for k in ("item_code", "description", "specification"))
        # A detached numeric-only line after a complete item is a summary, not
        # another quantity to append to that item. A missing quantity may still
        # be supplied on its next physical line.
        if quantity and not has_identity and last_anchor_has_quantity:
            break
        if field.get("item_code") or field.get("description"):
            last_anchor_has_quantity = bool(quantity)
        elif quantity:
            last_anchor_has_quantity = True
        fields.append(field)
    # A code column gives row identity even when quantity OCR is missing. Without
    # it, only quantity positions anchor rows; never use numbers from specifications.
    anchor_kind = "item_code" if any(k == "item_code" for k, _ in columns) else "quantity"
    anchors = []
    for field in fields:
        words = field.get(anchor_kind, [])
        value = _text(words)
        if value and (anchor_kind == "item_code" or _NUMBER.fullmatch(value)):
            anchors.append(mean(w["y"] + w["height"] / 2 for w in words))
    if not anchors:
        return []
    boundaries = [(a + b) / 2 for a, b in zip(anchors, anchors[1:], strict=False)]
    records = [{} for _ in anchors]
    for field in fields:
        for kind, words in field.items():
            for word in words:
                if kind in _PRICE_KINDS and any(
                    word["y"] < boundary < word["y"] + word["height"] for boundary in boundaries
                ):
                    # A vertically merged source cell has no single row owner.
                    first = bisect_right(boundaries, word["y"])
                    last = bisect_right(boundaries, word["y"] + word["height"])
                    for record in records[first : last + 1]:
                        record.setdefault(kind, []).append({**word, "text": ""})
                    continue
                record = records[bisect_right(boundaries, word["y"] + word["height"] / 2)]
                record.setdefault(kind, []).append(word)
    result = []
    for record in records:
        reassigned = _specification_continuations(record)
        if reassigned and unresolved_regions is not None:
            unresolved_regions.append(_bounds(reassigned))
        quantity = _cell_text(record.get("quantity", []))
        if anchor_kind != "item_code" and not _NUMBER.fullmatch(quantity):
            continue
        proposal = _proposal(record, [kind for kind, _ in columns])
        if proposal is not None:
            result.append(proposal)
    return result


def _grid_footer(words):
    text = _text(sorted(words, key=lambda w: w["x"]))
    return _FOOTER.match(text) or re.match(
        r"^(?:签收人|收货人|制单人|审核人|仓管员|(?:制单|审核|签收)\s*[:：]|"
        r"TEL\b|FAX\b|联系电话[:：]|电话[:：]|地址[:：]|联系人[:：])",
        text,
        re.I,
    )


def _bounds(words):
    return (
        min(w["x"] for w in words),
        min(w["y"] for w in words),
        max(w["x"] + w["width"] for w in words),
        max(w["y"] + w["height"] for w in words),
    )


def _quantity_unit_parts(word, xs, kinds):
    """Use source spans only inside distinct, fully containing known columns."""
    parts = word.get("subwords")
    if not isinstance(parts, list) or not 2 <= len(parts) <= 512:
        return None
    if kinds.count("quantity") != 1 or kinds.count("unit") != 1:
        return None
    if (
        len(xs) != len(kinds) + 1
        or not all(type(v) in (int, float) and math.isfinite(v) for v in xs)
        or any(b <= a for a, b in zip(xs, xs[1:], strict=False))
    ):
        return None
    qi, ui = kinds.index("quantity"), kinds.index("unit")
    if qi >= ui:
        return None
    text = word["text"]
    match = re.fullmatch(
        rf"(?P<quantity>{_NUMBER.pattern})\s*(?P<unit>[A-Za-z.\u4e00-\u9fff]+)", text
    )
    if match is None or confirm_quantity("1", match["unit"]).policy.mode == "UNKNOWN":
        return None
    groups = {"quantity": [], "unit": []}
    cursor = 0
    try:
        original = [word[key] for key in ("x", "y", "width", "height")]
        if not all(type(v) in (int, float) and math.isfinite(v) for v in original):
            return None
        ox, oy, ow, oh = original
        if ox < 0 or oy < 0 or ow <= 0 or oh <= 0 or ox + ow > 10000 or oy + oh > 10000:
            return None
        for part in parts:
            start, end = part["start"], part["end"]
            if (
                type(start) is not int
                or type(end) is not int
                or not cursor <= start < end <= len(text)
                or text[cursor:start].strip()
                or part["text"] != text[start:end]
            ):
                return None
            values = [part[key] for key in ("x", "y", "width", "height")]
            if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                return None
            x, y, width, height = values
            if (
                width <= 0
                or height <= 0
                or x < ox
                or y < oy
                or x + width > ox + ow
                or y + height > oy + oh
            ):
                return None
            confidence, polygon = part["confidence"], part["polygon"]
            if (
                type(confidence) not in (int, float)
                or not math.isfinite(confidence)
                or not 0 <= confidence <= 1
            ):
                return None
            if (
                not isinstance(polygon, list)
                or len(polygon) != 4
                or any(not isinstance(point, list) or len(point) != 2 for point in polygon)
            ):
                return None
            if any(
                type(value) not in (int, float) or not math.isfinite(value)
                for point in polygon
                for value in point
            ):
                return None
            if any(
                not x <= point[0] <= x + width or not y <= point[1] <= y + height
                for point in polygon
            ):
                return None
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
                return None
            kind = next(
                (kind for kind in groups if match.start(kind) <= start < end <= match.end(kind)),
                None,
            )
            if kind is None:
                return None
            index = qi if kind == "quantity" else ui
            if not xs[index] <= x < x + width <= xs[index + 1]:
                return None
            groups[kind].append(part)
            cursor = end
        if text[cursor:].strip() or not all(groups.values()):
            return None
        result = []
        for kind, observed in groups.items():
            left, top, right, bottom = _bounds(observed)
            # This geometry is the union of observed token boxes, never character widths.
            result.append(
                {
                    "text": match[kind],
                    "x": left,
                    "y": top,
                    "width": right - left,
                    "height": bottom - top,
                }
            )
        return result
    except KeyError, TypeError, ValueError, OverflowError:
        return None


def _single_cell_token(word, xs, kinds):
    """Project one full-source token into a unique physical quantity/unit cell."""
    try:
        parts = word.get("subwords")
        if not isinstance(parts, list) or len(parts) != 1:
            return word
        part = parts[0]
        text = word["text"]
        kind = "quantity" if _NUMBER.fullmatch(text) else "unit"
        if kind == "unit" and confirm_quantity("1", text).policy.mode == "UNKNOWN":
            return word
        if kinds.count(kind) != 1 or len(xs) != len(kinds) + 1:
            return word
        if not all(type(v) in (int, float) and math.isfinite(v) for v in xs):
            return word
        if any(b <= a for a, b in zip(xs, xs[1:], strict=False)):
            return word
        if (
            type(part["start"]) is not int
            or type(part["end"]) is not int
            or part["start"] != 0
            or part["end"] != len(text)
            or part["text"] != text
        ):
            return word
        boxes = [[item[key] for key in ("x", "y", "width", "height")] for item in (word, part)]
        if not all(type(v) in (int, float) and math.isfinite(v) for box in boxes for v in box):
            return word
        (ox, oy, ow, oh), (x, y, width, height) = boxes
        if not (
            0 <= ox <= x < x + width <= ox + ow <= 10000
            and 0 <= oy <= y < y + height <= oy + oh <= 10000
        ):
            return word
        index = kinds.index(kind)
        if not xs[index] < ox + ow / 2 < xs[index + 1]:
            return word
        if not xs[index] <= x < x + width <= xs[index + 1]:
            return word
        confidence = part["confidence"]
        if (
            type(confidence) not in (int, float)
            or not math.isfinite(confidence)
            or not 0 <= confidence <= 1
        ):
            return word
        polygon = part["polygon"]
        if not isinstance(polygon, list) or len(polygon) != 4:
            return word
        if any(not isinstance(point, list) or len(point) != 2 for point in polygon):
            return word
        if not all(
            type(v) in (int, float) and math.isfinite(v) for point in polygon for v in point
        ):
            return word
        if any(not x <= px <= x + width or not y <= py <= y + height for px, py in polygon):
            return word
        observed = (
            min(p[0] for p in polygon),
            min(p[1] for p in polygon),
            max(p[0] for p in polygon),
            max(p[1] for p in polygon),
        )
        if not all(
            math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
            for a, b in zip(observed, (x, y, x + width, y + height), strict=True)
        ):
            return word
        return {**word, "x": x, "y": y, "width": width, "height": height}
    except KeyError, TypeError, ValueError, OverflowError:
        return word


def _inferred_price_pair(xs, kinds, words):
    """Independent same-row literals can disambiguate one estimated right edge."""
    if any(kinds.count(kind) != 1 for kind in _PRICE_KINDS):
        return set()
    indices = sorted(kinds.index(kind) for kind in _PRICE_KINDS)
    if indices[1] != indices[0] + 1:
        return set()
    pair = []
    for index in indices:
        # Count competing left-edge OR center owners, including invalid literals
        # and merged parents. Never pick one of several price candidates.
        candidates = [
            word
            for word in words
            if xs[index] <= word["x"] < xs[index + 1]
            or xs[index] <= word["x"] + word["width"] / 2 < xs[index + 1]
        ]
        if len(candidates) != 1:
            return set()
        word = candidates[0]
        left, right = word["x"], word["x"] + word["width"]
        if (
            not _PRICE_TEXT.fullmatch(word["text"].strip())
            or word["width"] <= 0
            or word["height"] <= 0
            or not xs[index] <= left < left + word["width"] / 2 < xs[index + 1]
        ):
            return set()
        if right > xs[index + 1] and (
            index + 1 >= len(kinds)
            or kinds[index + 1] not in _PRICE_KINDS | {"ignored"}
            or right > xs[index + 2]
        ):
            return set()
        pair.append(word)
    first, second = pair
    overlap = min(first["y"] + first["height"], second["y"] + second["height"]) - max(
        first["y"], second["y"]
    )
    if (
        first["x"] + first["width"] > second["x"]
        or overlap < max(first["height"], second["height"]) * 0.65
    ):
        return set()
    return {id(word) for word in pair}


def _regional_fields(xs, kinds, words, physical=True):
    # Local projected fields only: source words, polygons and spans remain untouched.
    words = [part for word in words for part in (_quantity_unit_parts(word, xs, kinds) or [word])]
    if physical:
        words = [_single_cell_token(word, xs, kinds) for word in words]
    price_pair = set() if physical else _inferred_price_pair(xs, kinds, words)
    fields, uncertain = {}, []
    quantity_boxes = [
        w
        for w in words
        if re.search(r"[0-9]", w["text"])
        and re.fullmatch(r"[+\-−＋－0-9\s.,·．，。]+", w["text"])
        and any(
            kind == "quantity" and left - 2 <= w["x"] and w["x"] + w["width"] <= right + 2
            for left, right, kind in zip(xs, xs[1:], kinds, strict=False)
        )
    ]
    quantity_left = next(
        (xs[index] for index, kind in enumerate(kinds) if kind == "quantity"), xs[-1]
    )
    for word in words:
        center = word["x"] + word["width"] / 2
        # Physical edges remain strict; an independent inferred pair can resolve
        # its estimated right edges without changing any source boxes or text.
        # A merged price/amount box must not suppress safe merchandise fields.
        touched = {
            kind
            for left, right, kind in zip(xs, xs[1:], kinds, strict=False)
            if min(right, word["x"] + word["width"]) > max(left, word["x"])
        }
        touched_prices = touched & _PRICE_KINDS
        column = bisect_right(xs[1:-1], center)
        kind = kinds[column]
        if kind in _PRICE_KINDS or (
            touched_prices and touched <= _PRICE_KINDS | {"ignored"} and kind == "ignored"
        ):
            if (
                kind in _PRICE_KINDS
                and word["width"] > 0
                and word["height"] > 0
                and xs[column] <= word["x"]
                and (word["x"] + word["width"] <= xs[column + 1] or id(word) in price_pair)
            ):
                fields.setdefault(kind, []).append(word)
            else:
                # Crossings into quantity/identity are not safe price cells either.
                for target in touched_prices | ({kind} & _PRICE_KINDS):
                    fields.setdefault(target, []).append({**word, "text": ""})
            continue
        if not physical:
            column = bisect_right(xs[1:-1], center)
            start = bisect_right(xs[1:-1], word["x"])
            separate_quantity = any(
                min(word["x"] + word["width"], other["x"] + other["width"])
                <= max(word["x"], other["x"])
                for other in quantity_boxes
                if other is not word
            )
            separate_code = any(
                other is not word
                and kinds[bisect_right(xs[1:-1], other["x"] + other["width"] / 2)] == "item_code"
                for other in words
            )
            kind = kinds[column]
            if (
                kinds[start] in ("description", "item_code", "specification")
                and word["x"] < quantity_left < word["x"] + word["width"]
            ):
                if separate_quantity:
                    # Correct a wide identity box only when its center fell in
                    # quantity. A description extending from the inferred code
                    # column must not become a second item-code row anchor.
                    if kind == "quantity" and kinds[start] in ("description", "specification"):
                        kind = kinds[start]
                elif kind == "quantity" or not separate_code:
                    uncertain.append(word)
                    continue
            if kind != "ignored":
                fields.setdefault(kind, []).append(word)
            continue
        if not xs[0] < center < xs[-1]:
            uncertain.append(word)
            continue
        column = bisect_right(xs, center) - 1
        kind = kinds[column]
        contained = xs[column] - 2 <= word["x"] and word["x"] + word["width"] <= xs[column + 1] + 2
        if not contained:
            touched = {
                target
                for left, right, target in zip(xs, xs[1:], kinds, strict=False)
                if min(right, word["x"] + word["width"]) > max(left, word["x"])
            }
            if kind == "ignored" and touched == {"ignored"}:
                # Adjacent price/amount boxes do not determine business fields.
                # Keep identity/quantity/unit crossings strict.
                continue
            start = bisect_right(xs, word["x"]) - 1
            separate_quantity = any(
                min(word["x"] + word["width"], other["x"] + other["width"])
                <= max(word["x"], other["x"])
                for other in quantity_boxes
                if other is not word
            )
            if (
                0 <= start < len(kinds)
                and kinds[start] in ("description", "specification")
                and separate_quantity
            ):
                kind = kinds[start]
            else:
                uncertain.append(word)
                continue
        if kind != "ignored":
            fields.setdefault(kind, []).append(word)
    return fields, uncertain


def _proposal(record, kinds):
    description = " ".join(
        filter(
            None,
            (
                _cell_text(record.get(kind, []))
                for kind in ("item_code", "description", "specification")
            ),
        )
    )
    quantity, unit = _cell_text(record.get("quantity", [])), _cell_text(record.get("unit", []))
    if not description or len(unit) > 40:
        return None
    proposal = {
        "description": description[:500],
        "quantity": quantity,
        "unit": unit,
        "source_unit_price": _source_price(record.get("source_unit_price", [])),
        "source_amount": _source_price(record.get("source_amount", [])),
    }
    if set(kinds) & {"item_code", "specification"} and all(
        kinds.count(kind) <= 1 for kind in ("item_code", "description", "specification")
    ):
        separated = {
            "item_code": _cell_text(record.get("item_code", [])) or None,
            "item_name": _cell_text(record.get("description", [])),
            "specification": _cell_text(record.get("specification", [])) or None,
        }
        # Preserve original strings; do not truncate the separated source fields.
        if all(
            len(separated[key] or "") <= limit
            for key, limit in (("item_code", 100), ("item_name", 500), ("specification", 1000))
        ):
            proposal.update(separated)
            proposal["description"] = description
    return proposal


def _source_price(words):
    if len(words) != 1:
        return None
    value = words[0]["text"].strip()
    return value if _PRICE_TEXT.fullmatch(value) else None


def _structured(fields):
    identity = any(fields.get(kind) for kind in ("item_code", "description", "specification"))
    return bool(
        identity
        and fields.get("quantity")
        or fields.get("item_code")
        and (fields.get("description") or fields.get("specification"))
    )


def _column_edges(columns):
    centers = [center for _, center in columns]
    return [
        centers[0] - (centers[1] - centers[0]) / 2,
        *[(a + b) / 2 for a, b in zip(centers, centers[1:], strict=False)],
        centers[-1] + (centers[-1] - centers[-2]) / 2,
    ]


def _unruled_body_fields(xs, kinds, body):
    """Resolve wrapping against nearby observed identity and quantity boxes.

    Inferred midpoints can cut a genuine cell before its actual quantity box.
    Borrow only left-alignment evidence from the closest anchored row, never
    its quantity value, and never extend that evidence across a table footer.
    """
    resolved = [_regional_fields(xs, kinds, row, physical=False) for row in body]
    anchors, borrowed = [], []
    for row, (record, uncertain) in zip(body, resolved, strict=True):
        if _grid_footer(row):
            break
        quantity = record.get("quantity", [])
        identity = record.get("item_code", []) or record.get("description", [])
        if not identity:
            continue
        if uncertain and not record.get("item_code"):
            continue
        if not record.get("item_code") and not _NUMBER.fullmatch(_cell_text(quantity)):
            continue
        anchor = record.get("item_code", []) or quantity
        anchors.append((mean(w["y"] + w["height"] / 2 for w in anchor), record))
    for row, (record, uncertain) in zip(body, resolved, strict=True):
        if _grid_footer(row):
            break
        for word in uncertain[:]:
            if not anchors:
                continue
            center = word["y"] + word["height"] / 2
            distances = sorted((abs(center - y), index) for index, (y, _) in enumerate(anchors))
            if len(distances) > 1 and abs(distances[0][0] - distances[1][0]) <= 2:
                continue
            neighbor = anchors[distances[0][1]][1]
            if not _NUMBER.fullmatch(_cell_text(neighbor.get("quantity", []))):
                # An intervening identified record without quantity blocks
                # borrowing another record's column evidence.
                continue
            quantity_left = min(w["x"] for w in neighbor["quantity"])
            if word["x"] + word["width"] > quantity_left - 2:
                continue
            matches = {
                kind
                for kind in ("description", "specification")
                for reference in neighbor.get(kind, [])
                if abs(word["x"] - reference["x"]) <= min(word["height"], reference["height"]) * 0.5
                and distances[0][0] <= max(word["height"], reference["height"]) * 2.5
            }
            if len(matches) == 1:
                record.setdefault(matches.pop(), []).append(word)
                uncertain.remove(word)
                # Nearby geometry supports a candidate, not certain ownership.
                borrowed.append(word)
    return resolved, borrowed


def table_result(page):
    """Local evidence: resolved lines, consumed regions and unresolved regions.

    None means no table clues. A claimed region records ownership, not accuracy;
    unresolved regions may overlap it when boxes/columns remain uncertain.
    """
    rows = _rows(page)
    words = [w for row in rows for w in row]
    handled, entries, claimed, unresolved, contexts, table_ends = set(), [], [], [], [], []
    detected = False

    def claim(region_words, warning=False):
        if not region_words:
            return
        handled.update(id(w) for w in region_words)
        region = _bounds(region_words)
        claimed.append(region)
        if warning:
            unresolved.append(region)

    def emit(record, region_words, kinds):
        line = _proposal(record, kinds)
        if line is not None:
            entries.append(
                (min(w["y"] for w in region_words), min(w["x"] for w in region_words), line)
            )

    for grid in page.get("table_grids", [])[:8]:
        xs, ys = grid.get("x_edges", []), grid.get("y_edges", [])
        if not 3 <= len(xs) <= 33 or not 3 <= len(ys) <= 201:
            continue
        if any(b <= a for edges in (xs, ys) for a, b in zip(edges, edges[1:], strict=False)):
            continue
        complete = grid.get("row_complete", [True] * (len(ys) - 1))
        if len(complete) != len(ys) - 1 or any(type(value) is not bool for value in complete):
            continue
        bands = [[] for _ in ys[1:]]
        for word in words:
            x, y = word["x"] + word["width"] / 2, word["y"] + word["height"] / 2
            if id(word) not in handled and xs[0] < x < xs[-1] and ys[0] < y < ys[-1]:
                bands[bisect_right(ys, y) - 1].append(word)
        kinds = None
        for index, band in enumerate(bands):
            cells = [[] for _ in xs[1:]]
            for word in band:
                cells[bisect_right(xs, word["x"] + word["width"] / 2) - 1].append(word)
            labels = [_compact(_cell_text(cell)) for cell in cells]
            proposed = [_KINDS.get(label, "ignored") for label in labels]
            core = set(proposed) & {"description", "item_code", "specification", "quantity", "unit"}
            eligible = (
                "quantity" in core
                and bool(core & {"description", "item_code", "specification"})
                and sum(label in _KINDS for label in labels) >= len(labels) / 2
            )
            if eligible:
                if any(
                    w["x"] + 2 < edge < w["x"] + w["width"] - 2 for w in band for edge in xs[1:-1]
                ):
                    continue
                detected = True
                if any(
                    proposed.count(kind) > 1
                    for kind in ("description", "item_code", "quantity", "unit")
                ):
                    claim([w for following in bands[index:] for w in following], True)
                    break
                kinds = [
                    kind if kind not in _PRICE_KINDS or proposed.count(kind) == 1 else "ignored"
                    for kind in proposed
                ]
                contexts.append((ys[index], xs, kinds, True))
                claimed.append((xs[0], ys[index], xs[-1], ys[-1]))
                claim(band)
                continue
            if kinds is None:
                continue
            if _grid_footer(band):
                table_ends.append(min(w["y"] for w in band))
                claim(band)
                break
            record, uncertain = _regional_fields(xs, kinds, band)
            for kind in _PRICE_KINDS:
                if any(
                    min(ys[index + 1], w["y"] + w["height"]) > max(ys[index], w["y"])
                    and (w["y"] < ys[index] or w["y"] + w["height"] > ys[index + 1])
                    and any(
                        target == kind and min(right, w["x"] + w["width"]) > max(left, w["x"])
                        for left, right, target in zip(xs, xs[1:], kinds, strict=False)
                    )
                    for other_band in bands
                    for w in other_band
                ):
                    record.pop(kind, None)
            cross_row = any(
                w["y"] < ys[index] - 2 or w["y"] + w["height"] > ys[index + 1] + 2 for w in band
            )
            safe = _structured(record) or bool(complete[index] and record.get("item_code"))
            claim(band, bool(uncertain or cross_row or band and not safe))
            if safe and not uncertain:
                if not record.get("quantity"):
                    unresolved.append(_bounds(band))
                if complete[index] or record.get("quantity"):
                    emit(record, band, kinds)

    # Discover each unhandled header independently, even after totals or prose.
    remaining_rows = [[w for w in row if id(w) not in handled] for row in rows]
    headers = []
    index = 0
    while index < len(rows):
        header, hint = _header_at(remaining_rows, index)
        detected |= hint
        if header is None:
            index += 1
            continue
        columns, count, _ = header
        headers.append((index, count, columns))
        detected = True
        index += count
    for header_index, (start, count, columns) in enumerate(headers):
        end = headers[header_index + 1][0] if header_index + 1 < len(headers) else len(rows)
        header_words = [w for row in remaining_rows[start : start + count] for w in row]
        claim(header_words, not columns)
        if not columns:
            claim([w for row in remaining_rows[start + count : end] for w in row], True)
            continue
        xs, kinds = _column_edges(columns), [kind for kind, _ in columns]
        contexts.append((min(w["y"] for w in header_words), xs, kinds, False))
        body = remaining_rows[start + count : end]
        clean, resolved = [], []
        body_fields, borrowed = _unruled_body_fields(xs, kinds, body)
        if borrowed:
            unresolved.append(_bounds(borrowed))
        for row, (record, uncertain) in zip(body, body_fields, strict=True):
            if not row:
                continue
            if _grid_footer(row):
                table_ends.append(min(w["y"] for w in row))
                claim(row)
                break
            if uncertain:
                if (
                    record.get("item_code")
                    and (record.get("description") or record.get("specification"))
                    and not record.get("quantity")
                ):
                    # Keep independently observed identity with empty quantity;
                    # leave the unassigned wide fragments visibly unresolved.
                    unresolved.append(_bounds(uncertain))
                else:
                    break
            clean.append(row)
            resolved.append(record)
        proposals = _business_rows(columns, clean, resolved, unresolved)
        for ordinal, line in enumerate(proposals):
            first = next((w for row in clean for w in row), None)
            if first is not None:
                entries.append((first["y"] + ordinal / 1000, first["x"], line))
        claim([w for row in clean for w in row])

    if not detected:
        return None
    contexts.sort(key=lambda context: context[0])
    outside = [[w for w in row if id(w) not in handled] for row in rows]

    def context_for(row):
        center = min(w["y"] + w["height"] / 2 for w in row)
        return next((context for context in reversed(contexts) if context[0] <= center), None)

    # Continuous wide boxes crossing both identity and quantity boundaries are
    # paragraph geometry. A separate quantity box makes a wide item different.
    wide = []
    for row in outside:
        context = context_for(row) if row else None
        if context is None:
            wide.append(False)
            continue
        _, xs, kinds, physical = context
        record, uncertain = _regional_fields(xs, kinds, row, physical)
        quantity_left = next((xs[i] for i, kind in enumerate(kinds) if kind == "quantity"), xs[-1])
        wide.append(
            bool(
                uncertain
                and not _structured(record)
                and any(w["x"] < quantity_left < w["x"] + w["width"] for w in uncertain)
            )
        )
    index = 0
    while index < len(outside):
        if not wide[index]:
            index += 1
            continue
        end = index + 1
        while (
            end < len(outside)
            and wide[end]
            and outside[end][0]["y"] - outside[end - 1][0]["y"]
            <= max(w["height"] for w in outside[end - 1]) * 3
        ):
            end += 1
        if end - index >= 2:
            claim([w for row in outside[index:end] for w in row])
            if index > 0 and outside[index - 1] and not wide[index - 1]:
                previous = outside[index - 1]
                context = context_for(previous)
                if (
                    context
                    and not _structured(
                        _regional_fields(context[1], context[2], previous, context[3])[0]
                    )
                    and previous[-1]["x"] + previous[-1]["width"] > context[1][1]
                ):
                    claim(previous)
        index = end

    for row in outside:
        row = [w for w in row if id(w) not in handled]
        if not row:
            continue
        if _grid_footer(row):
            table_ends.append(min(w["y"] for w in row))
            claim(row)
            continue
        context = context_for(row)
        if context is None:
            # Header metadata is not an unhandled merchandise region.
            continue
        record, uncertain = _regional_fields(context[1], context[2], row, context[3])
        safe = _structured(record)
        ended = any(context[0] <= end <= min(w["y"] for w in row) for end in table_ends)
        if ended:
            # A footer ends this header's authority. Column-aligned clauses
            # cannot be promoted to merchandise without a new independent header.
            safe = False
        claim(row, bool(uncertain or not safe))
        if safe and not uncertain:
            emit(record, row, context[2])
    if not contexts and words:
        unresolved.append(_bounds(words))
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    return {
        "lines": [line for _, _, line in entries][:200],
        "claimed_regions": claimed,
        "unresolved_regions": unresolved,
    }


def _grid_lines(page):
    """Compatibility helper; diagnostics are available through table_result."""
    if not page.get("table_grids"):
        return None
    result = table_result(page)
    return result["lines"] if result is not None else None


def table_lines(page):
    """Compatibility wrapper for older callers; candidate uses region diagnostics."""
    result = table_result(page)
    return result["lines"] if result is not None else None


def ordinal_header_regions(layout_lines):
    """Bounded strips for an observed header missing its leading ordinal label."""
    rows = _rows({"layout_lines": layout_lines})
    regions = []
    for index in range(len(rows)):
        header, _ = _header_at(rows, index)
        if header is None:
            continue
        columns, count, recognized = header
        if count != 1 or recognized < 3 or columns[0][0] != "item_code":
            continue
        anchors = [w for w in rows[index] if exact_header_kind([w]) is not None]
        if len(anchors) < 3:
            continue
        left = min(w["x"] for w in anchors)
        # Separate leading integers only trigger inspection; never delete them.
        if not any(
            w["text"].strip().isdigit()
            and 0 < len(w["text"].strip()) <= 3
            and w["width"] <= w["height"] * 3
            and w["x"] + w["width"] < left
            for row in rows[index + 1 : index + 4]
            for w in row
        ):
            continue
        top = min(w["y"] for w in anchors)
        bottom = max(w["y"] + w["height"] for w in anchors)
        regions.append(
            {
                "top": top,
                "bottom": bottom,
                "left": left,
                "anchors": anchors,
                "original_words": rows[index],
            }
        )
        if len(regions) == 2:
            break
    return regions
