"""Read bounded XLSX XML values without evaluating formulas or passing numbers through float."""

import posixpath
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, localcontext
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.domain.candidate import propose
from factoryflow.modules.documents.domain.purchase_sheet import map_purchase_sheet, suggest_mapping
from openpyxl.styles.numbers import BUILTIN_FORMATS, is_date_format

MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_FILE = 2 * 1024 * 1024
MAX_EXPANDED = 20 * 1024 * 1024
MAX_ROWS, MAX_COLUMNS = 300, 30
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PART = re.compile(
    r"(?:\[Content_Types\]\.xml|_rels/\.rels|docProps/[\w.-]+\.xml|"
    r"xl/(?:workbook\.xml|styles\.xml|sharedStrings\.xml|theme/theme\d+\.xml|"
    r"_rels/workbook\.xml\.rels|worksheets/sheet\d+\.xml|"
    r"worksheets/_rels/sheet\d+\.xml\.rels))\Z"
)


def reject(code="PURCHASE_SHEET_UNSUPPORTED", field="file"):
    raise BusinessError(code, field=field)


def coordinate(value):
    found = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if found is None:
        reject(field="coordinate")
    column = 0
    for char in found[1]:
        column = column * 26 + ord(char) - 64
    row = int(found[2])
    if row > MAX_ROWS or column > MAX_COLUMNS:
        reject("PURCHASE_SHEET_LIMIT", "rows_columns")
    return row, column


def xml_parts(content):
    if not content or len(content) > MAX_FILE:
        reject("PURCHASE_SHEET_LIMIT")
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 400 or len({entry.filename for entry in entries}) != len(entries):
            reject(field="zip")
        if sum(entry.file_size for entry in entries) > MAX_EXPANDED:
            reject("PURCHASE_SHEET_LIMIT")
        parts = {}
        for entry in entries:
            if entry.flag_bits & 1:
                reject(field="encrypted")
            if entry.is_dir():
                continue
            if not PART.fullmatch(entry.filename):
                reject(field="workbook_parts")
            raw = archive.read(entry)
            if (
                len(raw) > MAX_EXPANDED
                or b"\x00" in raw
                or b"<!DOCTYPE" in raw.upper()
                or b"<!ENTITY" in raw.upper()
            ):
                reject(field="xml")
            root = ET.fromstring(raw)
            for node in root.iter():
                tag = node.tag.rsplit("}", 1)[-1]
                if tag == "Relationship" and node.get("TargetMode", "Internal") != "Internal":
                    reject(field="external_links")
                if tag in {
                    "oleObject",
                    "externalReference",
                    "tablePart",
                    "autoFilter",
                    "pivotTable",
                }:
                    reject(field=tag)
            parts[entry.filename] = root
    return parts


def styles(parts):
    root = parts.get("xl/styles.xml")
    if root is None:
        return ["General"]
    formats = dict(BUILTIN_FORMATS)
    custom = root.find(NS + "numFmts")
    if custom is not None:
        for item in custom:
            code = item.get("formatCode", "General")
            if len(code) > 256:
                reject("PURCHASE_SHEET_LIMIT", "number_format")
            formats[int(item.get("numFmtId"))] = code
    xfs = root.find(NS + "cellXfs")
    return (
        [formats.get(int(item.get("numFmtId", "0")), "General") for item in xfs]
        if xfs is not None
        else ["General"]
    )


def numeric_text(raw, number_format, date1904):
    if len(raw) > 80 or not re.fullmatch(
        r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[Ee][+-]?[0-9]{1,3})?", raw
    ):
        reject("PURCHASE_SHEET_INVALID", "number")
    with localcontext() as context:
        context.prec = 100
        value = Decimal(raw)
        if (
            not value.is_finite()
            or abs(value) >= Decimal("1e64")
            or value.as_tuple().exponent < -64
        ):
            reject("PURCHASE_SHEET_LIMIT", "number")
        if (
            is_date_format(number_format)
            and value == value.to_integral_value()
            and 0 <= value <= 1000000
        ):
            days = int(value)
            base = date(1904, 1, 1) if date1904 else date(1899, 12, 30)
            if not date1904 and 0 < days < 60:
                days += 1
            return (base + timedelta(days=days)).isoformat(), "date"
        result = format(value, "f")
        # Preserve displayed trailing zeroes only when formatting does not round the value.
        simple = re.fullmatch(r"(?:#,##)?0(?:\.(0{1,12}))?", number_format)
        if simple:
            places = len(simple[1] or "")
            rounded = value.quantize(Decimal(1).scaleb(-places))
            if rounded == value:
                result = format(rounded, "f")
        return result, "number"


