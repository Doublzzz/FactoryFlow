"""The same escaped delivery document for preview and printing."""

from html import escape
from secrets import token_urlsafe

from factoryflow.modules.fulfillment.domain.print_layout import default_layout, normalize_layout

PRINT_SCRIPT_URL = "/delivery-print.js?v=a4-upper-half-1"


def localized_defaults(locale="zh-CN"):
    """Only create built-in wording; never infer ownership from a saved label's text."""
    if locale not in ("zh-CN", "en"):
        raise ValueError("Unsupported print locale")
    settings = default_layout()
    if locale == "en":
        settings["title"] = "Delivery note"
        settings["signatures"] = ["Dispatched by", "Delivered by", "Received by / Customer", "Date"]
        for column, label in zip(
            settings["columns"],
            ("No.", "PO number", "Item code", "Item / Specification", "Unit", "Quantity", "Notes"),
            strict=True,
        ):
            column["label"] = label
    return settings


def render_delivery(
    delivery: dict,
    layout: dict,
    version: int,
    *,
    preview: bool = False,
    nonce: str | None = None,
    locale: str = "zh-CN",
) -> str:
    if locale not in ("zh-CN", "en"):
        raise ValueError("Unsupported print locale")

    def text(chinese, english):
        return english if locale == "en" else chinese

    settings = normalize_layout(layout)
    nonce = token_urlsafe(24) if nonce is None else nonce

    def e(value) -> str:
        return escape(str(value if value is not None else ""), quote=True)

    columns = settings["columns"]
    rows = []
    for index, line in enumerate(delivery["lines"], 1):
        specification = " / ".join(
            str(line.get(key) or "") for key in ("item_name", "specification") if line.get(key)
        ) or line.get("description", "")
        warning = bool(line.get("quantity_policy", {}).get("warning_codes"))
        values = {
            "index": index,
            "order_number": delivery["order_number"],
            "item_code": line.get("item_code", ""),
            "specification": specification,
            "unit": line.get("source_unit")
            or line.get("canonical_unit")
            or text("未填写", "Not set"),
            "quantity": line["quantity"],
            "note": text("单位待核对", "Check unit") if warning else "",
        }
        rows.append(
            "<tr>"
            + "".join(
                f'<td data-column="{column["key"]}">{e(values[column["key"]])}</td>'
                for column in columns
            )
            + "</tr>"
        )
    colgroup = "".join(f'<col style="width:{c["width_mm"]}mm">' for c in columns)
    headings = "".join(f"<th>{e(c['label'])}</th>" for c in columns)
    signatures = "".join(
        f"<div>{e(label)}<br>________________</div>" for label in settings["signatures"]
    )
    status = (
        text("已作废 · 不作为有效送货", "Void · Not a valid delivery")
        if delivery["status"] == "void"
        else text("有效送货", "Valid delivery")
    )
    reason = (
        f'<div class="void-reason">{text("作废原因：", "Void reason: ")}'
        f"{e(delivery.get('void_reason'))}</div>"
        if delivery["status"] == "void"
        else ""
    )
    contact = "　".join(
        f"{label}：{e(settings[key])}"
        for key, label in (
            ("phone", text("电话", "Phone")),
            ("fax", text("传真", "Fax")),
            ("postcode", text("邮编", "Postcode")),
        )
        if settings[key]
    )
    width = settings["paper_width_mm"]
    height = settings["paper_height_mm"]
    content_width = width - settings["margin_left_mm"] - settings["margin_right_mm"]
    content_height = height - settings["margin_top_mm"] - settings["margin_bottom_mm"]
    table_width = sum(c["width_mm"] for c in columns)
    version_label = (
        text("版面预览 · 当前预览设置", "Layout preview · Current preview settings")
        if preview
        else text(
            f"FactoryFlow · 送货打印模板 v{e(version)}",
            f"FactoryFlow · Delivery layout v{e(version)}",
        )
    )
    paper_label = text("本次打印用纸", "Paper for this print")
    template_label = text(
        f"沿用模板（{width} × {height} mm）", f"Template size ({width} × {height} mm)"
    )
    a4_label = text("A4 竖版 · 送货单放上半张", "A4 portrait · Delivery note on upper half")
    measuring_label = text("正在测量分页…", "Laying out pages…")
    customer_label = text("客户：", "Customer: ")
    ship_label = text("送往：", "Ship to: ")
    date_label = text("日期：", "Date: ")
    po_label = text("订单：", "PO number: ")
    page_label = text("第", "Page")
    page_unit = text("页", "")
    template_hint = text(
        f"模板纸张 {width} × {height} mm，100% 缩放，关闭浏览器页眉页脚。",
        f"Template paper {width} × {height} mm. "
        "Use 100% scale and disable browser headers and footers.",
    )
    print_hint = text(
        "只影响本次打印，不保存模板。A4 模式保持送货单原版式，等比例放在上半张，下半张留空。"
        "打印对话框选 A4、每张纸 1 页、缩放 100%，关闭页眉页脚。",
        "Applies to this print only. The saved layout is unchanged. "
        "A4 mode fits the note proportionally on the upper half and leaves the lower half blank. "
        "In the print dialog choose A4, one page per sheet, 100% scale, and no headers or footers.",
    )
    return f'''<!doctype html><html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none';
style-src 'unsafe-inline'; script-src 'nonce-{nonce}'">
<title>{e(settings["title"])}</title><style>
*{{box-sizing:border-box}}body{{margin:0;color:#000;background:#eee;
font:{settings["font_size_pt"]}pt "Microsoft YaHei",sans-serif}}
.toolbar{{padding:12px;background:white}}.toolbar button,.toolbar select{{padding:6px 18px}}
.print-options{{display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-bottom:8px}}
.toolbar small{{display:block;margin-top:6px}}
.page-frame{{margin:8mm auto}}
.print-paper{{position:relative;transform-origin:top left;background:white;
width:{width}mm;height:{height}mm}}
.sheet{{transform-origin:top left;
width:{width}mm;height:{height}mm;background:white;margin:0;
padding:{settings["margin_top_mm"]}mm {settings["margin_right_mm"]}mm
{settings["margin_bottom_mm"]}mm {settings["margin_left_mm"]}mm;
break-after:page;page-break-after:always}}
.sheet:last-child{{break-after:auto;page-break-after:auto}}
.paper-content{{width:{content_width}mm;height:{content_height}mm;display:flex;flex-direction:column}}
.heading,.signatures,.trace{{flex-shrink:0}}.company{{font-size:12pt;font-weight:bold;text-align:center}}
.address,.contact{{text-align:center}}h1{{font-size:{settings["title_size_pt"]}pt;
text-align:center;margin:2mm 0}}
.meta{{display:flex;flex-wrap:wrap;gap:1mm 5mm;margin:1mm 0}}
.trace{{font-size:7pt;overflow-wrap:anywhere;margin:1mm 0}}
.status{{font-weight:bold}}.void-reason{{font-weight:bold;white-space:pre-wrap}}
table{{border-collapse:collapse;table-layout:fixed;width:{table_width}mm;flex-shrink:0}}
th,td{{border:1px solid black;padding:1mm;overflow-wrap:anywhere;white-space:pre-wrap;
line-height:1.3;text-align:center}}th{{font-weight:normal}}td{{height:{settings["row_height_mm"]}mm}}
.signatures{{display:flex;justify-content:space-between;gap:2mm;min-height:24mm;
padding-top:4mm;margin-top:auto;overflow-wrap:anywhere}}
.signatures>div{{flex:1;min-width:0}}.footer-note{{white-space:pre-wrap}}
.page-counter{{text-align:right}}[hidden]{{display:none!important}}
#problem{{white-space:pre-wrap;color:#a00;font-weight:bold}}.blocked{{outline:3px solid #a00}}
@page{{size:{width}mm {height}mm;margin:0}}
@media print{{body{{background:white}}.toolbar{{display:none}}
.page-frame{{margin:0;width:auto!important;height:auto!important;
break-after:page;page-break-after:always}}
.page-frame:last-child{{break-after:auto;page-break-after:auto}}
.print-paper{{transform:none!important}}
.sheet{{margin:0;break-after:auto;page-break-after:auto}}
body[data-blocked="true"] #pages{{display:none}}
body[data-blocked="true"] .toolbar{{display:block}}}}
</style><style id="print-direction-style"></style></head><body data-preview="{str(preview).lower()}"
data-paper-width="{width}" data-paper-height="{height}"
data-rows-per-page="{settings["rows_per_page"]}" data-blocked="true">
<div class="toolbar"><div class="print-options">
<label for="print-direction">{paper_label}</label><select id="print-direction">
<option value="template" selected>{template_label}</option>
<option value="a4_upper_half">{a4_label}</option></select>
<button id="print-button" disabled>{text("打印", "Print")}</button></div>
<span id="print-status">{measuring_label}</span><div id="problem" role="alert"></div>
<small id="print-direction-hint" role="status">{template_hint}</small>
<small>{print_hint}</small></div>
<div id="pages"></div><section id="source" hidden>
<div class="heading"><div class="company">{e(settings["company_name"])}</div>
<div class="address">{e(settings["address"])}</div><div class="contact">{contact}</div>
<h1>{e(settings["title"])}</h1><div class="status">{status}</div>{reason}
<div class="meta"><span>{customer_label}{e(delivery["customer_name"])}</span>
<span>{ship_label}________</span>
<span>{date_label}{e(delivery["delivery_date"])}</span><span>{po_label}{e(delivery["order_number"])}</span>
<span>{text("送货人：", "Delivered by: ")}{e(settings["delivery_person"])}</span></div>
<div class="trace">{text("送货标识：", "Delivery ID: ")}{e(delivery["id"])}<br>
{text("来源确认版本：", "Source revision: ")}{e(delivery["revision_id"])}</div></div>
<table><colgroup>{colgroup}</colgroup><thead><tr>{headings}</tr></thead><tbody>{"".join(rows)}</tbody></table>
<div class="signatures">{signatures}</div>
<div class="trace document-footer"><div class="footer-note">{e(settings["footer_note"])}</div>
<div>{version_label}</div><div class="page-counter">
{page_label} <span class="page-number">1</span> / <span class="page-total">1</span> {page_unit}
</div></div>
</section><script nonce="{nonce}" src="{PRINT_SCRIPT_URL}" defer></script></body></html>'''
