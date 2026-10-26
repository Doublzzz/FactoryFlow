"""Database, transaction, ownership and concurrent acceptance for FG07–FG12."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier, Event, local
from uuid import uuid4

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.materials.public import MaterialCatalog
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_inventory import (
    inventory_rows,
    make_order,
    ok,
    opening,
    receipt,
    send,
    shipment,
    stock,
    void_delivery,
)
from test_postgres_material_order_links import link
from test_postgres_materials import create_material
from test_postgres_statement_lifecycle import approve, reserve, settle


def effects(pg):
    with pg.owner.connect() as conn:
        return {
            table: tuple(
                conn.execute(
                    text(
                        f"SELECT row_to_json(t)::text FROM {table} t ORDER BY row_to_json(t)::text"
                    )
                ).scalars()
            )
            for table in (
                "orders",
                "order_lines",
                "deliveries",
                "delivery_lines",
                "fulfillment_actions",
                "inventory_accounts",
                "inventory_ledger",
                "delivery_inventory_snapshots",
                "audit_events",
                "command_results",
                "order_events",
            )
        }


def test_iv22_runtime_temp_table_cannot_replace_material_in_privileged_trigger(pg):
    material = create_material(pg, unit="PCS")
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE materials AS SELECT * FROM public.materials"))
        conn.execute(text("UPDATE materials SET unit='KG'"))
        conn.execute(
            text("""INSERT INTO public.inventory_accounts
            (organization_id,material_id,canonical_unit,created_by)
            VALUES(:org,:material,'KG',:actor)"""),
            {
                "org": pg.actor.organization_id,
                "material": material["id"],
                "actor": pg.actor.user_id,
            },
        )
        conn.execute(
            text("""INSERT INTO public.inventory_ledger
            (organization_id,id,material_id,kind,delta,target_quantity,business_date,actor_id)
            VALUES(:org,:id,:material,'opening',1,1,'2026-10-24',:actor)"""),
            {
                "org": pg.actor.organization_id,
                "id": uuid4(),
                "material": material["id"],
                "actor": pg.actor.user_id,
            },
        )
    assert inventory_rows(pg) == (0, 0)


def test_iv02_iv12_late_link_and_rebind_never_rewrite_delivery_inventory(pg):
    first, second = create_material(pg), create_material(pg)
    opening(pg, first)
    opening(pg, second)
    unlinked = make_order(pg, [None])
    old = send(pg, unlinked)
    current = ok(pg.api.request("GET", f"/api/v1/orders/{unlinked['id']}"))
    ok(link(pg, current, first))
    assert ok(pg.api.request("GET", f"/api/v1/deliveries/{old['id']}")) == old
    assert stock(pg, first)["account"]["balance"] == "100"
    tracked = send(pg, unlinked, ["20"])
    current = ok(pg.api.request("GET", f"/api/v1/orders/{unlinked['id']}"))
    ok(link(pg, current, second, reason="Synthetic corrected identity"))
    void_delivery(pg, tracked)
    void_delivery(pg, old)
    assert stock(pg, first)["account"]["balance"] == "100"
    assert stock(pg, second)["account"]["balance"] == "100"
    assert (
        stock(pg, first)["entries"][0]["reverses_id"]
        == tracked["lines"][0]["inventory"]["movement_id"]
    )


def test_iv11_confirming_shortage_never_permits_overdelivery(pg):
    material = create_material(pg)
    opening(pg, material, "0")
    order = make_order(pg, [material], quantity="10")
    before = effects(pg)
    rejected = pg.api.command(
        "/api/v1/deliveries",
        shipment(
            pg,
            order,
            ["11"],
            confirm_inventory_shortage=True,
        ),
    )
    assert rejected.json()["code"] == "DELIVERY_EXCEEDS_REMAINING"
    assert effects(pg) == before


@pytest.mark.parametrize("command", ["create", "void"])
@pytest.mark.parametrize(
    "table", ["inventory_ledger", "order_lines", "audit_events", "command_results"]
)
def test_iv18_all_participant_failures_roll_back_every_business_effect(pg, command, table):
    material = create_material(pg)
    opening(pg, material)
    order = make_order(pg, [material])
    path, body = "/api/v1/deliveries", shipment(pg, order)
    if command == "void":
        created = ok(pg.api.command(path, body))
        path += f"/{created['id']}/void"
        body = {"expected_version": 1, "reason": "Synthetic rollback"}
    before = effects(pg)
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_inventory_command() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END; $$;
            CREATE TRIGGER fail_inventory_command
            BEFORE {"UPDATE" if table == "order_lines" else "INSERT"}
            ON {table} FOR EACH ROW EXECUTE FUNCTION fail_inventory_command();""")
        )
    assert pg.api.command(path, body).status_code == 503
    assert effects(pg) == before