def read_workbook(content):
    parts = xml_parts(content)
    workbook = parts["xl/workbook.xml"]
    relationships = {
        relation.get("Id"): relation.get("Target")
        for relation in parts["xl/_rels/workbook.xml.rels"]
    }
    strings = []
    shared = parts.get("xl/sharedStrings.xml")
    if shared is not None:
        for item in shared:
            strings.append("".join(node.text or "" for node in item.iter(NS + "t")))
    formats = styles(parts)
    properties = workbook.find(NS + "workbookPr")
    date1904 = properties is not None and properties.get("date1904") in {"1", "true"}
    populated = []
    total_text = 0
    for sheet in workbook.find(NS + "sheets"):
        target = relationships[sheet.get(REL + "id")]
        location = posixpath.normpath(
            target.lstrip("/") if target.startswith("/") else "xl/" + target
        )
        if not re.fullmatch(r"xl/worksheets/sheet[0-9]+\.xml", location):
            reject(field="sheet")
        xml = parts[location]
        hidden_columns = [
            (int(col.get("min")), int(col.get("max")))
            for col in xml.iter(NS + "col")
            if col.get("hidden") in {"1", "true"}
        ]
        rows, seen = [], set()
        for row in xml.iter(NS + "row"):
            cells = []
            for node in row.findall(NS + "c"):
                address = node.get("r", "")
                row_number, column = coordinate(address)
                if address in seen or int(row.get("r", row_number)) != row_number:
                    reject(field="coordinate")
                seen.add(address)
                kind, raw, formula = (
                    node.get("t", "n"),
                    node.findtext(NS + "v", ""),
                    node.find(NS + "f"),
                )
                fmt_index = int(node.get("s", "0"))
                if not 0 <= fmt_index < len(formats):
                    reject(field="style")
                number_format = formats[fmt_index]
                if kind == "s":
                    if not raw.isdigit() or int(raw) >= len(strings):
                        reject(field="shared_string")
                    value, view_kind = strings[int(raw)], "text"
                elif kind == "inlineStr":
                    value, view_kind = (
                        "".join(child.text or "" for child in node.iter(NS + "t")),
                        "text",
                    )
                elif kind in {"str", "d", "e", "b"}:
                    value, view_kind = (
                        raw,
                        {"e": "error", "b": "boolean", "d": "date"}.get(kind, "text"),
                    )
                elif kind in {"n", ""} and raw:
                    value, view_kind = numeric_text(raw, number_format, date1904)
                elif not raw:
                    value, view_kind = "", "text"
                else:
                    reject(field="cell_type")
                formula_text = formula.text or "" if formula is not None else None
                if max(len(value), len(raw), len(formula_text or "")) > 4000:
                    reject("PURCHASE_SHEET_LIMIT", "cell")
                if value or formula is not None:
                    if (
                        sheet.get("state", "visible") != "visible"
                        or row.get("hidden") in {"1", "true"}
                        or any(first <= column <= last for first, last in hidden_columns)
                    ):
                        reject("PURCHASE_SHEET_HIDDEN_DATA")
                total_text += (
                    len(value.encode()) + len(raw.encode()) + len((formula_text or "").encode())
                )
                if total_text > MAX_EXPANDED:
                    reject("PURCHASE_SHEET_LIMIT")
                cells.append(
                    {
                        "address": address,
                        "column": column,
                        "text": value,
                        "raw_value": raw,
                        "kind": view_kind,
                        "number_format": number_format,
                        "formula": formula_text,
                    }
                )
            if cells and any(cell["text"] or cell["formula"] is not None for cell in cells):
                rows.append(
                    {
                        "row_number": int(row.get("r")),
                        "cells": sorted(cells, key=lambda cell: cell["column"]),
                    }
                )
        if not rows:
            continue
        merges = []
        for merge in xml.iter(NS + "mergeCell"):
            endpoints = merge.get("ref", "").split(":")
            if len(endpoints) != 2:
                reject(field="merge")
            start_row, start_column = coordinate(endpoints[0])
            end_row, end_column = coordinate(endpoints[1])
            if start_row > end_row or start_column > end_column:
                reject(field="merge")
            merges.append(
                {
                    "first_row": start_row,
                    "last_row": end_row,
                    "first_column": start_column,
                    "last_column": end_column,
                }
            )
        populated.append(
            {
                "sheet_name": sheet.get("name", "Sheet"),
                "max_row": max(row["row_number"] for row in rows),
                "max_column": max(cell["column"] for row in rows for cell in row["cells"]),
                "rows": sorted(rows, key=lambda row: row["row_number"]),
                "merges": merges,
            }
        )
    if len(populated) != 1:
        reject("PURCHASE_SHEET_MULTIPLE_SHEETS")
    return populated[0]


def inspect_purchase_spreadsheet(content):
    try:
        sheet = read_workbook(content)
        mapping = suggest_mapping(sheet)
        error_code = None
        try:
            candidate = map_purchase_sheet(sheet, mapping)
        except BusinessError as error:
            candidate = propose([])
            error_code = error.code
        sheet["suggested_mapping"] = mapping
        return {
            "status": "failed" if error_code == "PURCHASE_IMPORT_TOO_MANY_LINES" else "ready",
            "error_code": error_code,
            "pages": [],
            "engine": "xlsx-xml-v1",
            "spreadsheet": sheet,
            "candidate": candidate,
        }
    except BusinessError:
        raise
    except (
        KeyError,
        ValueError,
        TypeError,
        AttributeError,
        IndexError,
        OSError,
        OverflowError,
        InvalidOperation,
        BadZipFile,
        ET.ParseError,
    ):
        reject("PURCHASE_SHEET_INVALID")
