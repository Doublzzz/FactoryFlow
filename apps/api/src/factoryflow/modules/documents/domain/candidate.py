"""Conservative proposals, never business facts; raw OCR is stored separately."""

import re
from datetime import date

from factoryflow.kernel.quantity import confirm_quantity
from factoryflow.modules.documents.domain.table_candidate import table_result

_META = re.compile(
    r"(?:\b(?:tel|fax|telephone|phone)\b|联系电话|联系人|地址|供应商|客户名称|"
    r"^备注|^说明|^合计|^总计|^小计|^以下空白)",
    re.I,
)
_HEADER = re.compile(
    r"(?<![A-Za-z0-9_\u4e00-\u9fff])(?:"
    r"(?P<number>客户订单号|采购订单号|订单编号|采购单号|订单号|Order\s*(?:No\.?|Number))"
    r"|(?P<dated>订单日期|下单日期|采购日期|日期|Order\s+Date|Date))"
    r"(?:\s*[:：]\s*|\s+)",
    re.I,
)
_NEXT_FIELD = re.compile(
    r"(?:^|[\s;,；，|])(?:[\u4e00-\u9fff]{2,12}|[A-Za-z][A-Za-z ]{0,30})\s*[:：]"
)
_ORDER_CODE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9_./-]{0,98}[A-Za-z0-9])?")
_DATE_VALUE = re.compile(
    r"([0-9]{4})(?:([-/.])([0-9]{1,2})\2([0-9]{1,2})|年([0-9]{1,2})月([0-9]{1,2})日)"
)


def _header_values(raw: str) -> tuple[list[str], list[str], bool]:
    headers = list(_HEADER.finditer(raw))
    numbers, dates = [], []
    for index, header in enumerate(headers):
        # A generic English Date is not a delivery/signature date suffix.
        if (
            header["dated"]
            and header["dated"].lower() == "date"
            and re.search(
                r"(?:delivery|shipping|signature|signed|due)\s+$", raw[: header.start()], re.I
            )
        ):
            continue
        end = headers[index + 1].start() if index + 1 < len(headers) else len(raw)
        value = raw[header.end() : end]
        following = _NEXT_FIELD.search(value)
        if following:
            value = value[: following.start()]
        value = value.strip()
        if index + 1 < len(headers) or following:
            value = value.rstrip(";,；，|").strip()
        if header["number"]:
            if _ORDER_CODE.fullmatch(value):
                numbers.append(value)
        else:
            matched = _DATE_VALUE.fullmatch(value)
            if matched:
                try:
                    dates.append(
                        date(
                            int(matched[1]),
                            int(matched[3] or matched[5]),
                            int(matched[4] or matched[6]),
                        ).isoformat()
                    )
                except ValueError:
                    pass
    return numbers, dates, bool(headers)


def propose(rows: list[str], *, pages: list[dict] | None = None) -> dict:
    candidate = {
        "order_number": "",
        "business_date": "",
        "currency": "",
        "lines": [],
        "warnings": [],
    }
    numbers, dates = set(), set()
    for raw in rows:
        row_numbers, row_dates, metadata = _header_values(raw)
        numbers.update(row_numbers)
        dates.update(row_dates)
        line = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", raw).strip()
        if re.fullmatch(r"(?:币种|Currency)\s*[:：]\s*CNY", line, re.I):
            candidate["currency"] = "CNY"
        match = re.fullmatch(
            r"(.+?)\s+([+\-−＋－]?\s*[0-9]+(?:\s*[.,·．，。]\s*[0-9]+)?)"
            r"\s+([A-Za-z.\u4e00-\u9fff]{1,40})",
            line,
        )
        # Adapted from the legacy Parser's classify/filter + candidate eligibility:
        # free text needs a recognized unit; an explicit table column may still be unknown.
        if (
            match
            and not metadata
            and not _META.search(line)
            and confirm_quantity("1", match[3]).policy.mode != "UNKNOWN"
            and len(candidate["lines"]) < 200
        ):
            candidate["lines"].append(
                {
                    "description": match[1][:500],
                    "quantity": match[2],
                    "unit": match[3],
                    "source_unit_price": None,
                    "source_amount": None,
                }
            )
    candidate["order_number"] = next(iter(numbers)) if len(numbers) == 1 else ""
    candidate["business_date"] = next(iter(dates)) if len(dates) == 1 else ""
    if pages is not None:
        candidate["lines"] = []
        for number, page in enumerate(pages, start=1):
            result = table_result(page)
            if result is None:
                lines = propose(page["rows"])["lines"]
            else:
                lines = result["lines"]
                if result["unresolved_regions"]:
                    candidate["warnings"].append(
                        {"code": "TABLE_COVERAGE_UNRESOLVED", "page": page.get("number", number)}
                    )
            candidate["lines"].extend(lines)
        candidate["lines"] = candidate["lines"][:200]
    return candidate