@pytest.mark.parametrize("first", ["opening", "delivery"])
def test_iv20_catalog_lock_fixes_opening_delivery_order(pg, monkeypatch, first):
    material = create_material(pg)
    order = make_order(pg, [material])
    body = shipment(pg, order)
    entered, second_started, release = Event(), Event(), Event()
    thread = local()
    actual_lock = MaterialCatalog.lock

    def lock(catalog, actor):
        if not getattr(thread, "first", False):
            second_started.set()
        actual_lock(catalog, actor)
        if getattr(thread, "first", False):
            entered.set()
            assert release.wait(5)

    monkeypatch.setattr(MaterialCatalog, "lock", lock)

    def execute(kind, is_first):
        thread.first = is_first
        if kind == "opening":
            return pg.runtime.inventory.record(
                pg.actor,
                uuid4(),
                material["id"],
                "opening",
                {
                    "quantity": "100",
                    "business_date": "2026-10-24",
                },
            )
        return pg.runtime.deliveries.create(pg.actor, uuid4(), body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        earlier = pool.submit(execute, first, True)
        try:
            assert entered.wait(5)
            later = pool.submit(execute, "delivery" if first == "opening" else "opening", False)
            assert second_started.wait(5)
            assert not later.done()
        finally:
            release.set()
        results = [earlier.result(timeout=10), later.result(timeout=10)]
    delivery = next(result for result in results if "lines" in result)
    assert delivery["lines"][0]["inventory"]["state"] == (
        "tracked" if first == "opening" else "unmanaged"
    )
    assert stock(pg, material)["account"]["balance"] == ("70" if first == "opening" else "100")


def test_iv21_two_orders_recheck_one_account_after_serialization(pg):
    material = create_material(pg)
    opening(pg, material, "10")
    requests = [shipment(pg, make_order(pg, [material]), ["6"]) for _ in range(2)]
    barrier = Barrier(2)

    def execute(body):
        barrier.wait()
        try:
            return pg.runtime.deliveries.create(pg.actor, uuid4(), body)["status"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(execute, requests))
    assert sorted(results) == ["INVENTORY_SHORTAGE", "active"]
    assert stock(pg, material)["account"]["balance"] == "4"


def test_iv22_concurrent_direct_receipt_reversals_are_enforced_by_postgresql(pg):
    material = create_material(pg)
    opening(pg, material, "0")
    entries = [receipt(pg, material, "8")["entry"] for _ in range(2)]
    send(pg, make_order(pg, [material]), ["6"])
    barrier = Barrier(2)

    def reverse(original):
        barrier.wait()
        try:
            with pg.runtime.engine.begin() as conn:
                conn.execute(
                    text("""INSERT INTO inventory_ledger
                    (organization_id,id,material_id,kind,delta,business_date,reason,actor_id,reverses_id)
                    VALUES(:org,:id,:material,'receipt_void',-8,'2026-10-24','Synthetic',:actor,:original)
                """),
                    {
                        "org": pg.actor.organization_id,
                        "id": uuid4(),
                        "material": material["id"],
                        "actor": pg.actor.user_id,
                        "original": original["id"],
                    },
                )
            return "reversed"
        except DBAPIError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reverse, entries)) == ["rejected", "reversed"]
    assert stock(pg, material)["account"]["balance"] == "2"


