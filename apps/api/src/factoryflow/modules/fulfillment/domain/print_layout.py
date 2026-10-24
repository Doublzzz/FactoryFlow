"""Whitelisted presentation settings; no business fields or persistence."""

from factoryflow.kernel.contracts import BusinessError

TEXT_LIMITS = {
    "company_name": 100,
    "address": 240,
    "phone": 60,
    "fax": 60,
    "postcode": 20,
    "delivery_person": 60,
    "title": 40,
    "footer_note": 300,
}
BOUNDS = {
    "paper_width_mm": (100, 420),
    "paper_height_mm": (100, 420),
    "margin_top_mm": (0, 40),
    "margin_bottom_mm": (0, 40),
    "margin_left_mm": (0, 40),
    "margin_right_mm": (0, 40),
    "font_size_pt": (8, 16),
    "title_size_pt": (12, 26),
    "row_height_mm": (6, 18),
    "rows_per_page": (1, 30),
}
COLUMN_KEYS = (
    "index",
    "order_number",
    "item_code",
    "specification",
    "unit",
    "quantity",
    "note",
)


def default_layout() -> dict:
    return {
        **dict.fromkeys(TEXT_LIMITS, ""),
        "title": "送货单",
        "signatures": ["出货员签名", "送货员签名", "收货人 / 客户签收", "日期"],
        "paper_width_mm": 243,
        "paper_height_mm": 140,
        "margin_top_mm": 8,
        "margin_bottom_mm": 6,
        "margin_left_mm": 18,
        "margin_right_mm": 17,
        "font_size_pt": 9,
        "title_size_pt": 15,
        "row_height_mm": 8,
        "rows_per_page": 8,
        "columns": [
            {"key": key, "label": label, "width_mm": width}
            for key, label, width in zip(
                COLUMN_KEYS,
                ("序号", "订单号", "料号", "品名规格", "单位", "本次送货数量", "备注"),
                (9, 30, 36, 74, 11, 25, 23),
                strict=True,
            )
        ],
    }


def _invalid(field: str):
    raise BusinessError("DELIVERY_LAYOUT_INVALID", 422, field=field)


def _text(value, limit: int, field: str) -> str:
    if not isinstance(value, str) or len(value.strip()) > limit:
        _invalid(field)
    return value.strip()


def _integer(value, bounds: tuple[int, int], field: str) -> int:
    if type(value) is not int or not bounds[0] <= value <= bounds[1]:
        _invalid(field)
    return value


def normalize_layout(payload) -> dict:
    if not isinstance(payload, dict):
        _invalid("layout")
    required = set(TEXT_LIMITS) | set(BOUNDS) | {"signatures", "columns"}
    if set(payload) != required:
        _invalid("layout")
    result = {key: _text(payload[key], limit, key) for key, limit in TEXT_LIMITS.items()}
    if not result["title"]:
        _invalid("title")
    result.update({key: _integer(payload[key], bounds, key) for key, bounds in BOUNDS.items()})
    signatures = payload["signatures"]
    if not isinstance(signatures, list) or len(signatures) != 4:
        _invalid("signatures")
    result["signatures"] = [
        _text(value, 40, f"signatures.{index}") for index, value in enumerate(signatures)
    ]
    columns = payload["columns"]
    if not isinstance(columns, list) or len(columns) != 7:
        _invalid("columns")
    result["columns"] = []
    for index, column in enumerate(columns):
        field = f"columns.{index}"
        if not isinstance(column, dict) or set(column) != {"key", "label", "width_mm"}:
            _invalid(field)
        if column["key"] not in COLUMN_KEYS:
            _invalid(field + ".key")
        result["columns"].append(
            {
                "key": column["key"],
                "label": _text(column["label"], 30, field + ".label"),
                "width_mm": _integer(column["width_mm"], (6, 200), field + ".width_mm"),
            }
        )
        if not result["columns"][-1]["label"]:
            _invalid(field + ".label")
    if {column["key"] for column in result["columns"]} != set(COLUMN_KEYS):
        _invalid("columns")
    width = result["paper_width_mm"] - result["margin_left_mm"] - result["margin_right_mm"]
    if sum(column["width_mm"] for column in result["columns"]) > width:
        _invalid("columns")
    height = result["paper_height_mm"] - result["margin_top_mm"] - result["margin_bottom_mm"]
    if height < 60:
        _invalid("paper_height_mm")
    return result
