"""Exact XML purchase candidates and explicit unsupported/coverage boundaries."""

from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.adapters.purchase_spreadsheet import (
    NS,
    inspect_purchase_spreadsheet,
)
from factoryflow.modules.documents.domain.purchase_sheet import map_purchase_sheet
from openpyxl import Workbook


def workbook(rows=1, change=None):
    book = Workbook()
    sheet = book.active
    sheet.title = "Synthetic Purchase"
    sheet.append(["Synthetic Purchase Order"])
    sheet.merge_cells("A1:G1")
    sheet.append(["采购单号: SYN-XLSX-1", "采购日期: 2026-10-27", "币种: USD"])
    sheet.append(["料号", "名称", "规格", "数量", "单位", "单价", "金额"])
    for number in range(rows):
        sheet.append([f"SYN-{number}", "Synthetic Raw", "Synthetic spec", 3, "KG", 2.5, 7.5])
        sheet.cell(number + 4, 6).number_format = "0.00"
        sheet.cell(number + 4, 7).number_format = "0.00"
    book.create_sheet("Blank")
    if change:
        change(book, sheet)
    content = BytesIO()
    book.save(content)
    return content.getvalue()


def rewrite(content, modify):
    result = BytesIO()
    with ZipFile(BytesIO(content)) as source, ZipFile(result, "w") as target:
        for entry in source.infolist():
            target.writestr(entry, modify(entry.filename, source.read(entry)))
    return result.getvalue()


def cell_xml(content, address, raw):
    def modify(name, value):
        if name != "xl/worksheets/sheet1.xml":
            return value
        root = ET.fromstring(value)
        cell = next(node for node in root.iter(NS + "c") if node.get("r") == address)
        stored = cell.find(NS + "v")
        if stored is None:
            stored = ET.SubElement(cell, NS + "v")
        stored.text = raw
        return ET.tostring(root)

    return rewrite(content, modify)


def test_header_merge_blank_spare_sheet_and_exact_formatted_zeroes():
    result = inspect_purchase_spreadsheet(workbook())
    assert result["status"] == "ready"
    assert result["candidate"]["order_number"] == "SYN-XLSX-1"
    assert result["candidate"]["business_date"] == "2026-10-27"
    assert result["candidate"]["currency"] == "USD"
    line = result["candidate"]["lines"][0]
    assert line["source_unit_price"] == "2.50" and line["source_amount"] == "7.50"
    assert result["spreadsheet"]["suggested_mapping"]["header_row"] == 3


def test_numeric_xml_value_keeps_digits_beyond_binary_float_and_never_rounds_to_style():
    value = "123456789012345678.123456"
    content = cell_xml(workbook(), "F4", value)
    content = cell_xml(content, "D4", "1.125")
    result = inspect_purchase_spreadsheet(content)
    assert result["candidate"]["lines"][0]["source_unit_price"] == value
    assert result["candidate"]["lines"][0]["quantity"] == "1.125"
    cell = next(
        c for row in result["spreadsheet"]["rows"] for c in row["cells"] if c["address"] == "F4"
    )
    assert cell["raw_value"] == value and cell["number_format"] == "0.00"


@pytest.mark.parametrize("cache", ["", "7.50"])
def test_formulas_keep_cache_and_expression_but_are_not_adopted(cache):
    content = workbook(change=lambda _, sheet: setattr(sheet["G4"], "value", "=D4*F4"))
    result = inspect_purchase_spreadsheet(cell_xml(content, "G4", cache))
    assert result["candidate"]["lines"][0]["source_amount"] is None
    cell = next(
        c for row in result["spreadsheet"]["rows"] for c in row["cells"] if c["address"] == "G4"
    )
    assert cell["formula"] == "D4*F4" and cell["text"] == cache


@pytest.mark.parametrize(
    "change",
    [
        lambda _, sheet: setattr(sheet.row_dimensions[4], "hidden", True),
        lambda _, sheet: setattr(sheet.column_dimensions["D"], "hidden", True),
        lambda _, sheet: setattr(sheet, "sheet_state", "hidden"),
    ],
)
def test_hidden_nonempty_data_is_rejected(change):
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_HIDDEN_DATA"):
        inspect_purchase_spreadsheet(workbook(change=change))


