"""PD10: real PostgreSQL concurrency, rollback and independent runtime SQL guards."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_inventory import stock
from test_postgres_material_order_links import body as order_body
from test_postgres_material_order_links import link
from test_postgres_materials import create_material
from test_production import BASE, DAY, detail, finish, fixture, issue, ok, void
from test_raw_inventory_safeguards import append


def effects(pg):
    with pg.owner.connect() as conn:
        return {
            table: tuple(
                conn.execute(
                    text(f"SELECT row_to_json(t)::text FROM {table} t ORDER BY 1")
                ).scalars()
            )
            for table in (
                "orders",
                "order_lines",
                "production_orders",
                "production_completions",
                "inventory_accounts",
                "inventory_ledger",
                "audit_events",
                "command_results",
            )
        }


def insert_completion(conn, pg, production, quantity="1", scrap="0", **extra):
    values = {
        "organization_id": pg.actor.organization_id,
        "id": uuid4(),
        "production_order_id": production["id"],
        "material_id": production["material_id"],
        "quantity": quantity,
        "scrap_quantity": scrap,
        "business_date": DAY,
        "created_by": pg.actor.user_id,
        **extra,
    }
    conn.execute(
        text(
            f"INSERT INTO public.production_completions ({','.join(values)}) "
            f"VALUES ({','.join(':' + k for k in values)})"
        ),
        values,
    )
    return values["id"]


@pytest.mark.parametrize(
    "table", ["production_completions", "inventory_ledger", "audit_events", "command_results"]
)
@pytest.mark.parametrize("action", ["complete", "void"])
def test_pd_participant_failure_rolls_back_all_facts_and_same_key_retries(pg, table, action):
    _, _, _, production, _ = fixture(pg)
    completed = ok(finish(pg, production))
    key = uuid4()

    def operation():
        return (
            void(pg, production, completed, key)
            if action == "void"
            else finish(pg, production, "2", "1", key)
        )

    before = effects(pg)
    mutation = "UPDATE" if table == "production_completions" and action == "void" else "INSERT"
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_production() RETURNS trigger LANGUAGE plpgsql AS
         $$ BEGIN RAISE EXCEPTION 'synthetic production failure'; END; $$;
         CREATE TRIGGER fail_production BEFORE {mutation} ON {table}
         FOR EACH ROW EXECUTE FUNCTION fail_production();""")
        )
    assert operation().status_code == 503
    assert effects(pg) == before
    with pg.owner.begin() as conn:
        conn.execute(text(f"DROP TRIGGER fail_production ON {table}"))
    result = ok(operation())
    assert ok(operation()) == result


def test_pd_runtime_missing_stock_and_missing_reverse_fail_at_commit(pg):
    finished, _, _, production, _ = fixture(pg)
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        insert_completion(conn, pg, production)
    assert effects(pg) == before
    completed = ok(finish(pg, production))
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("""UPDATE production_completions SET status='void',version=2,
            void_at=clock_timestamp(),void_by=:actor,void_reason='Synthetic missing reverse'
            WHERE id=:id"""),
            {"actor": pg.actor.user_id, "id": completed["id"]},
        )
    assert effects(pg) == before
    # A ledger-only reverse cannot leave the completion active.
    with pg.owner.connect() as conn:
        entry = conn.scalar(text("SELECT id FROM inventory_ledger WHERE kind='production_receipt'"))
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        append(
            conn,
            pg,
            finished,
            "production_receipt_void",
            "-40",
            reverses_id=entry,
            production_order_id=production["id"],
            production_completion_id=completed["id"],
        )
    assert effects(pg) == before


def test_pd_runtime_insufficient_stock_reversal_rolls_back_completion_and_ledger(pg):
    finished, _, _, production, _ = fixture(pg)
    completed = ok(finish(pg, production))
    inventory = stock(pg, finished)
    entry = next(x for x in inventory["entries"] if x["kind"] == "production_receipt")
    ok(
        pg.api.command(
            f"/api/v1/inventory/{finished['id']}/counts",
            {
                "quantity": "2",
                "expected_version": inventory["account"]["version"],
                "business_date": DAY,
                "reason": "Synthetic stock no longer available",
            },
        )
    )
    before = effects(pg)
    with (
        pytest.raises(DBAPIError, match="invalid production stock reversal"),
        pg.runtime.engine.begin() as conn,
    ):
        conn.execute(
            text("""UPDATE production_completions SET status='void',version=2,
            void_at=clock_timestamp(),void_by=:actor,void_reason='Synthetic direct reversal'
            WHERE id=:id"""),
            {"actor": pg.actor.user_id, "id": completed["id"]},
        )
        append(
            conn,
            pg,
            finished,
            "production_receipt_void",
            "-40",
            reverses_id=entry["id"],
            production_order_id=production["id"],
            production_completion_id=completed["id"],
        )
    assert effects(pg) == before
    assert detail(pg, production)["completed_quantity"] == "40"
    assert stock(pg, finished)["account"]["balance"] == "2"