def test_iv22_direct_mutation_invalid_opening_and_repeated_reversal_are_rejected(pg):
    material, unopened = create_material(pg), create_material(pg)
    opening(pg, material, "0")
    original = receipt(pg, material)["entry"]
    params = {
        "org": pg.actor.organization_id,
        "material": material["id"],
        "actor": pg.actor.user_id,
        "id": original["id"],
    }
    statements = [
        "UPDATE inventory_accounts SET balance=999 WHERE material_id=:material",
        "UPDATE inventory_accounts SET material_id=material_id WHERE material_id=:material",
        "UPDATE inventory_ledger SET delta=999 WHERE id=:id",
        "DELETE FROM inventory_ledger WHERE id=:id",
        "DELETE FROM inventory_accounts WHERE material_id=:material",
        """INSERT INTO inventory_ledger
        (organization_id,id,material_id,kind,delta,business_date,actor_id)
        VALUES(:org,gen_random_uuid(),:material,'receipt',-1,'2026-10-24',:actor)""",
    ]
    before = effects(pg)
    for statement in statements:
        with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
            conn.execute(text(statement), params)
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(text("UPDATE inventory_ledger SET delta=999 WHERE id=:id"), params)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO inventory_accounts
            (organization_id,material_id,canonical_unit,created_by)
            VALUES(:org,:material,'PCS',:actor)"""),
            params | {"material": unopened["id"]},
        )
    assert effects(pg) == before
    ok(pg.api.command(f"/api/v1/inventory/entries/{original['id']}/void", {"reason": "Synthetic"}))
    receipt(
        pg, material, "20"
    )  # A second reversal would be nonnegative; uniqueness must still reject.
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO inventory_ledger
            (organization_id,id,material_id,kind,delta,business_date,reason,actor_id,reverses_id)
            VALUES(:org,gen_random_uuid(),:material,'receipt_void',-10,'2026-10-24','Synthetic',:actor,:id)
        """),
            params,
        )
    assert effects(pg) == before


def test_iv22_decisions_are_immutable_and_cross_organization_writes_fail(pg):
    material = create_material(pg)
    opening(pg, material)
    send(pg, make_order(pg, [material]))
    before = effects(pg)
    for statement in (
        "UPDATE delivery_inventory_snapshots SET state=state",
        "DELETE FROM delivery_inventory_snapshots",
    ):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(statement))
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("""INSERT INTO inventory_ledger
            (organization_id,id,material_id,kind,delta,business_date,actor_id)
            VALUES(:org,:id,:material,'receipt',1,'2026-10-24',:actor)"""),
            {
                "org": uuid4(),
                "id": uuid4(),
                "material": material["id"],
                "actor": pg.actor.user_id,
            },
        )
    assert effects(pg) == before


@pytest.mark.parametrize("managed", [False, True])
def test_iv01_iv19_approval_and_formal_settlement_do_not_change_inventory(pg, managed):
    material = create_material(pg)
    if managed:
        opening(pg, material)
    order = make_order(pg, [material])
    delivery = send(pg, order, ["30"])
    source = {"delivery_id": delivery["id"], "order_line_id": delivery["lines"][0]["order_line_id"]}
    before = inventory_rows(pg)
    statement = ok(
        pg.api.command(
            "/api/v1/statements",
            {
                "customer_id": pg.customer_id,
                "period_start": "2026-10-01",
                "period_end": "2026-10-31",
                "tax_mode": "untaxed_final",
                "tax_rate": "0",
                "adjustments": [],
                "lines": [{**source, "quantity": "30", "unit_price": "10", "reason": "Synthetic"}],
            },
        )
    )
    export = ok(
        pg.api.command(f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1})
    )
    ok(pg.api.request("POST", f"/api/v1/statement-exports/{export['id']}/generate"))
    sent = ok(
        pg.api.command(
            f"/api/v1/statements/{statement['id']}/sent",
            {
                "expected_version": 1,
                "export_id": export["id"],
                "person": "Synthetic Sender",
                "occurred_on": "2026-10-24",
                "note": "Synthetic actual send",
            },
        )
    )
    feedback = ok(
        pg.api.command(
            f"/api/v1/statements/{statement['id']}/feedback",
            {
                "person": "Synthetic Recipient",
                "occurred_on": "2026-10-24",
                "note": "Synthetic confirmation",
            },
        )
    )
    approval = approve(pg, statement, source, sent, feedback, "30")
    for formal in (False, True):
        if formal:
            reserve(pg, statement, approval, "30")
            assert settle(pg, statement)["status"] == "confirmed"
        frozen = effects(pg)
        response = pg.api.command(
            f"/api/v1/deliveries/{delivery['id']}/void",
            {
                "expected_version": 1,
                "reason": "Synthetic protected source",
            },
        )
        assert response.json()["code"] == "STATEMENT_APPROVED_SOURCE_PROTECTED"
        assert effects(pg) == frozen
        assert inventory_rows(pg) == before
    current = ok(pg.api.request("GET", f"/api/v1/orders/{order['id']}"))
    assert current["lines"][0]["remaining_quantity"] == "70"
    assert (
        stock(pg, material)["account"]["balance"] == "70"
        if managed
        else inventory_rows(pg) == (0, 0)
    )


