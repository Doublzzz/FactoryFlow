"""Pure business classification for immutable work-file copies."""

import re
from datetime import date
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError

RULES = {"date", "customer", "month_customer"}
DEFAULT_RULE = "month_customer"
_KINDS = {"source": "订单原件", "delivery": "送货单", "statement_export": "对账草稿"}
_DEVICES = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)


def _human(value: str, limit: int) -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", value).strip().rstrip(". ")
    value = value[:limit].rstrip(". ") or "未命名"
    if _DEVICES.match(value) or value in {".", ".."}:
        value = "_" + value
    return value


def relative_path(rule: str, item: dict) -> str:
    if rule not in RULES:
        raise BusinessError("ARCHIVE_RULE_INVALID")
    try:
        kind = item["kind"]
        category = _KINDS[kind]
        source_id = str(UUID(item["source_id"]))
        if item["key"] != f"{kind}:{source_id}":
            raise ValueError
        extension = item["extension"]
        if extension not in {"png", "jpg", "pdf", "html", "xlsx"} and not (
            kind == "statement_export" and extension == "zip"
        ):
            raise ValueError
        if kind == "statement_export" and extension == "zip":
            category = "正式对账资料"
        token = item["token"]
        if not re.fullmatch(r"[0-9a-f]{64}", token):
            raise ValueError
        day = date.fromisoformat(item["business_date"]) if item.get("business_date") else None
        if day and day.isoformat() != item["business_date"]:
            raise ValueError
        end = date.fromisoformat(item["period_end"]) if item.get("period_end") else None
        if end and (end.isoformat() != item["period_end"] or (day and end < day)):
            raise ValueError
        customer_id = str(UUID(item["customer_id"])) if item.get("customer_id") else None
        customer = item.get("customer_name")
        segments = ["工作文件"]
        if day is None or (rule != "date" and (customer_id is None or not customer)):
            segments.append("待归类")
        else:
            if rule == "date":
                segments.extend([f"{day.year:04d}", f"{day.month:02d}", f"{day.day:02d}"])
            elif rule == "month_customer":
                segments.extend([f"{day.year:04d}", f"{day.month:02d}"])
            if rule != "date":
                segments.append(f"{_human(customer, 20)}_{customer_id[:8]}")
        title = _human(item["title"], 30)
        version = _human(item["version_label"], 20)
        state = _human(item["state_label"], 12)
        period = f"_{day.isoformat()}至{end.isoformat()}" if day and end else ""
        name = f"{title}_{version}_{state}{period}_{source_id}_{token[:12]}.{extension}"
        return "/".join([*segments, category, name])
    except KeyError, ValueError, TypeError, AttributeError:
        raise BusinessError("ARCHIVE_PATH_INVALID") from None