@pytest.mark.parametrize("variant", ["missing", "wrong_plan", "independent"])
def test_pd_runtime_return_must_copy_exact_original_production_source(pg, variant):
    _, material, _, production, request = fixture(pg)
    issued = ok(issue(pg, production, material))
    other = ok(pg.api.command(BASE, request))
    source = None if variant == "missing" else other["id"]
    if variant == "independent":
        original = ok(
            pg.api.command(
                f"/api/v1/raw-inventory/{material['id']}/issues",
                {
                    "quantity": "1",
                    "business_date": DAY,
                    "reason": "Independent issue",
                },
            )
        )["entry"]
        issued["entry_id"] = original["id"]
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        append(
            conn,
            pg,
            material,
            "material_return",
            "1",
            returns_issue_id=issued["entry_id"],
            production_order_id=source,
        )
    assert effects(pg) == before


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE production_orders SET planned_quantity=999",
        "UPDATE production_orders SET material_name='Synthetic tamper'",
        "UPDATE production_orders SET source_quantity=999",
        "DELETE FROM production_orders",
        "UPDATE production_completions SET quantity=1",
        "UPDATE production_completions SET scrap_quantity=1",
        "DELETE FROM production_completions",
    ],
)
def test_pd_runtime_history_cannot_be_rewritten(pg, statement):
    _, _, _, production, _ = fixture(pg)
    ok(finish(pg, production))
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(text(statement))
    assert effects(pg) == before


@pytest.mark.parametrize(
    "variant", ["quantity", "material", "plan", "date", "organization", "scrap"]
)
def test_pd_runtime_completion_stock_requires_exact_source(pg, variant):
    finished, material, _, production, request = fixture(pg)
    other = ok(pg.api.command(BASE, request))
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        completed_id = insert_completion(
            conn, pg, production, "0" if variant == "scrap" else "1", "1"
        )
        append(
            conn,
            pg,
            material if variant == "material" else finished,
            "production_receipt",
            "2" if variant == "quantity" else "1",
            production_completion_id=completed_id,
            production_order_id=other["id"] if variant == "plan" else production["id"],
            organization_id=uuid4() if variant == "organization" else pg.actor.organization_id,
            business_date="2026-10-01" if variant == "date" else DAY,
        )
    assert effects(pg) == before


def test_pd_runtime_temp_table_cannot_hide_closed_source_or_completed_total(pg):
    _, material, _, production, _ = fixture(pg)
    ok(finish(pg, production, "100"))
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TEMP TABLE production_completions AS "
                "SELECT * FROM public.production_completions"
            )
        )
        conn.execute(text("DELETE FROM pg_temp.production_completions"))
        insert_completion(conn, pg, production, "1")
    assert effects(pg) == before
    ok(
        pg.api.command(
            f"{BASE}/{production['id']}/close", {"expected_version": 1, "reason": "Close"}
        )
    )
    before = effects(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("CREATE TEMP TABLE production_orders AS SELECT * FROM public.production_orders")
        )
        conn.execute(text("UPDATE pg_temp.production_orders SET status='open'"))
        append(conn, pg, material, "material_issue", "-1", production_order_id=production["id"])
    assert effects(pg) == before


def race(actions):
    barrier = Barrier(len(actions))

    def run(action):
        barrier.wait(timeout=10)
        try:
            return action()
        except BusinessError as error:
            return error.code
        except DBAPIError:
            return "DATABASE_REJECTED"

    with ThreadPoolExecutor(max_workers=len(actions)) as pool:
        return list(pool.map(run, actions))


@pytest.mark.parametrize("raw_sql", [False, True])
def test_pd_two_concurrent_completions_cannot_exceed_plan(pg, raw_sql):
    finished, _, _, production, _ = fixture(pg)

    def complete():
        if not raw_sql:
            return pg.runtime.production.complete(
                pg.actor,
                uuid4(),
                production["id"],
                {
                    "quantity": "60",
                    "business_date": DAY,
                },
            )
        with pg.runtime.engine.begin() as conn:
            completion_id = insert_completion(conn, pg, production, "60")
            append(
                conn,
                pg,
                finished,
                "production_receipt",
                "60",
                business_date=DAY,
                production_order_id=production["id"],
                production_completion_id=completion_id,
            )
        return {"id": str(completion_id)}

    results = race([complete, complete])
    assert sum(isinstance(x, dict) for x in results) == 1
    assert detail(pg, production)["completed_quantity"] == "60"


