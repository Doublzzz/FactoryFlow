"""Offline private oracle comparison; never imports OCR or writes business data.

CLI: python scripts/evaluate-ocr.py --truth PATH --candidates PATH --output PATH
Both UTF-8 JSON objects have schema_version: 1 and cases: [...]. Extra provenance
metadata is ignored, never echoed. Duplicate JSON keys are rejected.
Truth cases: case_id (C01..C9999, positive), split (development|retained), layout
(an ASCII safe marker, e.g. L01 or composite_header), source_sha256 (64 hex),
reviewed (boolean; manual_reviewed is an accepted equivalent), rows (list|null).
Rows require description, quantity, unit (strings|null); extra positioning metadata
is ignored. A reviewed truth requires complete nonempty description, valid quantity,
and a row list. An empty row list is legitimate reviewed zero-row truth.
Optional truth_row_count must equal list length; for pending rows=null it preserves
the known row denominator. Without it, total_truth_rows is null, known_truth_rows
and unknown_truth_row_cases disclose incompleteness. All cases stay in total_cases.
Candidate cases: case_id, source_sha256, rows (list of the same required fields).
Missing cases score failure; extra cases/hash mismatch/schema errors reject the run.

Description equivalence is NFKC plus collapsed whitespace only. Quantity follows
kernel Q01-Q05 (unsigned decimal, <=3 fractional digits, range/unit constraints),
with exact Decimal equality; floats, exponents, currency and signs are not quantities.
Units use kernel aliases; empty/null are equivalent absence, unknown labels compare
literally after NFKC/whitespace normalization, without inferred units.
Rows align by position, not fuzzy matching. Field counts use the full truth-row
denominator, including known pending rows; unreviewed rows earn no correct counts.
This is not precision/recall, a proof of zero spurious rows, or general OCR accuracy.
Output contains only anonymous markers, counts and statuses, never row data/hashes.
Exit 0 means a report was written (failed cases allowed); 2 means anonymous error.
The caller must retain the full frozen truth inventory: the evaluator cannot detect
cases omitted from both inputs or independently establish human review/source hashes.
"""

import argparse
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

from factoryflow.kernel.quantity import QuantityError, confirm_quantity

_ID = re.compile(r"C[0-9]{2,4}")
_HASH = re.compile(r"[0-9a-fA-F]{64}")
_MARKER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,47}")
_FIELDS = ("description", "quantity", "unit")


class EvaluationError(ValueError):
    """Only static codes and validated anonymous IDs may enter this exception."""


def _fail(code, case_id=None):
    raise EvaluationError(code if case_id is None else f"{code}:{case_id}")


def _text(value):
    return " ".join(unicodedata.normalize("NFKC", value).split())


def _quantity(row):
    value = row["quantity"]
    if value is None:
        return None
    try:
        return confirm_quantity(value, row["unit"]).value
    except QuantityError:
        return None


def _unit(value):
    if value is None or not value.strip():
        return None
    normalized = _text(value)
    return confirm_quantity("1", normalized).policy.canonical_unit or normalized


def _reviewed(case):
    value = case.get("reviewed", case.get("manual_reviewed"))
    if type(value) is not bool:
        _fail("INVALID_TRUTH", case["case_id"])
    if "reviewed" in case and "manual_reviewed" in case:
        if type(case["manual_reviewed"]) is not bool or case["reviewed"] != case["manual_reviewed"]:
            _fail("INVALID_TRUTH", case["case_id"])
    return value


def _inventory(document, truth):
    code = "INVALID_TRUTH" if truth else "INVALID_CANDIDATES"
    if (
        not isinstance(document, dict)
        or type(document.get("schema_version")) is not int
        or document["schema_version"] != 1
        or not isinstance(document.get("cases"), list)
    ):
        _fail(code)
    cases = {}
    for case in document["cases"]:
        if not isinstance(case, dict):
            _fail(code)
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not _ID.fullmatch(case_id) or int(case_id[1:]) < 1:
            _fail("INVALID_CASE_ID")
        if case_id in cases:
            _fail("DUPLICATE_CASE", case_id)
        source_hash = case.get("source_sha256")
        if not isinstance(source_hash, str) or not _HASH.fullmatch(source_hash):
            _fail(code, case_id)
        if "rows" not in case:
            _fail(code, case_id)
        rows = case["rows"]
        if truth:
            if case.get("split") not in ("development", "retained"):
                _fail(code, case_id)
            layout = case.get("layout")
            if not isinstance(layout, str) or not _MARKER.fullmatch(layout):
                _fail(code, case_id)
            reviewed = _reviewed(case)
            count = case.get("truth_row_count")
            if "truth_row_count" in case and (type(count) is not int or count < 0):
                _fail(code, case_id)
            if rows is None:
                if reviewed:
                    _fail(code, case_id)
                cases[case_id] = case
                continue
            if count is not None and isinstance(rows, list) and count != len(rows):
                _fail(code, case_id)
        if not isinstance(rows, list):
            _fail(code, case_id)
        for row in rows:
            if not isinstance(row, dict) or any(field not in row for field in _FIELDS):
                _fail(code, case_id)
            if any(row[field] is not None and not isinstance(row[field], str) for field in _FIELDS):
                _fail(code, case_id)
            if truth and reviewed:
                if (
                    not row["description"]
                    or not _text(row["description"])
                    or _quantity(row) is None
                ):
                    _fail(code, case_id)
        cases[case_id] = case
    if truth and not cases:
        _fail("EMPTY_TRUTH")
    return cases


