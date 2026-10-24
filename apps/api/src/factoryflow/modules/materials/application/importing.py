"""Construct the full import decision under the catalog's existing transaction lock."""

import hashlib
import json
from collections import defaultdict
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.materials.domain.material import prepare_material, signature, text_value

FIELDS = ("own_code", "name", "specification", "unit", "customer_code")


def inspection(table):
    return {
        "file_hash": table["file_hash"],
        "sheet_name": table["sheet_name"],
        "header_row": table["header_row"],
        "columns": [
            {"index": index, "label": value} for index, value in enumerate(table["headers"], 1)
        ],
        "samples": [
            {"row_number": row["row_number"], "values": [cell["text"] for cell in row["cells"]]}
            for row in table["rows"][:20]
        ],
        "data_row_count": len(table["rows"]),
    }


def mapped_rows(table, payload):
    columns = payload["columns"]
    if set(columns) - set(FIELDS) or not columns.get("name"):
        raise BusinessError("MATERIAL_IMPORT_MAPPING", field="columns")
    indexes = [value for value in columns.values() if value is not None]
    if len(set(indexes)) != len(indexes) or any(
        type(index) is not int or not 1 <= index <= len(table["headers"]) for index in indexes
    ):
        raise BusinessError("MATERIAL_IMPORT_MAPPING", field="columns")
    choices = {}
    numbers = {row["row_number"] for row in table["rows"]}
    for choice in payload.get("choices", []):
        number = choice["row_number"]
        target = choice.get("material_id")
        version = choice.get("expected_material_version")
        confirmed = choice.get("confirmed_numeric_fields", [])
        if (
            type(number) is not int
            or number not in numbers
            or number in choices
            or choice["action"] not in {"default", "create", "reuse", "skip"}
            or ((target is not None or version is not None) and choice["action"] != "reuse")
            or (
                choice["action"] == "reuse"
                and (not target or type(version) is not int or version < 1)
            )
            or len(set(confirmed)) != len(confirmed)
            or set(confirmed) - {"own_code", "customer_code"}
        ):
            raise BusinessError("MATERIAL_IMPORT_MAPPING", field="choices")
        choices[number] = choice
    rows = []
    for original in table["rows"]:
        values = {}
        cells = {}
        for field in FIELDS:
            index = columns.get(field)
            cell = (
                original["cells"][index - 1]
                if index is not None
                else {"text": "", "kind": "text", "number_format": None}
            )
            values[field] = cell["text"].strip() or ("" if field == "name" else None)
            cells[field] = cell
        rows.append(
            {
                "row_number": original["row_number"],
                "source": values,
                "cells": cells,
                "choice": choices.get(original["row_number"], {}),
            }
        )
    return rows


