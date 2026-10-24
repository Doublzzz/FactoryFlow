"""M2 public HTTP workflow against disposable real PostgreSQL databases only."""

import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from conftest import SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import event, text
from test_material_import import workbook_bytes


def csv_body(
    content=(
        "own,name,spec,unit,customer\n"
        "000123,Synthetic bracket,S-1,PCS,A-017\n,Synthetic pad,S-2,KG,\n"
    ),
):
    return {
        "filename": "synthetic.csv",
        "content_base64": base64.b64encode(content.encode()).decode(),
        "header_row": 1,
    }


def mapped(content=None, **overrides):
    return {
        **(csv_body() if content is None else csv_body(content)),
        "columns": {"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": None},
        "customer_id": None,
        "choices": [],
    } | overrides


def preview(pg, body):
    response = pg.api.command("/api/v1/materials/imports/preview", body)
    assert response.status_code == 200, response.text
    return response.json()


def confirm(pg, body, result, key=None):
    return pg.api.command(
        "/api/v1/materials/imports/confirm",
        body | {"preview_fingerprint": result["preview_fingerprint"]},
        key,
    )


def counts(pg):
    with pg.owner.connect() as conn:
        return {
            name: conn.execute(text(f"SELECT count(*) FROM {name}")).scalar_one()
            for name in (
                "materials",
                "customer_material_codes",
                "orders",
                "audit_events",
                "command_results",
            )
        }


def test_import_before_orders_is_preview_only_then_atomic_and_replayable(pg):
    before = counts(pg)
    inspected = pg.api.command("/api/v1/materials/imports/inspect", csv_body())
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["data_row_count"] == 2
    body = mapped()
    result = preview(pg, body)
    assert result["ready"] is True
    assert counts(pg) == before
    key = uuid4()
    saved = confirm(pg, body, result, key)
    assert saved.status_code == 200, saved.text
    rows = saved.json()["rows"]
    assert [row["row_number"] for row in rows] == [2, 3]
    assert rows[0]["material"]["own_code"] == "000123"
    assert rows[1]["material"]["own_code"].startswith("WL")
    assert counts(pg)["materials"] == 2 and counts(pg)["orders"] == 0
    assert confirm(pg, body, result, key).json() == saved.json()
    changed = body | {"choices": [{"row_number": 3, "action": "skip"}]}
    assert confirm(pg, changed, result, key).status_code == 409


def test_explicit_numbers_are_inserted_before_automatic_numbers(pg):
    body = mapped(
        "own,name\n,Synthetic automatic\nWL000001,Synthetic explicit\n",
        columns={"own_code": 1, "name": 2},
    )
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200, saved.text
    assert [row["material"]["own_code"] for row in saved.json()["rows"]] == ["WL000002", "WL000001"]


def test_duplicates_missing_names_and_skip_are_explicit_and_never_partially_written(pg):
    body = mapped(
        "own,name\nDUP,Synthetic first\nDUP,Synthetic first\nEMPTY,\n",
        columns={"own_code": 1, "name": 2},
    )
    result = preview(pg, body)
    assert result["ready"] is False
    assert "DUPLICATE_OWN_CODE" in result["rows"][0]["issues"]
    assert "NAME_REQUIRED" in result["rows"][2]["issues"]
    assert confirm(pg, body, result).status_code == 422
    assert counts(pg)["materials"] == 0
    body["choices"] = [{"row_number": 3, "action": "skip"}, {"row_number": 4, "action": "skip"}]
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200, saved.text
    assert [row["action"] for row in saved.json()["rows"]] == ["create", "skip", "skip"]
    assert saved.json()["rows"][1]["reason"]
    assert counts(pg)["materials"] == 1


def test_reimport_reuses_exact_code_but_no_code_only_offers_candidates(pg):
    body = mapped()
    assert confirm(pg, body, preview(pg, body)).status_code == 200
    again = preview(pg, body)
    assert again["rows"][0]["action"] == "reuse"
    assert again["rows"][1]["action"] == "pending"
    assert again["rows"][1]["candidates"]
    candidate = again["rows"][1]["candidates"][0]
    body["choices"] = [
        {
            "row_number": 3,
            "action": "reuse",
            "material_id": candidate["id"],
            "expected_material_version": candidate["version"],
        }
    ]
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200 and counts(pg)["materials"] == 2
    different = mapped(
        "own,name\n000123,Synthetic incompatible name\n", columns={"own_code": 1, "name": 2}
    )
    assert preview(pg, different)["ready"] is False