def evaluate(truth, candidates):
    """Return anonymous ordered comparisons or static EvaluationError codes."""
    expected = _inventory(truth, True)
    actual = _inventory(candidates, False)
    for case_id in actual:
        if case_id not in expected:
            _fail("EXTRA_CASE", case_id)
        if actual[case_id]["source_sha256"].lower() != expected[case_id]["source_sha256"].lower():
            _fail("SOURCE_HASH_MISMATCH", case_id)
    summary = {
        "total_cases": len(expected),
        "passed_documents": 0,
        "row_count_equal": 0,
        "known_truth_rows": 0,
        "unknown_truth_row_cases": 0,
        "unreviewed_cases": 0,
        "missing_cases": 0,
        **{f"{field}_correct": 0 for field in _FIELDS},
    }
    results = []
    for case_id, case in expected.items():
        rows = case["rows"]
        count = len(rows) if rows is not None else case.get("truth_row_count")
        summary["known_truth_rows"] += count or 0
        summary["unknown_truth_row_cases"] += count is None
        reviewed = _reviewed(case)
        summary["unreviewed_cases"] += not reviewed
        proposed = actual.get(case_id)
        equal = proposed is not None and count is not None and len(proposed["rows"]) == count
        summary["row_count_equal"] += equal
        scores = {f"{field}_correct": 0 for field in _FIELDS}
        if reviewed and proposed is not None:
            for oracle, candidate in zip(rows, proposed["rows"], strict=False):
                for field in _FIELDS:
                    if field == "quantity":
                        value = _quantity(candidate)
                        matches = value is not None and value == _quantity(oracle)
                    elif field == "unit":
                        matches = _unit(oracle[field]) == _unit(candidate[field])
                    else:
                        matches = candidate[field] is not None and (
                            _text(oracle[field]) == _text(candidate[field])
                        )
                    scores[f"{field}_correct"] += matches
        passed = reviewed and equal and all(value == count for value in scores.values())
        if proposed is None:
            status = "missing_case"
            summary["missing_cases"] += 1
        elif not reviewed:
            status = "unreviewed"
        else:
            status = "pass" if passed else "fail"
        summary["passed_documents"] += passed
        for key, value in scores.items():
            summary[key] += value
        results.append(
            {
                "case_id": case_id,
                "split": case["split"],
                "layout": case["layout"],
                "status": status,
                "reviewed": reviewed,
                "truth_rows": count,
                "candidate_rows": len(proposed["rows"]) if proposed is not None else None,
                "row_count_equal": equal,
                **scores,
            }
        )
    summary["total_truth_rows"] = (
        None if summary["unknown_truth_row_cases"] else summary["known_truth_rows"]
    )
    return {"schema_version": 1, "alignment": "ordered_rows", "summary": summary, "cases": results}


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _read(path):
    with path.open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=_object)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        _fail("INVALID_ARGUMENTS")


def main(argv=None):
    """Guard all runtime failures; no exception details or private paths printed."""
    try:
        parser = _Parser(description="Anonymous ordered offline OCR evaluation", allow_abbrev=False)
        for name in ("truth", "candidates", "output"):
            parser.add_argument(f"--{name}", required=True, type=Path)
        args = parser.parse_args(argv)
        paths = [args.truth.resolve(), args.candidates.resolve(), args.output.resolve()]
        for index, left in enumerate(paths):
            for right in paths[index + 1 :]:
                if left == right or (left.exists() and right.exists() and left.samefile(right)):
                    _fail("PATH_CONFLICT")
        result = evaluate(_read(paths[0]), _read(paths[1]))
        # Atomic replacement avoids truncated reports on interrupted writes.
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=paths[2].parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                json.dump(result, stream, ensure_ascii=True, indent=2)
                stream.write("\n")
            os.replace(temporary, paths[2])
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return 0
    except EvaluationError as exc:
        print(str(exc), file=sys.stderr)
    except Exception:
        print("EVALUATION_INPUT_OR_OUTPUT_ERROR", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
