"""Anonymous evidence for independent decimals crossing inferred price edges."""

from copy import deepcopy

import pytest
from factoryflow.modules.documents.domain.candidate import propose
from factoryflow.modules.documents.domain.table_candidate import _regional_fields, _source_price


def box(text, x, width, y=60, height=18):
    return {"text": text, "x": x, "width": width, "y": y, "height": height}


KINDS = ["description", "quantity", "source_unit_price", "source_amount", "ignored"]
EDGES = [0, 100, 200, 300, 400, 500]


def prices(words, *, kinds=KINDS, physical=False):
    fields, _ = _regional_fields(EDGES, kinds, words, physical=physical)
    return tuple(_source_price(fields.get(kind, [])) for kind in KINDS[2:4])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("peer_spills", [False, True])
def test_independent_same_row_decimal_pair_can_cross_one_inferred_edge(reverse, peer_spills):
    kinds = KINDS[:]
    first, second = "007.12340", "81.00900"
    if reverse:
        kinds[2:4] = reversed(kinds[2:4])
        first, second = second, first
    words = [box(first, 265, 45), box(second, 365, 45 if peer_spills else 30)]
    assert prices(words, kinds=kinds) == ("007.12340", "81.00900")


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "merged",
        "overlap",
        "duplicate",
        "row_mismatch",
        "quantity_cross",
        "identity_cross",
        "physical",
        "multiple_edges",
        "bad_literal",
        "wrong_center",
        "wrong_order",
        "ambiguous_parent",
        "tall_peer",
        "duplicate_headers",
        "nonadjacent",
        "split_literal",
    ],
)
def test_ambiguous_or_protected_crossings_do_not_recover_spilled_price(case):
    words = [box("007.12340", 265, 45), box("81.00900", 365, 45)]
    kinds = KINDS[:]
    physical = False
    if case == "missing":
        words.pop()
    elif case == "merged":
        words = [box("007.12340 81.00900", 265, 145)]
    elif case == "overlap":
        words[0]["width"] = 110
    elif case == "duplicate":
        words.append(deepcopy(words[0]))
    elif case == "row_mismatch":
        words[1]["y"] = 90
    elif case == "quantity_cross":
        kinds[-1] = "quantity"
    elif case == "identity_cross":
        kinds[-1] = "item_code"
    elif case == "physical":
        physical = True
    elif case == "multiple_edges":
        words[0].update(x=205, width=200)
    elif case == "bad_literal":
        words[1]["text"] = "81,00900"
    elif case == "wrong_center":
        words[0].update(x=290, width=45)
    elif case == "wrong_order":
        words[0]["x"] = 185
    elif case == "ambiguous_parent":
        words.append(box("007.12340", 210, 110))
    elif case == "tall_peer":
        words[1]["height"] = 70
    elif case == "duplicate_headers":
        kinds[-1] = "source_amount"
    elif case == "nonadjacent":
        kinds[3:] = ["ignored", "source_amount"]
        words[1]["x"] = 465
    elif case == "split_literal":
        words[1]["text"] = "81."
        words.append(box("00900", 380, 15))
    assert prices(words, kinds=kinds, physical=physical)[0] is None


@pytest.mark.parametrize("physical", [False, True])
def test_full_candidate_keeps_goods_literals_and_raw_trace_unchanged(physical):
    headers = ["料号", "品名", "规格", "数量", "单位", "单价", "金额", "备注"]
    header = [box(text, 32 + i * 100, 36, y=10) for i, text in enumerate(headers)]
    # Narrow header centers imply edges 500/600/700; independent right-aligned
    # decimals are wider and cross those estimated edges by ten pixels.
    values = ["SYN-Z", "合成零件", "M7 / green", "9", "PCS"]
    body = [box(text, 25 + i * 100, 40) for i, text in enumerate(values)]
    body += [box("007.12340", 565, 45), box("81.00900", 665, 45)]
    page = {"lines": [{"words": header}, {"words": body}], "rows": ["header", "body"]}
    if physical:
        page["table_grids"] = [{"x_edges": list(range(0, 801, 100)), "y_edges": [0, 40, 100]}]
    before = deepcopy(page)
    result = propose(page["rows"], pages=[page])["lines"]
    assert len(result) == 1
    assert result[0] == {
        "item_code": "SYN-Z",
        "item_name": "合成零件",
        "specification": "M7 / green",
        "description": "SYN-Z 合成零件 M7 / green",
        "quantity": "9",
        "unit": "PCS",
        "source_unit_price": None if physical else "007.12340",
        "source_amount": None if physical else "81.00900",
    }
    assert page == before