@pytest.mark.parametrize("second_spec", ["S-1", "S-2"])
def test_batch_similar_without_codes_requires_decisions_even_with_different_customer_codes(
    pg, second_spec
):
    body = mapped(
        "own,name,spec,unit,customer\n,Synthetic shared name,S-1,PCS,C1\n"
        f",Synthetic shared name,{second_spec},PCS,C2\n",
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    shown = preview(pg, body)
    assert shown["ready"] is False
    assert all("BATCH_CANDIDATE_REVIEW" in row["issues"] for row in shown["rows"])
    body["choices"] = [{"row_number": 2, "action": "create"}, {"row_number": 3, "action": "create"}]
    shown = preview(pg, body)
    assert shown["ready"] is True
    saved = confirm(pg, body, shown)
    assert saved.status_code == 200 and counts(pg)["materials"] == 2


def test_candidates_query_handles_missing_specification_in_real_postgres(pg):
    created = pg.api.command("/api/v1/materials", {"name": "Synthetic bare name"}).json()
    result = pg.runtime.materials.preview_import(
        pg.actor, mapped("name\nSynthetic bare name\n", columns={"name": 1})
    )
    assert result["rows"][0]["candidates"][0]["id"] == created["id"]
    assert result["ready"] is False


def test_customer_mapping_uses_source_name_and_never_updates_existing_signature(pg):
    body = mapped(
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200, saved.text
    mapping = pg.api.request("GET", "/api/v1/material-codes").json()["items"][0]
    assert mapping["item_name"] == "Synthetic bracket"
    assert mapping["canonical_unit"] == "PCS"
    changed = mapped(
        "own,name,spec,unit,customer\n000123,Synthetic changed,S-1,PCS,A-017\n",
        customer_id=pg.customer_id,
        columns=body["columns"],
    )
    row = preview(pg, changed)["rows"][0]
    changed["choices"] = [
        {
            "row_number": 2,
            "action": "reuse",
            "material_id": saved.json()["rows"][0]["material"]["id"],
            "expected_material_version": 1,
        }
    ]
    result = preview(pg, changed)
    assert "CUSTOMER_CODE_CONFLICT" in result["rows"][0]["issues"]
    assert confirm(pg, changed, result).status_code == 422
    assert pg.api.request("GET", "/api/v1/material-codes").json()["items"][0] == mapping
    assert row["action"] == "pending"


def test_old_preview_detects_previously_absent_code_and_selected_target_changes(pg):
    body = mapped("own,name\nNEW,Synthetic\n", columns={"own_code": 1, "name": 2})
    old = preview(pg, body)
    material = pg.api.command("/api/v1/materials", {"own_code": "NEW", "name": "Synthetic"}).json()
    conflict = confirm(pg, body, old)
    assert conflict.status_code == 409 and conflict.json()["code"] == "MATERIAL_IMPORT_STALE"
    current = preview(pg, body)
    pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            "own_code": "NEW",
            "name": "Synthetic renamed",
            "expected_version": 1,
            "active": False,
            "reason": "Synthetic concurrent update",
        },
    )
    assert confirm(pg, body, current).status_code == 409
    assert counts(pg)["materials"] == 1


def test_committed_key_replays_before_current_material_and_mapping_revalidation(pg):
    body = mapped(
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    result = preview(pg, body)
    key = uuid4()
    saved = confirm(pg, body, result, key)
    assert saved.status_code == 200, saved.text
    material = saved.json()["rows"][0]["material"]
    pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            **{field: material[field] for field in ("own_code", "name", "specification", "unit")},
            "name": "Synthetic renamed",
            "expected_version": 1,
            "active": False,
            "reason": "Synthetic later change",
        },
    )
    with pg.owner.begin() as conn:
        conn.execute(
            text(
                "UPDATE customer_material_codes "
                "SET item_name='Synthetic corrected',version=version+1"
            )
        )
    assert confirm(pg, body, result, key).json() == saved.json()
    assert confirm(pg, body, result).status_code == 409


def test_numeric_codes_need_separate_confirmations_and_unsafe_numbers_cannot_bypass(pg):
    raw = workbook_bytes([["own", "name", "customer"], [123, "Synthetic", 456]])
    body = mapped(
        columns={"own_code": 1, "name": 2, "customer_code": 3}, customer_id=pg.customer_id
    )
    body.update(filename="synthetic.xlsx", content_base64=base64.b64encode(raw).decode())
    assert preview(pg, body)["ready"] is False
    body["choices"] = [
        {"row_number": 2, "action": "create", "confirmed_numeric_fields": ["own_code"]}
    ]
    result = preview(pg, body)
    assert "NUMERIC_CUSTOMER_CODE_CONFIRM" in result["rows"][0]["issues"]
    body["choices"][0]["confirmed_numeric_fields"].append("customer_code")
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200 and saved.json()["rows"][0]["material"]["own_code"] == "123"
    unsafe = workbook_bytes([["own", "name", "customer"], [1234567890123456, "Synthetic", True]])
    body["content_base64"] = base64.b64encode(unsafe).decode()
    result = preview(pg, body)
    assert "UNSAFE_OWN_CODE" in result["rows"][0]["issues"]
    assert "UNSAFE_CUSTOMER_CODE" in result["rows"][0]["issues"]
    assert confirm(pg, body, result).status_code == 422


def test_confirming_numeric_text_does_not_implicitly_choose_an_incompatible_target(pg):
    pg.api.command("/api/v1/materials", {"own_code": "123", "name": "Synthetic original"})
    raw = workbook_bytes([["own", "name"], [123, "Synthetic changed"]])
    body = mapped(
        columns={"own_code": 1, "name": 2},
        choices=[{"row_number": 2, "action": "default", "confirmed_numeric_fields": ["own_code"]}],
    )
    body.update(filename="synthetic.xlsx", content_base64=base64.b64encode(raw).decode())
    result = preview(pg, body)
    assert "EXISTING_CODE_DIFFERS" in result["rows"][0]["issues"]
    assert result["ready"] is False


