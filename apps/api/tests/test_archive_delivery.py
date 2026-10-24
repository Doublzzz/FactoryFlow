"""Synthetic archive snapshots; browser/physical printing verified separately."""

from copy import deepcopy
from hashlib import sha256
from html.parser import HTMLParser
from uuid import UUID

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.fulfillment.adapters.print_renderer import render_delivery
from factoryflow.modules.fulfillment.domain.print_layout import default_layout

DELIVERY_ID = "00000000-0000-0000-0000-000000000011"
ORDER_ID = "00000000-0000-0000-0000-000000000012"
REVISION_ID = "00000000-0000-0000-0000-000000000013"
LINE_ID = "00000000-0000-0000-0000-000000000014"
KEY = f"delivery:{DELIVERY_ID}"


def delivery():
    return {
        "id": DELIVERY_ID,
        "order_id": ORDER_ID,
        "revision_id": REVISION_ID,
        "customer_id": "00000000-0000-0000-0000-000000000015",
        "customer_name": "合成客户<script>",
        "order_number": "SYN-ARCHIVE",
        "delivery_date": "2026-10-12",
        "status": "active",
        "version": 1,
        "void_reason": None,
        "lines": [
            {
                "order_line_id": LINE_ID,
                "line_number": 1,
                "description": "原始描述<unsafe>",
                "quantity": "1.250",
                "source_unit": "KG",
                "canonical_unit": "KG",
                "quantity_policy": {"warning_codes": []},
            }
        ],
    }


class Repository:
    def __init__(self):
        self.data = delivery()

    def get(self, actor, identifier):
        assert identifier == UUID(DELIVERY_ID)
        return deepcopy(self.data)

    def list(self, actor, customer_id, cursor, limit, order_id):
        assert customer_id is None and order_id is None
        assert cursor is None and limit == 10
        return {"items": [deepcopy(self.data)], "next_cursor": DELIVERY_ID}


class Layouts:
    version = 3

    def current(self, actor):
        return {"version": self.version, "config": default_layout()}


class Sources:
    def read(self, actor, references):
        assert references == {(ORDER_ID, REVISION_ID, LINE_ID)}
        return {
            ref: {
                "item_code": '<img src=x onerror="bad">',
                "item_name": "合成名称",
                "specification": "长规格\n末尾",
            }
            for ref in references
        }


def facade():
    from factoryflow.modules.fulfillment.adapters.archive_renderer import render_archive_delivery
    from factoryflow.modules.fulfillment.public import ArchiveDeliveries

    repository, layouts = Repository(), Layouts()
    return (
        ArchiveDeliveries(repository, layouts, Sources(), render_archive_delivery),
        repository,
        layouts,
    )


def test_public_facade_deterministic_capture_and_describe():
    service, repository, _ = facade()
    first = service.capture(None, KEY)
    assert service.capture(None, KEY) == first
    metadata, content = first
    assert service.describe(None, KEY) == metadata | {"byte_size": None}
    assert metadata["key"] == KEY and metadata["kind"] == "delivery"
    assert metadata["source_id"] == DELIVERY_ID
    assert metadata["title"] == "SYN-ARCHIVE"
    assert metadata["business_date"] == "2026-10-12"
    assert metadata["period_end"] is None
    assert "v1" in metadata["version_label"] and "v3" in metadata["version_label"]
    assert metadata["state_label"] == "有效"
    assert metadata["extension"] == "html" and metadata["available"] is True
    assert metadata["current"] is True and metadata["byte_size"] == len(content)
    assert len(metadata["token"]) == 64
    assert repository.data == delivery()


def test_catalog_explicit_pagination_and_layout_void_changes_tokens():
    service, repository, layouts = facade()
    page = service.catalog(None, None, 10)
    assert page["next_cursor"] == DELIVERY_ID
    original = page["items"][0]
    layouts.version += 1
    changed = service.describe(None, KEY)
    assert changed["token"] != original["token"]
    repository.data.update(status="void", version=2, void_reason="合成作废<b>原因</b>")
    changed_again, content = service.capture(None, KEY)
    assert changed_again["token"] != changed["token"]
    assert changed_again["state_label"] == "已作废"
    assert "合成作废&lt;b&gt;原因&lt;/b&gt;" in content.decode()


