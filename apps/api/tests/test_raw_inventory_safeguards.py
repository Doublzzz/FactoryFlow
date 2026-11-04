"""PR01/08–14: runtime SQL and failed commands cannot bypass raw-stock ownership."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_inventory import opening
from test_postgres_materials import create_material
from test_purchasing import fixture, ok, purchasing_effects, receipt
from test_raw_inventory import movement, raw


def append(conn, pg, material, kind, delta, **extra):
    values = {
        "organization_id": pg.actor.organization_id,
        "id": uuid4(),
        "material_id": material["id"],
        "kind": kind,
        "delta": delta,
        "business_date": "2026-10-26",
        "actor_id": pg.actor.user_id,
        "reason": "Synthetic SQL safeguard",
        **extra,
    }
    columns = ",".join(values)
    parameters = ",".join(":" + name for name in values)
    conn.execute(
        text(f"INSERT INTO public.inventory_ledger ({columns}) VALUES ({parameters})"), values
    )


@pytest.mark.parametrize(
    "kind,delta",
    [("receipt", 1), ("material_issue", 1), ("material_issue", -11), ("material_return", 1)],
)
def test_runtime_raw_rejects_wrong_kind_sign_or_missing_source(pg, kind, delta):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    before = purchasing_effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        append(conn, pg, material, kind, delta)
    assert purchasing_effects(pg) == before


def test_runtime_finished_cannot_forge_raw_issue(pg):
    material = create_material(pg, unit="KG")
    opening(pg, material, "10")
    before = purchasing_effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        append(conn, pg, material, "material_issue", -1)
    assert purchasing_effects(pg) == before


@pytest.mark.parametrize("source", ["over", "other_material", "other_org", "not_issue"])
def test_runtime_return_requires_same_owner_material_issue_and_remaining_allowance(pg, source):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    issue = ok(movement(pg, material, "issues", "6"))["entry"]
    ok(
        pg.api.command(
            f"/api/v1/raw-inventory/entries/{issue['id']}/returns",
            {"quantity": "4", "business_date": "2026-10-26", "reason": "Synthetic return"},
        )
    )
    extra = {"returns_issue_id": issue["id"]}
    target = material
    if source == "other_material":
        target = raw(pg, own_code="SYN-OTHER-RAW")
        ok(movement(pg, target, "open", "0"))
    elif source == "other_org":
        extra["organization_id"] = uuid4()
    elif source == "not_issue":
        with pg.owner.connect() as conn:
            extra["returns_issue_id"] = conn.scalar(
                text("SELECT id FROM inventory_ledger WHERE kind='opening'")
            )
    before = purchasing_effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        append(conn, pg, target, "material_return", 3, **extra)
    assert purchasing_effects(pg) == before


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE inventory_accounts SET balance=99",
        "UPDATE inventory_accounts SET version=version+1",
        "DELETE FROM inventory_ledger",
        "UPDATE inventory_ledger SET reason='Synthetic changed'",
    ],
)
def test_runtime_cannot_tamper_with_raw_projection_or_evidence(pg, statement):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    before = purchasing_effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(text(statement))
    assert purchasing_effects(pg) == before


def test_runtime_temp_material_and_ledger_cannot_hide_raw_kind_or_over_return(pg):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    issue = ok(movement(pg, material, "issues", "6"))["entry"]
    before = purchasing_effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE materials AS SELECT * FROM public.materials"))
        conn.execute(text("UPDATE pg_temp.materials SET kind='finished'"))
        append(conn, pg, material, "receipt", 1)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("CREATE TEMP TABLE inventory_ledger AS SELECT * FROM public.inventory_ledger")
        )
        conn.execute(
            text("UPDATE pg_temp.inventory_ledger SET delta=-100 WHERE kind='material_issue'")
        )
        append(conn, pg, material, "material_return", 7, returns_issue_id=issue["id"])
    assert purchasing_effects(pg) == before


@pytest.mark.parametrize("target", ["supplier", "material"])
def test_purchasing_privileged_guards_ignore_temp_supplier_and_material_forgery(pg, target):
    supplier, materials, _ = fixture(pg)
    material = materials[0]
    if target == "supplier":
        ok(
            pg.api.command(
                f"/api/v1/suppliers/{supplier['id']}",
                {"full_name": supplier["full_name"], "active": False, "expected_version": 1},
            )
        )
    else:
        material = create_material(pg, unit="KG")
    before = purchasing_effects(pg)
    params = {
        "org": pg.actor.organization_id,
        "actor": pg.actor.user_id,
        "supplier": supplier["id"],
        "name": supplier["full_name"],
        "order": uuid4(),
        "number": "SYN-TEMP-" + uuid4().hex,
        "material": material["id"],
        "line": uuid4(),
    }
    with pg.runtime.engine.connect() as conn:
        try:
            conn.execute(text("CREATE TEMP TABLE suppliers AS SELECT * FROM public.suppliers"))
            conn.execute(text("UPDATE pg_temp.suppliers SET active=true"))
            conn.execute(text("CREATE TEMP TABLE materials AS SELECT * FROM public.materials"))
            conn.execute(text("UPDATE pg_temp.materials SET kind='raw'"))
            header = text("""INSERT INTO public.purchase_orders
                (organization_id,id,supplier_id,number,business_date,supplier_name,created_by)
                VALUES (:org,:order,:supplier,:number,'2026-10-26',:name,:actor)""")
            if target == "supplier":
                # Require failure in this immediate guard, not a deferred missing-audit check.
                with pytest.raises(DBAPIError):
                    conn.execute(header, params)
            else:
                conn.execute(header, params)
                with pytest.raises(DBAPIError):
                    conn.execute(
                        text("""INSERT INTO public.purchase_order_lines
                        (organization_id,id,order_id,line_number,material_id,own_code,
                         material_name,specification,canonical_unit,ordered_quantity)
                        SELECT organization_id,:line,:order,1,id,own_code,name,specification,'KG',1
                        FROM public.materials WHERE id=:material"""),
                        params,
                    )
        finally:
            conn.rollback()
    assert purchasing_effects(pg) == before


def test_purchase_receipt_cannot_be_reversed_through_generic_route_or_forged_sql(pg):
    supplier, materials, order = fixture(pg)
    received = ok(receipt(pg, supplier, order, ["4"]))
    with pg.owner.connect() as conn:
        entry = (
            conn.execute(
                text(
                    "SELECT id,purchase_receipt_line_id FROM inventory_ledger "
                    "WHERE kind='purchase_receipt'"
                )
            )
            .mappings()
            .one()
        )
    before = purchasing_effects(pg)
    response = pg.api.command(
        f"/api/v1/inventory/entries/{entry['id']}/void", {"reason": "Synthetic bypass"}
    )
    assert response.status_code == 409
    for kind in ["receipt_void", "purchase_receipt_void"]:
        with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
            extra = {"reverses_id": entry["id"]}
            if kind == "purchase_receipt_void":
                extra["purchase_receipt_line_id"] = entry["purchase_receipt_line_id"]
            append(conn, pg, materials[0], kind, -4, **extra)
    # A fake void header in pg_temp cannot authorize a reversal of the active real receipt.
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("CREATE TEMP TABLE purchase_receipts AS SELECT * FROM public.purchase_receipts")
        )
        conn.execute(text("UPDATE pg_temp.purchase_receipts SET status='void'"))
        append(
            conn,
            pg,
            materials[0],
            "purchase_receipt_void",
            -4,
            reverses_id=entry["id"],
            purchase_receipt_line_id=entry["purchase_receipt_line_id"],
        )
    assert purchasing_effects(pg) == before
    assert (
        ok(pg.api.request("GET", f"/api/v1/purchase-receipts/{received['id']}"))["status"]
        == "active"
    )


@pytest.mark.parametrize("table", ["inventory_ledger", "audit_events", "command_results"])
@pytest.mark.parametrize("action", ["issue", "return"])
def test_issue_return_participant_failure_rolls_back_and_original_key_can_retry(pg, table, action):
    material = raw(pg)
    ok(movement(pg, material, "open", "10"))
    issue = ok(movement(pg, material, "issues", "6"))["entry"]
    path = (
        f"/api/v1/raw-inventory/{material['id']}/issues"
        if action == "issue"
        else f"/api/v1/raw-inventory/entries/{issue['id']}/returns"
    )
    payload = {"quantity": "2", "business_date": "2026-10-26", "reason": "Synthetic failure retry"}
    key = uuid4()
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_raw_participant() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic raw failure'; END; $$;
        CREATE TRIGGER fail_raw_participant BEFORE INSERT ON {table}
        FOR EACH ROW EXECUTE FUNCTION fail_raw_participant();""")
        )
    before = purchasing_effects(pg)
    assert pg.api.command(path, payload, key).status_code == 503
    assert purchasing_effects(pg) == before
    with pg.owner.begin() as conn:
        conn.execute(text(f"DROP TRIGGER fail_raw_participant ON {table}"))
    result = ok(pg.api.command(path, payload, key))
    assert ok(pg.api.command(path, payload, key)) == result