def test_invalid_row_values_are_visible_and_can_be_explicitly_skipped(pg):
    body = mapped(
        "own,name,spec,unit\nBAD,Synthetic," + "x" * 1001 + ",PCS\nOK,Synthetic valid,S-1,PCS\n"
    )
    result = preview(pg, body)
    assert "INVALID_SPECIFICATION" in result["rows"][0]["issues"]
    body["choices"] = [{"row_number": 2, "action": "skip"}]
    saved = confirm(pg, body, preview(pg, body))
    assert saved.status_code == 200 and counts(pg)["materials"] == 1


def test_file_mapping_and_new_customer_code_invalidate_old_previews(pg):
    body = mapped(
        "own,name,spec,unit,customer\nNEW,Synthetic,S-1,PCS,A-017\n",
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    result = preview(pg, body)
    changed_file = body | {
        "content_base64": csv_body("own,name,spec,unit,customer\nOTHER,Synthetic,S-1,PCS,A-017\n")[
            "content_base64"
        ]
    }
    assert confirm(pg, changed_file, result).status_code == 409
    assert (
        confirm(
            pg, body | {"columns": body["columns"] | {"customer_code": None}}, result
        ).status_code
        == 409
    )
    material = pg.api.command("/api/v1/materials", {"name": "Synthetic other"}).json()
    mapped_code = pg.api.command(
        "/api/v1/material-codes",
        {
            "customer_id": pg.customer_id,
            "customer_code": "A-017",
            "material_id": material["id"],
            "expected_material_version": 1,
        },
    )
    assert mapped_code.status_code == 200
    assert confirm(pg, body, result).status_code == 409
    assert counts(pg)["materials"] == 1


@pytest.mark.parametrize(
    "choices",
    [
        [{"row_number": 999, "action": "skip"}],
        [{"row_number": 2, "action": "skip"}, {"row_number": 2, "action": "skip"}],
        [
            {
                "row_number": 2,
                "action": "create",
                "material_id": str(uuid4()),
                "expected_material_version": 1,
            }
        ],
    ],
)
def test_unknown_duplicate_and_ambiguous_row_choices_are_rejected(pg, choices):
    response = pg.api.command("/api/v1/materials/imports/preview", mapped(choices=choices))
    assert response.status_code == 422
    assert counts(pg)["materials"] == 0


def test_mapped_customer_code_requires_explicit_owned_customer_and_viewer_cannot_import(pg):
    body = mapped(
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5}
    )
    assert preview(pg, body)["ready"] is False
    with pytest.raises(BusinessError):
        pg.runtime.materials.preview_import(pg.actor, body | {"customer_id": str(uuid4())})
    viewer = pg.runtime.identity.add_user(pg.actor, "m2-viewer", SYNTHETIC_PASSWORD, "viewer")
    for operation in (pg.runtime.materials.inspect_import, pg.runtime.materials.preview_import):
        with pytest.raises(BusinessError, match="WRITE_FORBIDDEN"):
            operation(viewer, body)
    foreign = replace(pg.actor, organization_id=uuid4())
    with pytest.raises(BusinessError):
        pg.runtime.materials.preview_import(foreign, body | {"customer_id": pg.customer_id})
    assert counts(pg)["materials"] == 0


@pytest.mark.parametrize(
    "table", ["materials", "customer_material_codes", "audit_events", "command_results"]
)
def test_every_import_write_failure_rolls_back_the_entire_batch(pg, table):
    body = mapped(
        customer_id=pg.customer_id,
        columns={"own_code": 1, "name": 2, "specification": 3, "unit": 4, "customer_code": 5},
    )
    result = preview(pg, body)
    before = counts(pg)
    calls = 0

    def fail(conn, cursor, statement, parameters, context, executemany):
        nonlocal calls
        if statement.lower().lstrip().startswith("insert into " + table):
            calls += 1
            if calls == (2 if table == "materials" else 1):
                raise RuntimeError("Synthetic M2 write failure")

    engine = pg.app.state.services.engine
    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError, match="Synthetic M2 write failure"):
            confirm(pg, body, result)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert counts(pg) == before


def test_two_operators_cannot_both_import_the_same_new_code(pg):
    body = mapped("own,name\nRACE,Synthetic\n", columns={"own_code": 1, "name": 2})
    result = preview(pg, body)
    operator = pg.runtime.identity.add_user(pg.actor, "m2-operator", SYNTHETIC_PASSWORD, "operator")
    payload = body | {"preview_fingerprint": result["preview_fingerprint"]}

    def write(actor):
        try:
            return pg.runtime.materials.confirm_import(actor, uuid4(), payload)["actor_id"]
        except BusinessError as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, [pg.actor, operator]))
    assert results.count("MATERIAL_IMPORT_STALE") == 1
    assert counts(pg)["materials"] == 1