@pytest.mark.parametrize("key", ["other:" + DELIVERY_ID, "delivery:bad", "delivery:", None])
def test_invalid_source_key_is_business_error(key):
    service, _, _ = facade()
    with pytest.raises(BusinessError):
        service.capture(None, key)


@pytest.mark.parametrize("limit", [0, 51, True, "10"])
def test_invalid_catalog_limit(limit):
    service, _, _ = facade()
    with pytest.raises(BusinessError):
        service.catalog(None, None, limit)


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.details = None

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.scripts.append(dict(attrs))
        if dict(attrs).get("id") == "archive-details":
            self.details = dict(attrs)


def test_offline_bytes_keep_print_rows_without_a_reading_table():
    from factoryflow.modules.fulfillment.adapters.archive_renderer import render_archive_delivery

    data = delivery()
    data["lines"][0].update(item_code="<b>编号</b>", item_name="名称", specification="长" * 10000)
    data["lines"].append({**data["lines"][0], "item_name": "LAST-ROW-COMPLETE"})
    before = deepcopy(data)
    content = render_archive_delivery(data, default_layout(), 3)
    assert content == render_archive_delivery(data, default_layout(), 3)
    html = content.decode()
    elements = Elements()
    elements.feed(html)
    assert len(elements.scripts) == 1 and "src" not in elements.scripts[0]
    assert elements.details is None
    assert "完整明细" not in html and "阅读用" not in html
    assert '<section id="source" hidden>' in html
    assert "长" * 10000 in html and "LAST-ROW-COMPLETE" in html
    assert "&lt;b&gt;编号&lt;/b&gt;" in html and "<b>编号</b>" not in html
    assert "&lt;script&gt;" in html
    assert "工作文件 · 生成时快照" in html
    assert "生成时状态：有效" in html and "有效送货" not in html
    assert REVISION_ID in html and "送货版本 v1" in html and "模板版本 v3" in html
    assert "archive-details" not in html
    assert "单行内容无法完整排入一页" in html
    assert data == before
    assert (
        sha256(content).hexdigest()
        == sha256(render_archive_delivery(data, default_layout(), 3)).hexdigest()
    )


def test_normal_renderer_default_remains_external_and_nonce_is_optional():
    data = delivery()
    ordinary = render_delivery(data, default_layout(), 3)
    assert 'src="/delivery-print.js?v=a4-upper-half-1"' in ordinary
    assert "工作文件" not in ordinary
    stable = render_delivery(data, default_layout(), 3, nonce="synthetic-nonce")
    assert 'nonce="synthetic-nonce"' in stable
    assert stable == render_delivery(data, default_layout(), 3, nonce="synthetic-nonce")


def test_constructor_does_not_read_script_or_repositories(monkeypatch):
    from pathlib import Path

    from factoryflow.modules.fulfillment.adapters.archive_renderer import render_archive_delivery
    from factoryflow.modules.fulfillment.public import ArchiveDeliveries

    def forbidden(*args, **kwargs):
        raise AssertionError("constructor performed file I/O")

    monkeypatch.setattr(Path, "read_text", forbidden)
    service = ArchiveDeliveries(object(), object(), object(), render_archive_delivery)
    assert service.renderer is render_archive_delivery


def test_currentity_does_not_depend_on_rendering_and_preview_bytes_detect_code_changes(monkeypatch):
    from pathlib import Path

    service, _, _ = facade()
    original = service.describe(None, KEY)
    _, content = service.capture(None, KEY)
    original_read = Path.read_text

    def changed_script(path, *args, **kwargs):
        return original_read(path, *args, **kwargs) + "\n/* synthetic script change */"

    monkeypatch.setattr(Path, "read_text", changed_script)
    changed = service.describe(None, KEY)
    assert changed == original
    assert service.capture(None, KEY)[1] != content

    def unavailable(*_):
        raise RuntimeError("Synthetic renderer unavailable")

    service.renderer = unavailable
    assert service.describe(None, KEY) == original
