"""Map an explicitly bounded worksheet range into editable purchase proposals."""

import re

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.domain.candidate import propose

FIELDS = {
    "item_code": {"料号", "物料编码", "物料编号", "品号", "itemcode", "itemno", "code", "partno"},
    "item_name": {
        "品名",
        "名称",
        "产品名称",
        "物料名称",
        "原料名称",
        "货物名称",
        "item",
        "itemname",
        "description",
        "product",
        "productname",
    },
    "specification": {"规格", "规格型号", "型号", "材质规格", "specification", "spec", "model"},
    "quantity": {"数量", "采购数量", "订购数量", "订货数量", "quantity", "qty", "orderqty"},
    "unit": {"单位", "计量单位", "unit", "uom"},
    "source_unit_price": {"单价", "采购单价", "含税单价", "unitprice", "price"},
    "source_amount": {"金额", "行金额", "含税金额", "amount", "linetotal", "totalprice"},
}


def plain(cell):
    # A formula cache has not been recalculated and cannot silently become a proposal.
    return (
        ""
        if cell.get("formula") is not None or cell.get("kind") in {"error", "boolean"}
        else cell["text"].strip()
    )


def header_key(value):
    return re.sub(r"[\s.：:()（）_/-]+", "", value).casefold()


def suggest_mapping(sheet):
    best = None
    for row in sheet["rows"]:
        if row["row_number"] > 50:
            break
        columns = {}
        for field, aliases in FIELDS.items():
            matching = [
                cell["column"] for cell in row["cells"] if header_key(plain(cell)) in aliases
            ]
            columns[field] = matching[0] if len(matching) == 1 else None
        if columns["item_name"] and columns["quantity"]:
            score = sum(column is not None for column in columns.values())
            if best is None or score > best[0]:
                best = score, row["row_number"], columns
    header, columns = (best[1], best[2]) if best else (1, {field: None for field in FIELDS})
    end = sheet["max_row"]
    # Keep the complete suffix until the person chooses an explicit end row.
    # A subtotal or note in the middle must never hide later business lines.
    return {
        "header_row": header,
        "first_row": header + 1,
        "last_row": max(header + 1, end),
        "columns": columns,
    }


def map_purchase_sheet(sheet, mapping):
    first, last, header = (mapping.get(k) for k in ("first_row", "last_row", "header_row"))
    if (
        any(type(value) is not int for value in (first, last, header))
        or not 1 <= header < first <= last <= sheet["max_row"]
    ):
        raise BusinessError("PURCHASE_SHEET_MAPPING", field="rows")
    columns = mapping.get("columns", {})
    if set(columns) - set(FIELDS) or not columns.get("item_name") or not columns.get("quantity"):
        raise BusinessError("PURCHASE_SHEET_MAPPING", field="columns")
    chosen = [value for value in columns.values() if value is not None]
    if any(
        type(value) is not int or not 1 <= value <= sheet["max_column"] for value in chosen
    ) or len(chosen) != len(set(chosen)):
        raise BusinessError("PURCHASE_SHEET_MAPPING", field="columns")
    if any(merge["first_row"] <= last and merge["last_row"] >= first for merge in sheet["merges"]):
        raise BusinessError("PURCHASE_SHEET_MERGED_DETAIL", field="rows")
    metadata = []
    for row in sheet["rows"]:
        if row["row_number"] < first:
            texts = [plain(cell) for cell in row["cells"]]
            metadata.extend([" ".join(texts), *texts])
    candidate = propose(metadata)
    candidate["lines"] = []
    for row in sheet["rows"]:
        if not first <= row["row_number"] <= last:
            continue
        if not any(cell["text"] or cell.get("formula") is not None for cell in row["cells"]):
            continue
        cells = {cell["column"]: cell for cell in row["cells"]}
        values = {
            field: plain(cells[column]) if column in cells else ""
            for field, column in columns.items()
        }
        candidate["lines"].append(
            {
                "description": " ".join(
                    values.get(field, "")
                    for field in ("item_name", "specification")
                    if values.get(field)
                ),
                "item_name": values.get("item_name", ""),
                "item_code": values.get("item_code") or None,
                "specification": values.get("specification") or None,
                "quantity": values.get("quantity", ""),
                "unit": values.get("unit") or None,
                "source_unit_price": values.get("source_unit_price") or None,
                "source_amount": values.get("source_amount") or None,
            }
        )
    if len(candidate["lines"]) > 200:
        raise BusinessError("PURCHASE_IMPORT_TOO_MANY_LINES", field="lines")
    return candidate
