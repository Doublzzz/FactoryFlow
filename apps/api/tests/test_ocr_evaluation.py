"""Synthetic private-oracle evaluation; no native OCR or business writes."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "evaluate-ocr.py"


@pytest.fixture
def evaluator():
    spec = importlib.util.spec_from_file_location("ocr_evaluation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(description="Synthetic-A", quantity="2", unit="PCS"):
    return {"description": description, "quantity": quantity, "unit": unit}


def documents(rows=None, reviewed=True):
    rows = [row()] if rows is None else rows
    truth_case = {
        "case_id": "C01", "split": "development", "layout": "L01",
        "source_sha256": "a" * 64, "manual_reviewed": reviewed,
        "truth_row_count": len(rows), "rows": rows,
    }
    candidate = {
        "case_id": "C01", "source_sha256": "a" * 64, "rows": rows,
    }
    return {"schema_version": 1, "cases": [truth_case]}, {
        "schema_version": 1, "cases": [candidate],
    }


def test_missing_case_keeps_denominator(evaluator):
    truth, candidates = documents()
    candidates["cases"] = []
    result = evaluator.evaluate(truth, candidates)
    assert result["summary"]["total_cases"] == 1
    assert result["summary"]["total_truth_rows"] == 1
    assert result["summary"]["passed_documents"] == 0
    assert result["cases"][0]["status"] == "missing_case"


@pytest.mark.parametrize("field,value", [
    ("description", "Synthetic-B"), ("quantity", "20"), ("unit", "KG"),
])
def test_wrong_field_with_equal_row_count_fails(evaluator, field, value):
    truth, candidates = documents()
    candidates["cases"][0]["rows"] = [dict(row(), **{field: value})]
    result = evaluator.evaluate(truth, candidates)
    assert result["cases"][0]["row_count_equal"] is True
    assert result["summary"]["passed_documents"] == 0
    assert result["summary"][f"{field}_correct"] == 0


def test_empty_unit_and_aliases(evaluator):
    truth, candidates = documents([row(unit=None), row(unit="公斤")])
    candidates["cases"][0]["rows"] = [row(unit="  "), row(unit="KGS")]
    assert evaluator.evaluate(truth, candidates)["summary"]["passed_documents"] == 1
    candidates["cases"][0]["rows"][0]["unit"] = "PCS"
    assert evaluator.evaluate(truth, candidates)["summary"]["passed_documents"] == 0


@pytest.mark.parametrize("quantity", ["+2", "-2", "2e0", "2,000", "2.0000", "￥2", "NaN"])
def test_invalid_quantity_never_guessed(evaluator, quantity):
    truth, candidates = documents()
    candidates["cases"][0]["rows"] = [row(quantity=quantity)]
    assert evaluator.evaluate(truth, candidates)["summary"]["quantity_correct"] == 0


def test_nfkc_whitespace_and_decimal_only(evaluator):
    truth, candidates = documents([row(description="Ａ-1   部件", quantity="02.000")])
    candidates["cases"][0]["rows"] = [row(description="A-1\t部件", quantity="2")]
    assert evaluator.evaluate(truth, candidates)["summary"]["passed_documents"] == 1
    candidates["cases"][0]["rows"][0]["description"] = "A1 部件"
    assert evaluator.evaluate(truth, candidates)["summary"]["passed_documents"] == 0


def test_unreviewed_and_pending_keep_denominators(evaluator):
    truth, candidates = documents(reviewed=False)
    assert evaluator.evaluate(truth, candidates)["cases"][0]["status"] == "unreviewed"
    truth["cases"][0]["rows"] = None
    truth["cases"][0]["truth_row_count"] = 3
    result = evaluator.evaluate(truth, candidates)
    assert result["summary"]["total_truth_rows"] == 3
    assert result["summary"]["passed_documents"] == 0
    truth["cases"][0]["manual_reviewed"] = True
    with pytest.raises(evaluator.EvaluationError, match="INVALID_TRUTH"):
        evaluator.evaluate(truth, candidates)


def test_incomplete_truth_cannot_pass(evaluator):
    truth, candidates = documents([row(quantity=None)], reviewed=False)
    assert evaluator.evaluate(truth, candidates)["summary"]["quantity_correct"] == 0
    truth["cases"][0]["manual_reviewed"] = True
    with pytest.raises(evaluator.EvaluationError):
        evaluator.evaluate(truth, candidates)


def test_draft_provenance_unknown_denominator(evaluator):
    truth, candidates = documents(reviewed=False)
    truth["created"] = "PRIVATE-CUSTOMER"
    truth["cases"][0]["reviewed"] = truth["cases"][0].pop("manual_reviewed")
    truth["cases"][0]["rows"] = None
    del truth["cases"][0]["truth_row_count"]
    truth["cases"][0]["provenance"] = "PRIVATE-CUSTOMER"
    result = evaluator.evaluate(truth, candidates)
    assert result["summary"]["total_cases"] == 1
    assert result["summary"]["total_truth_rows"] is None
    assert result["summary"]["unknown_truth_row_cases"] == 1
    assert "PRIVATE" not in json.dumps(result)


def test_ordered_alignment_reports_full_row_denominator(evaluator):
    truth, candidates = documents([row(description="Synthetic-A"), row(description="Synthetic-B")])
    candidates["cases"][0]["rows"] = [row(description="Synthetic-B")]
    result = evaluator.evaluate(truth, candidates)
    assert result["summary"]["total_truth_rows"] == 2
    assert result["summary"]["description_correct"] == 0
    assert result["summary"]["quantity_correct"] == 1
    assert result["summary"]["passed_documents"] == 0


@pytest.mark.parametrize("mutation", ["empty", "layout", "hash", "count"])
def test_invalid_truth_is_rejected(evaluator, mutation):
    truth, candidates = documents()
    if mutation == "empty":
        truth["cases"] = []
    elif mutation == "layout":
        truth["cases"][0]["layout"] = "PRIVATE CUSTOMER"
    elif mutation == "hash":
        truth["cases"][0]["source_sha256"] = "PRIVATE"
    else:
        truth["cases"][0]["truth_row_count"] = 2
    with pytest.raises(evaluator.EvaluationError) as exc:
        evaluator.evaluate(truth, candidates)
    assert "PRIVATE" not in str(exc.value)


@pytest.mark.parametrize("mutation", ["duplicate", "extra", "hash", "id", "float", "money"])
def test_invalid_input_is_anonymous(evaluator, mutation):
    truth, candidates = documents()
    case = candidates["cases"][0]
    if mutation == "duplicate":
        candidates["cases"].append(dict(case))
    elif mutation == "extra":
        case["case_id"] = "C02"
    elif mutation == "hash":
        case["source_sha256"] = "b" * 64
    elif mutation == "id":
        case["case_id"] = "PRIVATE-CUSTOMER"
    elif mutation == "float":
        case["rows"] = [row(quantity=2.0)]
    else:
        case["rows"] = [{"description": "PRIVATE-CUSTOMER", "amount": "2", "unit": "PCS"}]
    with pytest.raises(evaluator.EvaluationError) as exc:
        evaluator.evaluate(truth, candidates)
    assert "PRIVATE" not in str(exc.value)


def test_cli_privacy_and_path_protection(evaluator, tmp_path, capsys):
    truth, candidates = documents([row(description="PRIVATE-CUSTOMER")])
    truth_path = tmp_path / "PRIVATE-truth.json"
    candidates_path = tmp_path / "PRIVATE-candidates.json"
    output = tmp_path / "result.json"
    truth_path.write_text(json.dumps(truth), encoding="utf-8")
    candidates_path.write_text(json.dumps(candidates), encoding="utf-8")
    args = ["--truth", str(truth_path), "--candidates", str(candidates_path)]
    assert evaluator.main([*args, "--output", str(output)]) == 0
    assert "PRIVATE" not in output.read_text(encoding="utf-8")
    before = truth_path.read_bytes()
    assert evaluator.main([*args, "--output", str(truth_path)]) == 2
    assert truth_path.read_bytes() == before
    candidates_path.write_text('{"PRIVATE-CUSTOMER":', encoding="utf-8")
    assert evaluator.main([*args, "--output", str(output)]) == 2
    assert evaluator.main(["--private-secret"]) == 2
    captured = capsys.readouterr()
    assert "PRIVATE" not in captured.out + captured.err
    assert str(tmp_path) not in captured.out + captured.err