@pytest.mark.parametrize("table", ["audit_events", "command_results"])
def test_iv18_inventory_commands_rollback_when_journal_cannot_commit(pg, table):
    material, unopened = create_material(pg), create_material(pg)
    opening(pg, material)
    received = receipt(pg, material)
    body = {"quantity": "10", "business_date": "2026-10-24", "reason": "Synthetic"}
    commands = [
        (f"/api/v1/inventory/{unopened['id']}/open", body),
        (f"/api/v1/inventory/{material['id']}/receipts", body),
        (f"/api/v1/inventory/{material['id']}/counts", body | {"expected_version": 2}),
        (f"/api/v1/inventory/entries/{received['entry']['id']}/void", {"reason": "Synthetic"}),
    ]
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_inventory_journal() RETURNS trigger
            LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic failure'; END; $$;
            CREATE TRIGGER fail_inventory_journal BEFORE INSERT ON {table}
            FOR EACH ROW EXECUTE FUNCTION fail_inventory_journal();""")
        )
    before = effects(pg)
    for path, request in commands:
        assert pg.api.command(path, request).status_code == 503
        assert effects(pg) == before


def test_iv23_exact_quantities_unknown_unit_and_business_order(pg):
    material = create_material(pg, unit="KG")
    opening(pg, material, "0.125")
    receipt(pg, material, "1.125")
    detail = stock(pg, material)
    assert detail["account"]["balance"] == "1.25"
    assert [row["kind"] for row in detail["entries"]] == ["receipt", "opening"]
    assert detail["entries"][0]["business_date"] < detail["entries"][1]["business_date"]
    before = effects(pg)
    for value in ("-1", "0", "0.0001", "9223372036854775.808", "NaN", "1e0", 1.25):
        response = pg.api.command(
            f"/api/v1/inventory/{material['id']}/receipts",
            {
                "quantity": value,
                "business_date": "2026-10-24",
            },
        )
        assert response.status_code == 422, response.text
    assert effects(pg) == before
    for unit, quantity, code in (
        ("PCS", "0.125", "UNIT_REQUIRES_INTEGER_QUANTITY"),
        (None, "1", "INVENTORY_UNIT_REQUIRED"),
        ("unknown", "1", "INVENTORY_UNIT_REQUIRED"),
    ):
        item = create_material(pg, unit=unit)
        result = pg.api.command(
            f"/api/v1/inventory/{item['id']}/open",
            {
                "quantity": quantity,
                "business_date": "2026-10-24",
            },
        )
        assert result.json()["code"] == code
        assert stock(pg, item)["account"] is None


def test_iv22_iv25_other_organization_and_viewer_never_gain_write_access(pg):
    material = create_material(pg)
    opening(pg, material)
    stranger = replace(pg.actor, organization_id=uuid4())
    with pytest.raises(BusinessError) as missing:
        pg.runtime.inventory.detail(stranger, material["id"])
    assert missing.value.status == 404
    with pytest.raises(BusinessError):
        pg.runtime.inventory.record(
            stranger,
            uuid4(),
            material["id"],
            "receipt",
            {
                "quantity": "1",
                "business_date": "2026-10-24",
            },
        )
    pg.runtime.identity.add_user(pg.actor, "synthetic-viewer", SYNTHETIC_PASSWORD, "viewer")
    api = API(pg.app)
    api.login("synthetic-viewer")
    assert api.request("GET", f"/api/v1/inventory/{material['id']}").status_code == 200
    assert (
        api.command("/api/v1/inventory/preview", {"material_ids": [material["id"]]}).status_code
        == 200
    )
    before = effects(pg)
    for operation, extra in (("open", {}), ("receipts", {}), ("counts", {"expected_version": 1})):
        assert (
            api.command(
                f"/api/v1/inventory/{material['id']}/{operation}",
                {
                    "quantity": "1",
                    "business_date": "2026-10-24",
                    "reason": "Synthetic",
                    **extra,
                },
            ).status_code
            == 403
        )
    assert effects(pg) == before
