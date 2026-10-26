"""Self-contained deterministic delivery HTML; no I/O during construction/import."""

import json
from hashlib import sha256
from html import escape
from pathlib import Path

from factoryflow.modules.fulfillment.adapters.print_renderer import (
    PRINT_SCRIPT_URL,
    localized_defaults,
    render_delivery,
)


def render_archive_delivery(
    delivery: dict,
    layout: dict,
    version: int,
    *,
    locale: str = "zh-CN",
    script_path: Path | None = None,
) -> bytes:
    if locale not in ("zh-CN", "en"):
        raise ValueError("Unsupported archive locale")
    if version == 0 and locale == "en":
        layout = localized_defaults(locale)
    # Read only when a snapshot is requested. bootstrap may inject another renderer.
    if script_path is None:
        script_path = (
            Path(__file__).resolve().parents[7] / "apps" / "web" / "public" / "delivery-print.js"
        )
    script = script_path.read_text(encoding="utf-8")
    snapshot = json.dumps(
        {
            "delivery": delivery,
            "layout": layout,
            "version": version,
            "script": script,
            **({"locale": locale} if locale != "zh-CN" else {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    nonce = sha256(snapshot).hexdigest()
    html = render_delivery(delivery, layout, version, nonce=nonce, locale=locale)

    def e(value):
        return escape(str(value if value is not None else ""), quote=True)

    state = "已作废" if delivery["status"] == "void" else "有效"
    evidence = (
        '<div class="archive-mark">工作文件 · 生成时快照<br>'
        f"生成时状态：{state} · 送货版本 v{e(delivery['version'])} · 模板版本 v{e(version)}<br>"
        f"来源确认版本：{e(delivery['revision_id'])}<br>"
        "此离线副本仅记录生成时内容；后续修订或作废不会自动更新。</div>"
    )
    if locale == "en":
        state = "Void" if delivery["status"] == "void" else "Active"
        evidence = (
            '<div class="archive-mark">Work file · Snapshot at generation<br>'
            f"State at generation: {state} · Delivery v{e(delivery['version'])} "
            f"· Layout v{e(version)}<br>"
            f"Source confirmation revision: {e(delivery['revision_id'])}<br>"
            "This offline copy keeps its original contents; later changes or voids "
            "do not update it.</div>"
        )
    # heading is cloned by the trusted paginator, keeping this evidence on every printed page.
    html = html.replace('<div class="heading">', '<div class="heading">' + evidence, 1)
    html = html.replace('class="status">有效送货', 'class="status">生成时状态：有效', 1)
    html = html.replace(
        'class="status">Valid delivery', 'class="status">State at generation: Active', 1
    )
    html = html.replace(
        "</style>",
        ".archive-mark{font-size:7pt;font-weight:bold;overflow-wrap:anywhere}</style>",
        1,
    )
    external = f'<script nonce="{nonce}" src="{PRINT_SCRIPT_URL}" defer></script>'
    embedded = f'<script nonce="{nonce}">{script.replace("</script", "<\\/script")}</script>'
    html = html.replace(external, embedded, 1)
    return html.encode("utf-8")
