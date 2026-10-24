"""Conservative axis-aligned raster table geometry; no OCR rewriting."""

from PIL import Image

_MAX_SIDE = 1024
_MAX_SEGMENTS = 2048


def _segments(pixels, width, height, vertical):
    outer, inner = (width, height) if vertical else (height, width)
    minimum = max(32, inner // 40 if vertical else inner // 10)
    segments = []
    for position in range(outer):
        start = None
        for offset in range(inner + 1):
            dark = (
                offset < inner
                and pixels[offset * width + position if vertical else position * width + offset]
                < 245
            )
            if dark and start is None:
                start = offset
            elif not dark and start is not None:
                if offset - start >= minimum:
                    segments.append((position, start, offset - 1))
                    if len(segments) > _MAX_SEGMENTS:
                        return None
                start = None
    # Adjacent scan lines of the same stroke are one edge, not narrow cells.
    groups = []
    for position, start, end in segments:
        group = next(
            (
                g
                for g in reversed(groups)
                if 0 <= position - g[-1][0] <= 2
                and abs(start - g[0][1]) <= 2
                and abs(end - g[0][2]) <= 2
            ),
            None,
        )
        if group is None:
            groups.append([(position, start, end)])
        else:
            group.append((position, start, end))
    return [
        (sum(s[0] for s in group) / len(group), min(s[1] for s in group), max(s[2] for s in group))
        for group in groups
    ]


def detect_table_grids(image):
    """Return x_edges/y_edges in original pixel coordinates, or [] if uncertain.

    Repeated column boundaries establish rows with physical horizontal borders.
    Missing interior lines are marked incomplete for domain-level row checks,
    including bounded trailing bands that could be merchandise or summary.
    A missing header top border
    is accepted only from aligned observed interior-line starts. Original-image
    conversion is capped at 20M pixels; scanning visits at most 2 * 1024**2 pixels.
    """
    width, height = image.size
    if width < 64 or height < 64 or width * height > 20_000_000:
        return []
    scale = min(1, _MAX_SIDE / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    # Classify before resizing: keep thin dark/gray rules but exclude pale cell fill.
    gray = (
        image.convert("L")
        .point(lambda value: 0 if value < 200 else 255)
        .resize(size, Image.Resampling.BILINEAR)
    )
    pixels = gray.tobytes()
    horizontal = _segments(pixels, *size, False)
    vertical = _segments(pixels, *size, True)
    if horizontal is None or vertical is None:
        return []
    groups = []
    for segment in horizontal:
        group = next(
            (
                g
                for g in groups
                if abs(g[0][1] - segment[1]) <= 2 and abs(g[0][2] - segment[2]) <= 2
            ),
            None,
        )
        if group is None:
            groups.append([segment])
        else:
            group.append(segment)
    grids = []
    for group in groups:
        ys = sorted(s[0] for s in group)
        if not 2 <= len(ys) <= 201:
            continue
        left, right = group[0][1:]
        borders = [
            s
            for s in vertical
            if left - 2 <= s[0] <= right + 2 and s[2] >= ys[0] and s[1] <= ys[-1]
        ]
        starts = [
            s[1]
            for s in borders
            if left + 2 < s[0] < right - 2 and s[1] < ys[0] - 8 and s[2] >= ys[0]
        ]
        open_header = bool(starts and max(starts) - min(starts) <= 2)
        if open_header:
            ys.insert(0, sum(starts) / len(starts))
        patterns = []
        for index, (top, bottom) in enumerate(zip(ys, ys[1:], strict=False)):
            active = [s for s in borders if s[1] <= top + 2 and s[2] >= bottom - 2]
            inner = sorted({s[0] for s in active if left + 2 < s[0] < right - 2})
            partial = any(
                left + 2 < s[0] < right - 2
                and s[1] < bottom - 2
                and s[2] > top + 2
                and (s[1] > top + 2 or s[2] < bottom - 2)
                for s in borders
            )
            broken_horizontal = any(
                top + 2 < s[0] < bottom - 2
                and s[2] > left
                and s[1] < right
                and (abs(s[1] - left) > 2 or abs(s[2] - right) > 2)
                for s in horizontal
            )
            outer = all(any(abs(s[0] - edge) <= 2 for s in active) for edge in (left, right))
            if (
                bottom - top < 8
                or partial
                or broken_horizontal
                or not (outer or (open_header and index == 0))
            ):
                patterns.append(None)
            elif inner:
                patterns.append([left, *inner, right])
            else:
                patterns.append([])
        # A row with all internal rules absent can inherit only identical,
        # directly observed column patterns on both sides of that gap.
        observed_patterns = list(patterns)
        for index, pattern in enumerate(patterns):
            if pattern != []:
                continue
            before = next((p for p in reversed(patterns[:index]) if p != []), None)
            after = next((p for p in patterns[index + 1 :] if p != []), None)
            if before and before == after:
                patterns[index] = before
        index = 0
        while index < len(patterns):
            pattern = patterns[index]
            end = index + 1
            while pattern and end < len(patterns) and patterns[end] in (pattern, []):
                end += 1
            if (
                pattern
                and end - index >= 2
                and len(pattern) <= 33
                and min(b - a for a, b in zip(pattern, pattern[1:], strict=False)) >= 8
            ):
                grids.append(
                    {
                        "x_edges": [round(x * width / size[0], 3) for x in pattern],
                        "y_edges": [round(y * height / size[1], 3) for y in ys[index : end + 1]],
                        "row_complete": [p == pattern for p in observed_patterns[index:end]],
                    }
                )
                if len(grids) == 8:
                    return grids
            index = end
    return grids
