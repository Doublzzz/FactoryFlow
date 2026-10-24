"""Create two visibly synthetic purchase orders. Optional authoring dependency: reportlab."""

import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FONT = ROOT / "apps/web/public/fonts/NotoSansSC-Variable.ttf"
DATA = json.loads((HERE / "purchase-order.json").read_text(encoding="utf-8"))
MONEY = Decimal("0.01")


def verify_data():
    assert DATA["synthetic"] is True
    amounts = []
    partial = []
    for index, row in enumerate(DATA["lines"]):
        quantity, price = Decimal(row["quantity"]), Decimal(row["unit_price"])
        amount = (quantity * price).quantize(MONEY, rounding=ROUND_HALF_UP)
        assert str(amount) == row["amount"]
        amounts.append(amount)
        delivered = Decimal(DATA["scenario"]["partial_delivery"]["quantities"][index])
        assert quantity - delivered == Decimal(
            DATA["scenario"]["partial_delivery"]["remaining"][index]
        )
        partial.append((delivered * price).quantize(MONEY, rounding=ROUND_HALF_UP))
        assert row["internal_item_code"].startswith("000")
    assert str(sum(amounts)) == DATA["total"]
    assert str(sum(partial)) == DATA["scenario"]["partial_delivery"]["expected_amount"]
    assert all(DATA[key]["email"].endswith(".example") for key in ("buyer", "supplier"))


def wrapped(value, font, size, width):
    lines = []
    for paragraph in str(value).split("\n"):
        words = (
            list(paragraph)
            if any("\u3400" <= c <= "\u9fff" for c in paragraph)
            else paragraph.split(" ")
        )
        separator = "" if any("\u3400" <= c <= "\u9fff" for c in paragraph) else " "
        line = ""
        for word in words:
            test = line + (separator if line else "") + word
            if line and pdfmetrics.stringWidth(test, font, size) > width:
                lines.append(line)
                line = word
            else:
                line = test
        lines.append(line)
    return lines


def text(
    c,
    value,
    x,
    y,
    *,
    size=9.5,
    width=500,
    leading=None,
    color="#172B3A",
    align="left",
    max_lines=None,
):
    leading = leading or size * 1.5
    lines = wrapped(value, "NotoSC", size, width)
    if max_lines is not None:
        assert len(lines) <= max_lines, (value, len(lines), max_lines)
    c.setFillColor(colors.HexColor(color))
    c.setStrokeColor(colors.HexColor(color))
    c.setLineWidth(0.12)
    for index, line in enumerate(lines):
        length = pdfmetrics.stringWidth(line, "NotoSC", size)
        assert length <= width + 0.2, (line, length, width)
        left = x + (width - length if align == "right" else 0)
        item = c.beginText(left, y - index * leading)
        item.setFont("NotoSC", size)
        # The licensed variable font's default master is Thin. A small outline
        # keeps the embedded subset legible without a separate font dependency.
        item.setTextRenderMode(2)
        item.textLine(line)
        c.drawText(item)
    return len(lines)


def box(c, x, y, width, height, fill="#FFFFFF", border="#D5DDE4"):
    c.setFillColor(colors.HexColor(fill))
    c.setStrokeColor(colors.HexColor(border))
    c.setLineWidth(0.6)
    c.rect(x, y, width, height, fill=1, stroke=1)


