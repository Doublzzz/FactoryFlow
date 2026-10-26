"""Pure business classification for immutable work-file copies."""

import re
from datetime import date
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError

RULES = {"date", "customer", "month_customer"}
DEFAULT_RULE = "month_customer"
_KINDS = {"source": "订单原件", "delivery": "送货单", "statement_export": "对账草稿"}
_DEVICES = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\.|$)", re.I)


def _human(value: str, limit: int, fallback="未命名") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f\x7f]', "_", value).strip().rstrip(". ")
    value = value[:limit].rstrip(". ") or fallback
    if _DEVICES.match(value) or value in {".", ".."}:
        value = "_" + value
    return value


def english_labels(item: dict) -> dict:
    """Translate server-owned labels, retaining customer/file/order titles."""
    title, version, state = item["title"], item["version_label"], item["state_label"]
    if item["kind"] == "statement_export":
        title = "Final statement materials" if item["extension"] == "zip" else "Statement Excel"
    version = re.sub(r"^送货 v(\d+) · 模板 v(\d+)$", r"Delivery v\1 Layout v\2", version)
    version = re.sub(r"^(正式对账|对账) v(\d+)$", r"Statement v\2", version)
    version = re.sub(r"^确认版本 ", "Revision ", version)
    state = {
        "已确认": "Confirmed",
        "有效": "Active",
        "已作废": "Void",
        "已删除": "Deleted",
        "待归类": "Unclassified",
        "未确认": "Unconfirmed",
        "未生成": "Not generated",
        "生成中": "Pending",
        "生成失败": "Failed",
        "已生成": "Generated",
    }.get(state, state)
    return {"title": title, "version_label": version, "state_label": state}


def relative_path(rule: str, item: dict, *, locale="zh-CN") -> str:
    if rule not in RULES:
        raise BusinessError("ARCHIVE_RULE_INVALID")
    if locale not in ("zh-CN", "en"):
        raise BusinessError("UNSUPPORTED_LOCALE")
    english = locale == "en"
    fallback = "Unnamed" if english else "未命名"
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
        if english:
            category = {
                "订单原件": "Order originals",
                "送货单": "Delivery notes",
                "对账草稿": "Statements",
                "正式对账资料": "Final statement materials",
            }[category]
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
        segments = ["Work files" if english else "工作文件"]
        if day is None or (rule != "date" and (customer_id is None or not customer)):
            segments.append("Unclassified" if english else "待归类")
        else:
            if rule == "date":
                segments.extend([f"{day.year:04d}", f"{day.month:02d}", f"{day.day:02d}"])
            elif rule == "month_customer":
                segments.extend([f"{day.year:04d}", f"{day.month:02d}"])
            if rule != "date":
                segments.append(f"{_human(customer, 20, fallback)}_{customer_id[:8]}")
        title, version, state = item["title"], item["version_label"], item["state_label"]
        if english:
            labels = english_labels(item)
            title, version, state = labels["title"], labels["version_label"], labels["state_label"]
        title = _human(title, 30, fallback)
        version = _human(version, 20, fallback)
        state = _human(state, 12, fallback)
        separator = "_to_" if english else "至"
        period = f"_{day.isoformat()}{separator}{end.isoformat()}" if day and end else ""
        name = f"{title}_{version}_{state}{period}_{source_id}_{token[:12]}.{extension}"
        return "/".join([*segments, category, name])
    except KeyError, ValueError, TypeError, AttributeError:
        raise BusinessError("ARCHIVE_PATH_INVALID") from None
