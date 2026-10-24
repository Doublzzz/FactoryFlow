"""Observed ordinal header only; generated data, no digit guessing."""

import time
from copy import deepcopy

import pytest
from factoryflow.modules.documents.adapters.ordinal_header import recover_ordinal_header
from factoryflow.modules.documents.domain.candidate import propose
from PIL import Image


def word(text, x, y=60, width=40):
    return {"text": text, "x": x, "y": y, "width": width, "height": 20}


def layout():
    return [
        {"words": [word("料号", 120), word("规格", 280), word("数量", 460)]},
        {
            "words": [
                word("1", 30, 130, 12),
                word("SYN-A", 120, 130, 60),
                word("合成材料", 280, 130, 80),
                word("12", 460, 130),
            ]
        },
    ]


def run(original, raw, budget=None, deadline=None):
    calls = []

    def recognize(image, *args):
        calls.append(image.size)
        return raw

    result = recover_ordinal_header(
        Image.new("RGB", (600, 400), "white"),
        original,
        None,
        0,
        "unused",
        time.monotonic() + 30 if deadline is None else deadline,
        {"remaining": 2} if budget is None else budget,
        recognize,
    )
    return result, calls


def raw_headers():
    return {
        "lines": [
            {
                "words": [
                    word("序号", 30, 20),
                    word("料号", 120, 20),
                    word("规格", 280, 20),
                    word("数量", 460, 20),
                ]
            }
        ],
        "text": "synthetic",
    }


def test_observed_header_recovers_ordinal_without_mutating_source():
    original = layout()
    before = deepcopy(original)
    (result, records), calls = run(original, raw_headers())
    assert len(calls) == 1
    assert original == before
    candidate = propose([], pages=[{"layout_lines": result}])
    assert candidate["lines"][0]["description"] == "SYN-A 合成材料"
    assert candidate["lines"][0]["quantity"] == "12"
    assert records[0]["accepted_words"][0]["text"] == "序号"
    assert records[0]["raw"] == raw_headers()


@pytest.mark.parametrize(
    "mutation", ["absent", "duplicate", "conflict", "shifted", "body", "invalid", "error"]
)
def test_ambiguous_observation_retains_original(mutation):
    original = layout()
    raw = raw_headers()
    words = raw["lines"][0]["words"]
    if mutation == "absent":
        words.pop(0)
    elif mutation == "duplicate":
        words.append(word("序号", 75, 20))
    elif mutation == "conflict":
        words[1]["text"] = "名称"
        words[2]["text"] = "单价"
    elif mutation == "shifted":
        for w in words[1:]:
            w["x"] += 100
    elif mutation == "body":
        words[0]["y"] = 60
    elif mutation == "invalid":
        words[0]["width"] = float("nan")
    else:
        raw["error_code"] = "OCR_TIMEOUT"
    (result, records), calls = run(original, raw)
    assert result == original
    assert records[0]["accepted_words"] == []


@pytest.mark.parametrize("reason", ["budget", "deadline", "no-leading-integer", "already-present"])
def test_ineligible_page_does_not_call_model(reason):
    original = layout()
    kwargs = {}
    if reason == "budget":
        kwargs["budget"] = {"remaining": 0}
    elif reason == "deadline":
        kwargs["deadline"] = time.monotonic() - 1
    elif reason == "no-leading-integer":
        original[1]["words"].pop(0)
    else:
        original[0]["words"].insert(0, word("序号", 30))
    (result, records), calls = run(original, raw_headers(), **kwargs)
    assert calls == [] and result == original and records == []


def test_optional_recognizer_exception_is_static_fallback():
    original = layout()

    def failing(*args):
        raise RuntimeError("synthetic provider detail must not escape")

    result, records = recover_ordinal_header(
        Image.new("RGB", (600, 400), "white"),
        original,
        None,
        0,
        "unused",
        time.monotonic() + 30,
        {"remaining": 2},
        failing,
    )
    assert result == original
    assert records[0]["raw"] == {"error_code": "OCR_HEADER_RECOVERY_UNAVAILABLE"}


def test_unknown_existing_header_is_not_overlaid():
    from factoryflow.modules.documents.adapters.ordinal_header import _accepted
    from factoryflow.modules.documents.domain.table_candidate import ordinal_header_regions

    region = ordinal_header_regions(layout())[0]
    region["original_words"] = [*region["original_words"], word("未知标签", 30)]
    assert _accepted(raw_headers(), region, 40, (600, 60)) == []


@pytest.mark.parametrize("failure", ["crop", "close"])
def test_optional_image_resource_errors_preserve_original(failure):
    original = layout()

    class FakeCrop:
        size = (600, 60)

        def close(self):
            raise RuntimeError("synthetic close detail")

    class FakeImage:
        width, height = 600, 400

        def crop(self, box):
            if failure == "crop":
                raise RuntimeError("synthetic crop detail")
            return FakeCrop()

    result, records = recover_ordinal_header(
        FakeImage(),
        original,
        None,
        0,
        "unused",
        time.monotonic() + 30,
        {"remaining": 2},
        lambda *args: raw_headers(),
    )
    assert result == original
    assert records[0]["raw"] == {"error_code": "OCR_HEADER_RECOVERY_UNAVAILABLE"}