def build_import_plan(catalog, actor, table, payload):
    rows = mapped_rows(table, payload)
    customer = payload.get("customer_id")
    if customer:
        catalog.customers.require(actor, customer)
    candidate_cache = {}
    own_cache = {}
    mapping_cache = {}
    states = []
    for row in rows:
        source, choice = row["source"], row["choice"]
        row.update(
            action=None if choice.get("action") == "default" else choice.get("action"),
            issues=[],
            warnings=[],
            numeric_fields=[],
            material=None,
            candidates=[],
        )
        if row["action"] == "skip":
            states.append({"row_number": row["row_number"], "source": source, "action": "skip"})
            continue
        try:
            row["data"] = prepare_material(source)
            text_value(source["customer_code"], "customer_code", 100)
        except BusinessError as error:
            row["issues"].append(
                "NAME_REQUIRED"
                if not source["name"]
                else "INVALID_" + (error.field or "ROW").upper()
            )
            states.append({"row_number": row["row_number"], "source": source, "invalid": True})
            continue
        for field in ("own_code", "customer_code"):
            cell = row["cells"][field]
            if not source[field] or cell["kind"] == "text":
                continue
            if (
                cell["kind"] != "number"
                or abs(Decimal(cell["text"])) >= 10**15
                or len(Decimal(cell["text"]).as_tuple().digits) > 15
            ):
                row["issues"].append("UNSAFE_" + field.upper())
                continue
            row["numeric_fields"].append(
                {"field": field, "value": cell["text"], "number_format": cell.get("number_format")}
            )
            if field not in choice.get("confirmed_numeric_fields", []):
                row["issues"].append("NUMERIC_" + field.upper() + "_CONFIRM")
        code = source["own_code"]
        if code and code not in own_cache:
            own_cache[code] = catalog.repository.by_own_code(actor, code)
        existing = own_cache.get(code)
        if choice.get("action") == "reuse":
            material = catalog.require(actor, choice["material_id"], active=False)
            row["material"] = material
            if material["version"] != choice["expected_material_version"]:
                row["issues"].append("TARGET_VERSION_CHANGED")
            if code and material["own_code"] != code:
                row["issues"].append("TARGET_CODE_DIFFERS")
            row["warnings"].append("REUSE_KEEPS_EXISTING")
        elif row["action"] == "create":
            if existing:
                row["issues"].append("OWN_CODE_EXISTS")
        elif existing:
            row["material"] = existing
            if all(existing[field] == source[field] for field in ("name", "specification", "unit")):
                row["action"] = "reuse"
            else:
                row["issues"].append("EXISTING_CODE_DIFFERS")
                row["candidates"] = [existing]
        else:
            row["action"] = "create"
            if not code and source["name"]:
                key = (source["name"], source["specification"])
                if key not in candidate_cache:
                    candidate_cache[key] = catalog.repository.import_candidates(actor, *key)
                row["candidates"] = candidate_cache[key]
                if row["candidates"]:
                    row["issues"].append("CANDIDATE_REVIEW")
        if row["material"] and not row["material"]["active"]:
            row["issues"].append("TARGET_INACTIVE")
        row["mapping"] = None
        if source["customer_code"]:
            if not customer:
                row["issues"].append("CUSTOMER_REQUIRED")
            else:
                code_key = source["customer_code"]
                if code_key not in mapping_cache:
                    mapping_cache[code_key] = catalog.repository.code(actor, customer, code_key)
                row["mapping"] = mapping_cache[code_key]
                if row["mapping"]:
                    remembered = signature({**source, "item_name": source["name"]})
                    if (
                        not row["material"]
                        or row["mapping"]["material_id"] != row["material"]["id"]
                        or any(row["mapping"][key] != value for key, value in remembered.items())
                    ):
                        row["issues"].append("CUSTOMER_CODE_CONFLICT")
        if source["unit"] and not signature({"unit": source["unit"]})["canonical_unit"]:
            row["warnings"].append("UNKNOWN_UNIT")
        states.append(
            {
                "row_number": row["row_number"],
                "source": source,
                "existing_code": existing,
                "target": row["material"],
                "mapping": row["mapping"],
            }
        )
    groups = {
        field: defaultdict(list)
        for field in ("own_code", "customer_code", "anonymous_name", "anonymous_specification")
    }
    for row in rows:
        if row["action"] == "skip":
            continue
        source = row["source"]
        for field in ("own_code", "customer_code"):
            if source[field]:
                groups[field][source[field]].append(row)
        if not source["own_code"]:
            for field in ("name", "specification"):
                if source[field]:
                    groups["anonymous_" + field][source[field]].append(row)
    for field, buckets in groups.items():
        for duplicate in buckets.values():
            if len(duplicate) < 2:
                continue
            for row in duplicate:
                row["warnings"].append("FILE_DUPLICATE")
                if field == "customer_code" or (
                    field == "own_code" and any(item["action"] != "reuse" for item in duplicate)
                ):
                    row["issues"].append("DUPLICATE_" + field.upper())
                elif field.startswith("anonymous_") and row["choice"].get("action") in {
                    None,
                    "default",
                }:
                    row["issues"].append("BATCH_CANDIDATE_REVIEW")
    for row, state in zip(rows, states, strict=True):
        row["issues"] = list(dict.fromkeys(row["issues"]))
        row["warnings"] = list(dict.fromkeys(row["warnings"]))
        if row["issues"]:
            row["action"] = "pending"
        state.update(action=row["action"], issues=row["issues"])
    stable = {
        key: value
        for key, value in payload.items()
        if key not in {"content_base64", "preview_fingerprint"}
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {"file_hash": table["file_hash"], "input": stable, "rows": states},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    public_rows = [
        {
            key: row[key]
            for key in (
                "row_number",
                "source",
                "action",
                "issues",
                "warnings",
                "numeric_fields",
                "material",
                "candidates",
            )
        }
        for row in rows
    ]
    return {
        "file_hash": table["file_hash"],
        "preview_fingerprint": fingerprint,
        "ready": bool(rows)
        and all(row["action"] != "pending" for row in rows)
        and any(row["action"] != "skip" for row in rows),
        "rows": public_rows,
    }, rows