def render(locale):
    zh = locale == "zh"

    def pick(cn, en):
        return cn if zh else en

    output = HERE / f"purchase-order-{locale}.pdf"
    c = canvas.Canvas(str(output), pagesize=A4, pageCompression=1, invariant=1)
    c.setTitle(f"FactoryFlow Synthetic Purchase Order ({locale})")
    c.setAuthor("FactoryFlow Demo")
    c.setCreator("FactoryFlow synthetic sample generator")
    c.setSubject("Fictional purchase order for bilingual demonstration; no real transaction")
    page_width, page_height = A4
    margin = 36
    width = page_width - 2 * margin
    text(c, "FactoryFlow / SYNTHETIC SAMPLE", margin, 806, size=8, color="#607080")
    text(c, pick("采购订单", "PURCHASE ORDER"), margin, 772, size=24, width=335)
    text(c, pick("采购单号", "PO number"), 376, 805, size=8, width=180, color="#607080")
    text(c, DATA["order_number"], 376, 790, size=10, width=180)
    text(c, pick("订单日期", "Order date") + ": " + DATA["order_date"], 376, 772, size=9, width=180)
    box(c, margin, 727, width, 28, fill="#EFF4F8", border="#EFF4F8")
    text(
        c,
        pick("合成演示 - 非真实采购单 - 无交易效力", "SYNTHETIC DEMO - NOT A REAL PURCHASE ORDER"),
        margin + 12,
        737,
        size=9,
        width=width - 24,
        color="#374E63",
        max_lines=1,
    )

    column = (width - 14) / 2
    for key, left, label in (
        ("buyer", margin, pick("采购方", "BUYER")),
        ("supplier", margin + column + 14, pick("供应方", "SUPPLIER")),
    ):
        box(c, left, 598, column, 111)
        text(c, label, left + 10, 691, size=8, width=column - 20, color="#607080")
        text(c, DATA[key][locale], left + 10, 672, size=11, width=column - 20, max_lines=1)
        text(
            c,
            DATA[key][f"address_{locale}"],
            left + 10,
            651,
            size=8.5,
            width=column - 20,
            leading=12,
            max_lines=2,
        )
        text(c, DATA[key]["email"], left + 10, 615, size=8.5, width=column - 20)
    text(
        c,
        pick("收货方", "Deliver to") + ": " + DATA["delivery_contact"][locale],
        margin,
        578,
        size=9,
        width=width,
    )
    text(
        c,
        pick(
            "收货地点：采购方演示地址；分批送货请先确认。",
            "Ship to the fictional buyer address; confirm partial deliveries in advance.",
        ),
        margin,
        560,
        size=8.5,
        width=width,
        max_lines=1,
    )

    top = 540
    widths = [24, 63, width - 349, 43, 32, 58, 64, 65]
    assert abs(sum(widths) - width) < 0.01
    header_height, row_height = 39, 62
    headers = [
        pick("行", "No."),
        pick("客户 / 我方料号", "Customer / Internal code"),
        pick("品名 / 规格", "Item / Specification"),
        pick("数量", "Qty"),
        pick("单位", "Unit"),
        pick("单价\n(CNY)", "Unit price\n(CNY)"),
        pick("金额\n(CNY)", "Amount\n(CNY)"),
        pick("交期", "Required date"),
    ]
    left = margin
    for col_width, label in zip(widths, headers, strict=True):
        box(c, left, top - header_height, col_width, header_height, fill="#E9EFF4")
        text(c, label, left + 5, top - 14, size=7.5, width=col_width - 10, leading=10, max_lines=3)
        left += col_width
    for index, row in enumerate(DATA["lines"]):
        row_top = top - header_height - index * row_height
        values = [
            str(row["line"]),
            row["customer_item_code"] + "\n" + row["internal_item_code"],
            row[f"name_{locale}"] + "\n" + row["specification"],
            row["quantity"],
            row["unit"],
            f"{Decimal(row['unit_price']):.4f}",
            row["amount"],
            row["required_date"],
        ]
        left = margin
        for col_index, (col_width, value) in enumerate(zip(widths, values, strict=True)):
            box(
                c,
                left,
                row_top - row_height,
                col_width,
                row_height,
                fill="#FFFFFF" if index % 2 == 0 else "#F9FAFB",
            )
            text(
                c,
                value,
                left + 5,
                row_top - 19,
                size=8 if col_index != 2 else 8.5,
                width=col_width - 10,
                leading=13,
                align="right" if col_index in {3, 5, 6} else "left",
                max_lines=3,
            )
            left += col_width
    bottom = top - header_height - len(DATA["lines"]) * row_height
    box(c, margin, bottom - 34, width, 34, fill="#F1F5F8")
    text(
        c,
        pick(
            "价格已含税，不另加税；不混加不同单位数量。",
            "Tax included; no additional tax. Do not sum mixed units.",
        ),
        margin + 10,
        bottom - 20,
        size=8,
        width=width - 180,
        max_lines=1,
    )
    text(
        c,
        pick("合计 CNY ", "TOTAL CNY ") + DATA["total"],
        margin + width - 175,
        bottom - 21,
        size=13,
        width=165,
        align="right",
        max_lines=1,
    )

    note_top = bottom - 55
    text(
        c,
        pick("交付与核对要求", "DELIVERY AND REVIEW NOTES"),
        margin,
        note_top,
        size=9.5,
        width=width,
    )
    notes = [
        pick(
            "1. 请按本单料号及规格备货，包装注明采购单号、料号和数量。",
            "1. Match the listed item codes/specifications; "
            "label packages with the PO, item and quantity.",
        ),
        pick(
            "2. 如有交期或规格差异，请在发货前确认；送货单列明实际交付数量。",
            "2. Confirm any date/specification change before dispatch; "
            "list actual quantities on the delivery note.",
        ),
        pick(
            "3. 本例只展示订单版式，不表示产品已管理付款或所有采购条款。",
            "3. This layout is illustrative; "
            "it does not imply payment or procurement-terms functionality.",
        ),
    ]
    y = note_top - 18
    for note in notes:
        count = text(c, note, margin, y, size=8, width=width, leading=11, max_lines=2)
        y -= count * 11 + 5
    sign_y = y - 16
    for index, label in enumerate(
        [
            pick("制单（演示）", "Prepared (demo)"),
            pick("审核（演示）", "Reviewed (demo)"),
            pick("供方确认（演示）", "Supplier acknowledgment (demo)"),
        ]
    ):
        text(c, label, margin + index * width / 3, sign_y, size=8, width=width / 3 - 8, max_lines=1)
        c.setStrokeColor(colors.HexColor("#AAB7C2"))
        c.setLineWidth(0.6)
        c.line(
            margin + index * width / 3,
            sign_y - 19,
            margin + (index + 1) * width / 3 - 15,
            sign_y - 19,
        )
    assert sign_y - 19 > 61
    c.setStrokeColor(colors.HexColor("#CAD4DD"))
    c.line(margin, 49, margin + width, 49)
    text(
        c,
        pick(
            "所有主体、地址、单号和价格均为虚构。合成演示，无交易效力。",
            "All parties, addresses, identifiers and prices are fictional. Demonstration only.",
        ),
        margin,
        34,
        size=7.5,
        width=width - 42,
        max_lines=1,
    )
    text(c, "1 / 1", margin + width - 35, 34, size=8, width=35, align="right")
    c.showPage()
    c.save()
    return output.name


if __name__ == "__main__":
    verify_data()
    pdfmetrics.registerFont(TTFont("NotoSC", str(FONT)))
    for language in ("zh", "en"):
        print(render(language))