def test_pd_two_return_entrances_share_one_remaining_quantity(pg):
    _, material, _, production, _ = fixture(pg)
    issued = ok(issue(pg, production, material, "30"))
    body = {"quantity": "20", "business_date": DAY, "reason": "Concurrent return"}
    results = race(
        [
            lambda: pg.runtime.production.return_issue(
                pg.actor, uuid4(), production["id"], issued["entry_id"], body
            ),
            lambda: pg.runtime.raw_inventory.return_issue(
                pg.actor, uuid4(), issued["entry_id"], body
            ),
        ]
    )
    assert sum(isinstance(x, dict) for x in results) == 1
    assert "RAW_RETURN_EXCEEDS_ISSUED" in results
    result = pg.runtime.production.issues(pg.actor, production["id"])["items"][0]
    assert result["returned_quantity"] == "20" and result["outstanding_quantity"] == "10"


def test_pd_close_races_completion_without_allowing_late_work(pg):
    _, _, _, production, _ = fixture(pg)
    result = race(
        [
            lambda: pg.runtime.production.complete(
                pg.actor, uuid4(), production["id"], {"quantity": "60", "business_date": DAY}
            ),
            lambda: pg.runtime.production.close(
                pg.actor, uuid4(), production["id"], {"expected_version": 1, "reason": "Stop"}
            ),
        ]
    )
    after = detail(pg, production)
    assert after["status"] == "closed" and after["completed_quantity"] in {"0", "60"}
    if after["completed_quantity"] == "0":
        assert "PRODUCTION_CLOSED" in result
    assert finish(pg, production, "1").json()["code"] == "PRODUCTION_CLOSED"


@pytest.mark.parametrize("change", ["rebind", "revision"])
@pytest.mark.parametrize("raw_sql", [False, True])
def test_pd_source_change_races_issue_with_one_consistent_source(pg, change, raw_sql):
    finished, material, order, production, _ = fixture(pg)
    other = create_material(pg, name="Synthetic replacement product", unit="PCS")

    def change_source():
        if change == "rebind":
            return ok(link(pg, order, other, reason="Synthetic source correction"))
        body = order_body(pg, order["order_number"])
        body["lines"][0]["quantity"] = "200"
        return ok(
            pg.api.command(
                f"/api/v1/orders/{order['id']}/revisions",
                {
                    "order": body,
                    "expected_version": order["version"],
                    "reason": "Synthetic source revision",
                },
            )
        )

    def issue_material():
        if not raw_sql:
            return pg.runtime.production.issue(
                pg.actor,
                uuid4(),
                production["id"],
                {
                    "material_id": material["id"],
                    "quantity": "30",
                    "business_date": DAY,
                    "reason": "Synthetic concurrent issue",
                },
            )
        try:
            with pg.runtime.engine.begin() as conn:
                append(
                    conn,
                    pg,
                    material,
                    "material_issue",
                    "-30",
                    production_order_id=production["id"],
                )
            return {"issued": True}
        except DBAPIError as error:
            assert error.orig.sqlstate == "23000"
            return "SOURCE_REJECTED_BY_DATABASE"

    changed, issued = race([change_source, issue_material])
    assert isinstance(changed, dict)
    assert isinstance(issued, dict) or issued in {
        "PRODUCTION_SOURCE_CHANGED",
        "SOURCE_REJECTED_BY_DATABASE",
    }
    issued_count = int(isinstance(issued, dict))
    after = detail(pg, production)
    assert after["source_current"] is False
    assert after["material_id"] == finished["id"]
    assert after["source_revision_id"] == order["revision_id"]
    with pg.owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM inventory_ledger WHERE production_order_id=:id"),
                {"id": production["id"]},
            )
            == issued_count
        )
        assert (
            conn.scalar(
                text("SELECT balance FROM inventory_accounts WHERE material_id=:id"),
                {"id": material["id"]},
            )
            == 100 - 30 * issued_count
        )
    assert issue(pg, production, material).json()["code"] == "PRODUCTION_SOURCE_CHANGED"


def test_pd_parallel_voids_only_reverse_once(pg):
    _, _, _, production, _ = fixture(pg)
    completed = ok(finish(pg, production))

    def reverse():
        return pg.runtime.production.void(
            pg.actor,
            uuid4(),
            production["id"],
            completed["id"],
            {
                "expected_version": 1,
                "reason": "Concurrent correction",
            },
        )

    results = race([reverse, reverse])
    assert sum(isinstance(x, dict) for x in results) == 1
    assert detail(pg, production)["completed_quantity"] == "0"
    with pg.owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM inventory_ledger WHERE kind='production_receipt_void'")
            )
            == 1
        )
