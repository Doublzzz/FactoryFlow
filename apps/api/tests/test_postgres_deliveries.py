from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import Actor, BusinessError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_orders import confirm


def delivery_body(pg):
    result = confirm(pg)
    order = pg.api.request("GET", f"/api/v1/orders/{result['order_id']}").json()
    return {
        "order_id": order["id"],
        "customer_id": order["customer_id"],
        "revision_id": order["revision_id"],
        "expected_version": order["version"],
        "delivery_date": "2026-10-01",
        "lines": [
            {"order_line_id": line["id"], "quantity": qty}
            for line, qty in zip(order["lines"], ["0.125", "1"], strict=True)
        ],
    }


def test_delivery_and_void_reverse_exactly_without_changing_evidence(pg):
    body = delivery_body(pg)
    before = pg.api.request("GET", f"/api/v1/documents/{body['revision_id']}/download").content
    result = pg.api.command("/api/v1/deliveries", body)
    assert result.status_code == 200, result.text
    created = result.json()
    order = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    assert order["version"] == 2
    assert [line["remaining_quantity"] for line in order["lines"]] == ["1", "1"]
    void = pg.api.command(
        f"/api/v1/deliveries/{created['id']}/void",
        {"expected_version": 1, "reason": "Synthetic correction"},
        uuid4(),
    )
    assert void.status_code == 200, void.text
    order = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    assert order["version"] == 3
    assert [line["remaining_quantity"] for line in order["lines"]] == ["1.125", "2"]
    assert (
        pg.api.request("GET", f"/api/v1/documents/{body['revision_id']}/download").content == before
    )


def snapshot(pg):
    with pg.owner.connect() as conn:
        return tuple(
            conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in [
                "deliveries",
                "delivery_lines",
                "fulfillment_actions",
                "order_events",
                "audit_events",
                "command_results",
            ]
        )


