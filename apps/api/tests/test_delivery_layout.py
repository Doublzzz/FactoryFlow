"""Synthetic layout and markup checks; not browser or physical-print proof."""

import json

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.fulfillment.adapters.print_renderer import render_delivery
from factoryflow.modules.fulfillment.domain.print_layout import default_layout, normalize_layout


def delivery():
    return {
        "id": "synthetic-delivery",
        "revision_id": "synthetic-revision",
        "customer_name": "合成客户<script>",
        "order_number": "SYN-ORDER",
        "delivery_date": "2026-10-11",
        "status": "active",
        "void_reason": None,
        "unit_price": "PRIVATE-MONEY-MARKER",
        "lines": [
            {
                "line_number": 7,
                "description": "合成品",
                "quantity": "12.500",
                "item_code": '<img src=x onerror="alert(1)">',
                "item_name": "合成品名",
                "specification": "合成规格",
                "source_unit": "KG",
                "canonical_unit": "KG",
                "quantity_policy": {"warning_codes": ["UNIT_UNKNOWN"]},
                "amount": "PRIVATE-MONEY-MARKER",
            }
        ],
    }


def test_defaults_roundtrip_and_no_shared_mutability():
    original = default_layout()
    assert normalize_layout(json.loads(json.dumps(original))) == original
    result = normalize_layout(original)
    result["columns"][0]["label"] = "changed"
    result["signatures"][0] = "changed"
    assert original == default_layout()
    assert sum(c["width_mm"] for c in original["columns"]) == 208


def test_english_delivery_only_translates_explicit_product_labels():
    from factoryflow.modules.fulfillment.adapters.print_renderer import localized_defaults

    settings = localized_defaults("en")
    assert settings["title"] == "Delivery note"
    assert normalize_layout(settings) == settings
    html = render_delivery(delivery(), settings, 0, locale="en")
    assert '<html lang="en">' in html
    assert "Check unit" in html and "Delivery ID:" in html
    assert "合成客户&lt;script&gt;" in html and "合成品名 / 合成规格" in html
    assert "12.500" in html and "PRIVATE-MONEY-MARKER" not in html
    # A custom title equal to the Chinese default is still user-owned text.
    custom = default_layout()
    custom["company_name"] = "合成公司"
    custom_html = render_delivery(delivery(), custom, 2, locale="en", preview=True)
    assert "<h1>送货单</h1>" in custom_html and "合成公司" in custom_html
    assert "Layout preview" in custom_html
    assert default_layout()["title"] == "送货单"
    with pytest.raises(ValueError, match="locale"):
        render_delivery(delivery(), custom, 2, locale="fr")


@pytest.mark.parametrize(
    "field,value",
    [
        ("paper_width_mm", True),
        ("paper_height_mm", 99),
        ("font_size_pt", 9.0),
        ("row_height_mm", 19),
        ("rows_per_page", 0),
        ("company_name", "x" * 101),
        ("signatures", ["x"]),
        ("title", None),
        ("title", "  "),
        ("columns", []),
    ],
)
def test_rejects_invalid_fields(field, value):
    settings = default_layout()
    settings[field] = value
    with pytest.raises(BusinessError) as error:
        normalize_layout(settings)
    assert (error.value.code, error.value.status) == ("DELIVERY_LAYOUT_INVALID", 422)
    assert error.value.field


def test_rejects_missing_unknown_duplicate_columns_and_impossible_dimensions():
    changes = []
    missing = default_layout()
    del missing["title"]
    changes.append(missing)
    unknown = default_layout()
    unknown["status"] = "hide"
    changes.append(unknown)
    duplicate = default_layout()
    duplicate["columns"][0]["key"] = "note"
    changes.append(duplicate)
    width = default_layout()
    width["columns"][0]["width_mm"] = 200
    changes.append(width)
    height = default_layout()
    height.update(paper_height_mm=100, margin_top_mm=40, margin_bottom_mm=40)
    changes.append(height)
    extra = default_layout()
    extra["columns"][0]["hidden"] = True
    changes.append(extra)
    empty_label = default_layout()
    empty_label["columns"][0]["label"] = "  "
    changes.append(empty_label)
    invalid_key = default_layout()
    invalid_key["columns"][0]["key"] = []
    changes.append(invalid_key)
    for payload in changes:
        with pytest.raises(BusinessError):
            normalize_layout(payload)


def test_trim_and_column_permutation_are_canonical_without_changing_input():
    settings = default_layout()
    settings["company_name"] = "  合成公司  "
    settings["columns"].reverse()
    result = normalize_layout(settings)
    assert result["company_name"] == "合成公司"
    assert settings["company_name"].startswith("  ")
    assert result["columns"][0]["key"] == "note"


def test_markup_escapes_source_and_preserves_mandatory_evidence_without_money():
    settings = default_layout()
    settings["company_name"] = "<script>bad</script>"
    html = render_delivery(delivery(), settings, 3, preview=True)
    for value in (
        "synthetic-delivery",
        "synthetic-revision",
        "SYN-ORDER",
        "2026-10-11",
        "有效送货",
        "单位待核对",
        "12.500",
        "合成品名 / 合成规格",
        "当前预览设置",
    ):
        assert value in html
    assert "&lt;script&gt;bad&lt;/script&gt;" in html
    assert "<img src=x" not in html
    assert "PRIVATE-MONEY-MARKER" not in html
    assert 'src="/delivery-print.js?v=a4-upper-half-1"' in html
    assert "script-src 'nonce-" in html
    assert "overflow:hidden" not in html
    assert 'class="page-number"' in html
    assert "size:243mm 140mm" in html
    assert "版面预览 · 当前预览设置" in html
    assert "模板 v3" not in html
    assert "transform:none!important" in html


def test_void_reason_is_unconditionally_visible_and_escaped():
    data = delivery()
    data.update(status="void", void_reason="合成作废 <b>原因</b>")
    html = render_delivery(data, default_layout(), 1)
    assert "已作废 · 不作为有效送货" in html
    assert "作废原因：合成作废 &lt;b&gt;原因&lt;/b&gt;" in html


def test_print_direction_is_local_choice_without_rewriting_saved_layout():
    from html.parser import HTMLParser

    class Controls(HTMLParser):
        def __init__(self):
            super().__init__()
            self.direction = False
            self.options = []
            self.labels = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "select":
                self.direction = attrs.get("id") == "print-direction"
            if tag == "option" and self.direction:
                self.options.append(attrs)
            if tag == "label":
                self.labels.append(attrs.get("for"))

        def handle_endtag(self, tag):
            if tag == "select":
                self.direction = False

    settings = default_layout()
    before = json.dumps(settings, ensure_ascii=False, sort_keys=True)
    html = render_delivery(delivery(), settings, 3)
    controls = Controls()
    controls.feed(html)
    assert [item["value"] for item in controls.options] == ["template", "a4_upper_half"]
    assert "selected" in controls.options[0]
    assert "print-direction" in controls.labels
    assert '<style id="print-direction-style"></style>' in html
    assert 'data-paper-width="243" data-paper-height="140"' in html
    assert "A4 竖版 · 送货单放上半张" in html
    assert "不保存模板" in html
    assert "size:243mm 140mm" in html
    assert json.dumps(settings, ensure_ascii=False, sort_keys=True) == before