def test_hidden_blank_cells_are_allowed_but_filters_and_multiple_content_sheets_are_not():
    content = workbook(
        change=lambda _, sheet: setattr(sheet.column_dimensions["Z"], "hidden", True)
    )
    assert inspect_purchase_spreadsheet(content)["status"] == "ready"
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_UNSUPPORTED"):
        inspect_purchase_spreadsheet(
            workbook(change=lambda _, sheet: setattr(sheet.auto_filter, "ref", "A3:G4"))
        )
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_MULTIPLE_SHEETS"):
        inspect_purchase_spreadsheet(
            workbook(change=lambda book, _: book["Blank"].append(["nonempty"]))
        )


def test_merged_detail_requires_explicit_manual_restructuring():
    result = inspect_purchase_spreadsheet(
        workbook(change=lambda _, sheet: sheet.merge_cells("B4:C4"))
    )
    assert result["error_code"] == "PURCHASE_SHEET_MERGED_DETAIL"
    assert result["candidate"]["lines"] == []
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_MERGED_DETAIL"):
        map_purchase_sheet(result["spreadsheet"], result["spreadsheet"]["suggested_mapping"])


def test_201_business_rows_are_reported_and_not_truncated_to_200():
    result = inspect_purchase_spreadsheet(workbook(rows=201))
    assert result["status"] == "failed"
    assert result["error_code"] == "PURCHASE_IMPORT_TOO_MANY_LINES"
    assert result["candidate"]["lines"] == []
    assert len(result["spreadsheet"]["rows"]) == 204


def test_row_and_column_limits_and_invalid_xml_are_rejected():
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_LIMIT"):
        inspect_purchase_spreadsheet(
            workbook(change=lambda _, sheet: setattr(sheet["A301"], "value", "too far"))
        )
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_LIMIT"):
        inspect_purchase_spreadsheet(
            workbook(change=lambda _, sheet: setattr(sheet["AE4"], "value", "too far"))
        )
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_INVALID"):
        inspect_purchase_spreadsheet(b"not a workbook")


def test_xml_entities_external_links_and_embedded_objects_are_rejected():
    content = workbook()
    hostile = rewrite(
        content,
        lambda name, value: (
            b'<!DOCTYPE x [<!ENTITY x "bad">]>' + value if name == "xl/workbook.xml" else value
        ),
    )
    with pytest.raises(BusinessError):
        inspect_purchase_spreadsheet(hostile)
    external = rewrite(
        content,
        lambda name, value: (
            value.replace(b'Target="', b'TargetMode="External" Target="', 1)
            if name == "xl/_rels/workbook.xml.rels"
            else value
        ),
    )
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_UNSUPPORTED"):
        inspect_purchase_spreadsheet(external)
    augmented = BytesIO(content)
    with ZipFile(augmented, "a") as archive:
        archive.writestr("xl/vbaProject.bin", b"synthetic")
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_UNSUPPORTED"):
        inspect_purchase_spreadsheet(augmented.getvalue())


def test_mapping_is_explicit_and_does_not_skip_incomplete_rows():
    result = inspect_purchase_spreadsheet(
        workbook(rows=2, change=lambda _, sheet: setattr(sheet["D5"], "value", None))
    )
    assert len(result["candidate"]["lines"]) == 2
    assert result["candidate"]["lines"][1]["quantity"] == ""
    sheet = result["spreadsheet"]
    mapping = sheet["suggested_mapping"]
    with pytest.raises(BusinessError, match="PURCHASE_SHEET_MAPPING"):
        map_purchase_sheet(sheet, {**mapping, "columns": {"item_name": 2, "quantity": 2}})


def test_subtotal_does_not_hide_following_detail_and_error_boolean_are_not_values():
    def change(_, sheet):
        sheet["A5"] = "小计"
        sheet["D4"] = True
        sheet["F4"] = "#VALUE!"

    result = inspect_purchase_spreadsheet(workbook(rows=3, change=change))
    assert len(result["candidate"]["lines"]) == 3
    assert result["candidate"]["lines"][0]["quantity"] == ""
    assert result["candidate"]["lines"][0]["source_unit_price"] is None