def test_normalized_replay_conflict_and_repeat_void(pg):
    body = delivery_body(pg)
    key = uuid4()
    first = pg.api.command("/api/v1/deliveries", body, key)
    assert first.status_code == 200
    counts = snapshot(pg)
    body["lines"][1]["quantity"] = "1.000"
    body["lines"].reverse()
    assert pg.api.command("/api/v1/deliveries", body, key).json() == first.json()
    assert snapshot(pg) == counts
    body["delivery_date"] = "2026-10-02"
    assert pg.api.command("/api/v1/deliveries", body, key).json()["code"] == "IDEMPOTENCY_CONFLICT"
    path = f"/api/v1/deliveries/{first.json()['id']}/void"
    void_key, request = uuid4(), {"expected_version": 1, "reason": "Synthetic void"}
    voided = pg.api.command(path, request, void_key)
    assert voided.status_code == 200
    counts = snapshot(pg)
    assert pg.api.command(path, request, void_key).json() == voided.json()
    assert pg.api.command(path, request).json()["code"] == "DELIVERY_NOT_ACTIVE"
    assert snapshot(pg) == counts
    with pg.owner.connect() as conn:
        assert (
            conn.execute(
                text(
                    "SELECT count(*) FROM fulfillment_actions v JOIN fulfillment_actions c "
                    "ON c.id=v.reverses_id WHERE v.action='void' AND c.action='create'"
                )
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize(
    "quantity", ["0", "-1", "1e0", "0.0001", "1.0000", 0.125, "NaN", "Infinity", "2"]
)
def test_rejected_quantity_has_no_effect(pg, quantity):
    body = delivery_body(pg)
    body["lines"][0]["quantity"] = quantity
    before = snapshot(pg)
    result = pg.api.command("/api/v1/deliveries", body)
    assert result.status_code in {409, 422}, result.text
    assert snapshot(pg) == before


@pytest.mark.parametrize(
    "mutation",
    ["integer_fraction", "duplicate", "customer", "revision", "line", "version", "deleted"],
)
def test_source_and_state_rejections(pg, mutation):
    body = delivery_body(pg)
    if mutation == "integer_fraction":
        body["lines"][1]["quantity"] = "0.5"
    elif mutation == "duplicate":
        body["lines"].append(body["lines"][0])
    elif mutation in {"customer", "revision"}:
        body[f"{mutation}_id"] = str(uuid4())
    elif mutation == "line":
        body["lines"][0]["order_line_id"] = str(uuid4())
    elif mutation == "version":
        body["expected_version"] = 2
    else:
        assert (
            pg.api.command(
                f"/api/v1/orders/{body['order_id']}/delete",
                {"expected_version": 1, "reason": "Synthetic deleted"},
            ).status_code
            == 200
        )
        body["expected_version"] = 2
    before = snapshot(pg)
    assert pg.api.command("/api/v1/deliveries", body).status_code in {409, 422}
    assert snapshot(pg) == before


@pytest.mark.parametrize("command", ["create", "void"])
@pytest.mark.parametrize("failure_table", ["audit_events", "command_results"])
def test_late_failure_rolls_back_ledger_projection_status_and_journal(pg, command, failure_table):
    body = delivery_body(pg)
    path, request = "/api/v1/deliveries", body
    if command == "void":
        created = pg.api.command(path, body).json()
        path = f"{path}/{created['id']}/void"
        request = {"expected_version": 1, "reason": "Synthetic rollback"}
    before = snapshot(pg)
    order = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    delivery_before = (
        pg.api.request("GET", path.removesuffix("/void")).json() if command == "void" else None
    )
    with pg.owner.begin() as conn:
        conn.execute(
            text(f"""CREATE FUNCTION fail_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
         BEGIN IF NEW.command_type='delivery.{command}' THEN
          RAISE EXCEPTION 'synthetic failure'; END IF;
         RETURN NEW; END; $$;
         CREATE TRIGGER fail_delivery BEFORE INSERT ON {failure_table}
         FOR EACH ROW EXECUTE FUNCTION fail_delivery();""")
        )
    assert pg.api.command(path, request).status_code == 503
    assert snapshot(pg) == before
    assert pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json() == order
    if command == "void":
        assert pg.api.request("GET", path.removesuffix("/void")).json() == delivery_before


@pytest.mark.parametrize("kind", ["create", "same_key", "void", "revise"])
def test_two_connections_arbitrate_without_double_effect(pg, kind):
    body = delivery_body(pg)
    body["lines"][0]["quantity"] = "1.125"
    body["lines"][1]["quantity"] = "2"
    created = pg.runtime.deliveries.create(pg.actor, uuid4(), body) if kind == "void" else None
    barrier, key = Barrier(2), uuid4()

    def run(index):
        barrier.wait(timeout=10)
        try:
            if kind == "void":
                return pg.runtime.deliveries.void(
                    pg.actor, uuid4(), created["id"], 1, "Synthetic concurrent"
                )["status"]
            if kind == "revise" and index == 1:
                from test_postgres_orders import order_body

                return pg.runtime.orders.revise(
                    pg.actor, uuid4(), body["order_id"], 1, order_body(pg), "Synthetic concurrent"
                )["status"]
            return pg.runtime.deliveries.create(
                pg.actor, key if kind == "same_key" else uuid4(), body
            )["status"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results.count("active") == (2 if kind == "same_key" else 0 if kind == "void" else 1), (
        results
    )
    if kind == "void":
        assert sorted(results) == ["DELIVERY_NOT_ACTIVE", "void"]
    elif kind != "same_key":
        assert "VERSION_CONFLICT" in results
    order = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    assert order["version"] == (3 if kind == "void" else 2)
    if kind in {"create", "same_key"}:
        assert pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"] == []


def test_ownership_roles_print_and_historical_snapshot(pg):
    body = delivery_body(pg)
    created = pg.api.command("/api/v1/deliveries", body).json()
    foreign = Actor(uuid4(), uuid4(), "synthetic-other", "operator")
    for read in [
        lambda: pg.runtime.deliveries.detail(foreign, created["id"]),
        lambda: pg.runtime.deliveries.create(foreign, uuid4(), body),
        lambda: pg.runtime.deliveries.void(foreign, uuid4(), created["id"], 1, "Synthetic"),
    ]:
        with pytest.raises(BusinessError) as error:
            read()
        assert error.value.status == 404
    assert pg.runtime.deliveries.list(foreign)["items"] == []
    pg.runtime.identity.add_user(pg.actor, "synthetic-viewer", SYNTHETIC_PASSWORD, "viewer")
    viewer = API(pg.app)
    viewer.login("synthetic-viewer")
    assert viewer.command("/api/v1/deliveries", body).status_code == 403
    path = f"/api/v1/deliveries/{created['id']}"
    assert (
        viewer.command(path + "/void", {"expected_version": 1, "reason": "Synthetic"}).status_code
        == 403
    )
    assert viewer.request("GET", path + "/print").status_code == 200
    assert API(pg.app).request("GET", path + "/print").status_code == 401
    assert (
        pg.api.command(
            path + "/void", {"expected_version": 1, "reason": "Synthetic void"}
        ).status_code
        == 200
    )
    from test_postgres_orders import order_body

    revised = order_body(pg)
    revised["lines"][0]["description"] = "Synthetic changed after void"
    assert (
        pg.api.command(
            f"/api/v1/orders/{body['order_id']}/revisions",
            {"order": revised, "expected_version": 3, "reason": "Synthetic revision"},
        ).status_code
        == 200
    )
    history = pg.api.request("GET", path).json()
    assert history["lines"] == created["lines"]
    printed = pg.api.request("GET", path + "/print").text
    assert "已作废" in printed and "0.125" in printed
    assert "Synthetic changed after void" not in printed


def test_database_rejects_unbalanced_projection_and_mutable_snapshots(pg):
    body = delivery_body(pg)
    assert pg.api.command("/api/v1/deliveries", body).status_code == 200
    for statement in [
        "UPDATE order_lines SET delivered_quantity=0",
        "UPDATE delivery_lines SET quantity=quantity",
        "DELETE FROM delivery_lines",
        "UPDATE fulfillment_actions SET reason=reason",
        "DELETE FROM fulfillment_actions",
        "UPDATE deliveries SET customer_name=customer_name",
        "DELETE FROM deliveries",
        "UPDATE orders SET status='deleted'",
    ]:
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(statement))
    for statement in [
        "UPDATE order_lines SET quantity=quantity",
        "UPDATE deliveries SET customer_name=customer_name",
    ]:
        with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
            conn.execute(text(statement))


def test_database_rejects_forged_source_and_quantity(pg):
    body = delivery_body(pg)
    pg.api.command("/api/v1/deliveries", body)
    for assignment in [
        "quantity=1.0000",
        "quantity='NaN'",
        "quantity='Infinity'",
        "quantity=0",
        "quantity=-1",
        "quantity=9223372036854775.808",
        "revision_id=gen_random_uuid()",
        "order_id=gen_random_uuid()",
        "organization_id=gen_random_uuid()",
        "description='Synthetic forged'",
    ]:
        # Exercise INSERT checks rather than immutable UPDATE triggers.
        with pytest.raises(DBAPIError) as error, pg.owner.begin() as conn:
            new_id = uuid4()
            conn.execute(
                text("""INSERT INTO deliveries
              (id,organization_id,order_id,customer_id,revision_id,delivery_date,customer_name,order_number)
              SELECT :new,organization_id,order_id,customer_id,revision_id,delivery_date,
                     customer_name,order_number FROM deliveries LIMIT 1"""),
                {"new": new_id},
            )
            conn.execute(
                text("CREATE TEMP TABLE synthetic_line AS SELECT * FROM delivery_lines LIMIT 1")
            )
            conn.execute(text("UPDATE synthetic_line SET " + assignment))
            conn.execute(text("UPDATE synthetic_line SET delivery_id=:new"), {"new": new_id})
            conn.execute(text("INSERT INTO delivery_lines SELECT * FROM synthetic_line"))
        assert error.value.orig.sqlstate == (
            "23514" if assignment.startswith("quantity=") else "23000"
        )


@pytest.mark.parametrize("voided", [False, True])
def test_database_seals_line_membership_after_create(pg, voided):
    body = delivery_body(pg)
    second = body["lines"].pop()
    created = pg.api.command("/api/v1/deliveries", body).json()
    if voided:
        assert (
            pg.api.command(
                f"/api/v1/deliveries/{created['id']}/void",
                {"expected_version": 1, "reason": "Synthetic seal"},
            ).status_code
            == 200
        )
    with pytest.raises(DBAPIError) as error, pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO delivery_lines
          (organization_id,delivery_id,order_id,revision_id,order_line_id,line_number,quantity,
           description,source_unit,canonical_unit,quantity_policy)
          SELECT organization_id,:delivery,order_id,revision_id,id,line_number,1,
                 description,source_unit,canonical_unit,quantity_policy
          FROM order_lines WHERE id=:line"""),
            {"delivery": created["id"], "line": second["order_line_id"]},
        )
        if not voided:
            conn.execute(
                text("UPDATE order_lines SET delivered_quantity=1 WHERE id=:line"),
                {"line": second["order_line_id"]},
            )
    assert error.value.orig.sqlstate == "23000"
    assert "sealed delivery" in str(error.value.orig)


def test_database_requires_void_reasons_and_header_ownership(pg):
    body = delivery_body(pg)
    created = pg.api.command("/api/v1/deliveries", body).json()
    with pytest.raises(DBAPIError) as error, pg.owner.begin() as conn:
        conn.execute(text("UPDATE deliveries SET status='void',version=2,voided_at=now()"))
    assert error.value.orig.sqlstate == "23514"
    with pytest.raises(DBAPIError) as error, pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO fulfillment_actions
          (id,organization_id,delivery_id,action,reverses_id,actor_id)
          SELECT gen_random_uuid(),organization_id,delivery_id,'void',id,actor_id
          FROM fulfillment_actions WHERE delivery_id=:id"""),
            {"id": created["id"]},
        )
    assert error.value.orig.sqlstate == "23514"
    for column in ("organization_id", "customer_id", "order_id", "revision_id"):
        with pytest.raises(DBAPIError) as error, pg.owner.begin() as conn:
            conn.execute(
                text("CREATE TEMP TABLE synthetic_header AS SELECT * FROM deliveries LIMIT 1")
            )
            conn.execute(
                text(f"UPDATE synthetic_header SET id=gen_random_uuid(),{column}=gen_random_uuid()")
            )
            conn.execute(text("INSERT INTO deliveries SELECT * FROM synthetic_header"))
        assert error.value.orig.sqlstate == "23503"


