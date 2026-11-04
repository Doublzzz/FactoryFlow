"""Escaped, fixed-layout purchase print using saved facts only."""

from html import escape


def render_purchase(order, locale="zh-CN"):
    if locale not in ("zh-CN", "en"):
        raise ValueError("Unsupported locale")

    def t(zh, en):
        return en if locale == "en" else zh

    def e(value):
        return escape(str(value if value is not None else ""), quote=True)

    title = t("采购单", "Purchase Order")
    headings = [
        t("序号", "No."),
        t("原料 / 规格", "Item / Specification"),
        t("单位", "Unit"),
        t("数量", "Quantity"),
        t("单价", "Unit price"),
        t("金额", "Amount"),
    ]
    rows = []
    for index, line in enumerate(order["lines"], 1):
        rows.append(
            f"<tr><td>{index}</td><td><strong>{e(line['material_name'])}</strong>"
            f"<div>{e(line['specification'])}</div><small>{e(line['own_code'])}</small></td>"
            f"<td>{e(line['canonical_unit'])}</td>"
            f'<td class="num">{e(line["ordered_quantity"])}</td>'
            f'<td class="num">{e(line.get("source_unit_price"))}</td>'
            f'<td class="num">{e(line.get("source_amount"))}</td></tr>'
        )
    closed = (
        f'<p class="closed">{t("已关闭", "Closed")} · {e(order["close_reason"])}</p>'
        if order["status"] == "closed"
        else ""
    )
    unknown = (
        '<p class="unknown">'
        + t("含未定金额项目，合计留空。", "Some amounts are not specified; total is left blank.")
        + "</p>"
        if order.get("total_amount") is None
        else ""
    )
    note = (
        f'<section class="note"><strong>{t("备注", "Notes")}</strong>'
        f"<p>{e(order['note'])}</p></section>"
        if order["note"]
        else ""
    )
    return f'''<!doctype html>
<html lang="{locale}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · {e(order["number"])}</title>
<style>
@font-face{{font-family:LocalCJK;
src:url('/fonts/NotoSansSC-Variable.ttf') format('truetype');font-display:swap}}
*{{box-sizing:border-box}}
body{{margin:0;color:#182532;background:#edf0f4;
font:13px LocalCJK,"Microsoft YaHei",sans-serif}}
.toolbar{{display:flex;justify-content:center;gap:16px;align-items:center;padding:16px}}
button{{font:inherit;padding:9px 18px;border:1px solid #34475c;
border-radius:6px;background:#fff;cursor:pointer}}
article{{max-width:210mm;margin:0 auto 24px;padding:12mm;background:#fff}}
h1{{font-size:26px;letter-spacing:3px;text-align:center;margin:0 0 8mm}}
.meta{{display:grid;grid-template-columns:1fr 1fr;gap:6px 18px;margin-bottom:6mm}}
.meta div,.note{{overflow-wrap:anywhere}}
.closed{{padding:8px;border:1px solid #586a7e}}
table{{border-collapse:collapse;width:100%;table-layout:fixed}}
th,td{{border:1px solid #74818e;padding:7px 6px;vertical-align:top;overflow-wrap:anywhere}}
th{{background:#f2f4f6;text-align:left;font-weight:600}}
th:nth-child(1){{width:7%}}th:nth-child(2){{width:35%}}th:nth-child(3){{width:9%}}
th:nth-child(4){{width:15%}}th:nth-child(5),th:nth-child(6){{width:17%}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}small{{color:#526171}}
.total{{display:flex;justify-content:flex-end;gap:16px;margin-top:14px;font-weight:600}}
.unknown{{text-align:right;font-size:12px}}
.note{{margin-top:20px;white-space:pre-wrap}}.note p{{margin:6px 0}}
@page{{size:A4 portrait;margin:12mm}}
@media print{{body{{background:white}}.toolbar{{display:none}}
article{{max-width:none;padding:0;margin:0}}thead{{display:table-header-group}}
tr{{break-inside:avoid}}.total,.unknown{{break-inside:avoid}}}}
@media screen and (max-width:700px){{body{{background:#fff}}article{{padding:12px}}
.meta{{grid-template-columns:1fr}}table{{font-size:11px}}th,td{{padding:5px 3px}}
h1{{font-size:22px}}.toolbar span{{display:none}}}}
</style><script src="/purchase-print.js?v=1" defer></script></head><body>
<div class="toolbar"><button id="print-purchase" type="button">
{t("打印采购单", "Print purchase order")}</button>
<span>{t("A4 · 纵向", "A4 · Portrait")}</span></div>
<article><h1>{title}</h1>{closed}<div class="meta">
<div>{t("采购方", "Buyer")}: {e(order.get("buyer_name"))}</div>
<div>{t("供应商", "Supplier")}: {e(order["supplier_name"])}</div>
<div>{t("采购单号", "PO number")}: {e(order["number"])}</div>
<div>{t("日期", "Date")}: {e(order["business_date"])}</div>
<div>{t("币种", "Currency")}: {e(order.get("currency"))}</div></div>
<table><thead><tr>{"".join(f"<th>{h}</th>" for h in headings)}</tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<div class="total"><span>{t("合计", "Total")} {e(order.get("currency"))}</span>
<span>{e(order.get("total_amount"))}</span></div>{unknown}{note}</article></body></html>'''