def test_database_last_quantity_guard_without_application_order_lock(pg):
    """Bypass service/version/event locks to prove the numeric guard itself arbitrates."""
    from factoryflow.modules.fulfillment.adapters.repository import DeliveryRepository
    from factoryflow.modules.fulfillment.domain.delivery import prepare_delivery
    from factoryflow.modules.orders.adapters.repository import OrderRepository

    body = delivery_body(pg)
    body["lines"] = [body["lines"][0]]
    body["lines"][0]["quantity"] = "1.125"
    request = prepare_delivery(body)
    order = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    line = {**order["lines"][0], "quantity": "1.125"}
    barrier = Barrier(2)

    def direct_write():
        barrier.wait(timeout=10)
        try:
            with pg.runtime.engine.begin() as conn:
                deliveries = DeliveryRepository(conn)
                identifier = uuid4()
                deliveries.insert(
                    pg.actor,
                    identifier,
                    request,
                    order,
                    {"full_name": "Synthetic Customer"},
                    [line],
                )
                OrderRepository(conn).apply_delivery(
                    pg.actor, order["id"], request.quantities, False
                )
                deliveries.inventory_snapshots(
                    pg.actor,
                    identifier,
                    {
                        line["id"]: {
                            "state": "unlinked",
                            "material_id": None,
                            "canonical_unit": line["canonical_unit"],
                            "quantity": "1.125",
                            "movement_id": None,
                            "reason": None,
                            "mode": "sync",
                            "shortage_confirmed": False,
                        },
                    },
                )
                deliveries.action(pg.actor, identifier, "create", None, None)
            return "created"
        except DBAPIError as error:
            assert error.orig.sqlstate == "23514"
            assert error.orig.diag.constraint_name == "order_lines_check"
            return "quantity_rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: direct_write(), range(2)))
    assert sorted(results) == ["created", "quantity_rejected"]
    assert snapshot(pg)[0] == 1
    detail = pg.api.request("GET", f"/api/v1/orders/{body['order_id']}").json()
    assert detail["lines"][0]["delivered_quantity"] == "1.125"
