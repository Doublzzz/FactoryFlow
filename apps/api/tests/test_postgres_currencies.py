"""Real money boundaries: no conversion, mixed-currency claims or partial commits."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.database import Journal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_statement_lifecycle import approve, blank, command, detail, setup_statement


def order_input(pg, currency):
    return {
        "customer_id": pg.customer_id,
        "order_number": "SYN-CURRENCY-" + uuid4().hex,
        "business_date": "2026-10-01",
        "currency": currency,
        "lines": [
            {
                "description": "Synthetic part",
                "quantity": "100",
                "unit": "PCS",
                "source_unit_price": "2.3456",
                "source_amount": None,
            }
        ],
    }


def delivered(pg, currency):
    confirmed = command(pg, "/api/v1/orders", order_input(pg, currency))
    order = pg.api.request("GET", f"/api/v1/orders/{confirmed['order_id']}").json()
    delivery = command(
        pg,
        "/api/v1/deliveries",
        {
            "order_id": order["id"],
            "customer_id": pg.customer_id,
            "revision_id": order["revision_id"],
            "expected_version": order["version"],
            "delivery_date": "2026-10-02",
            "lines": [{"order_line_id": order["lines"][0]["id"], "quantity": "30"}],
        },
    )
    return order, delivery


def draft_input(pg, currency, delivery=None, start="2026-10-01", end="2026-10-31"):
    return {
        "customer_id": pg.customer_id,
        "currency": currency,
        "period_start": start,
        "period_end": end,
        "tax_mode": "untaxed_final",
        "tax_rate": "0",
        "adjustments": [],
        "lines": (
            [
                {
                    "delivery_id": delivery["id"],
                    "order_line_id": delivery["lines"][0]["order_line_id"],
                    "quantity": "30",
                    "unit_price": "2.3456",
                    "reason": "",
                }
            ]
            if delivery
            else []
        ),
    }


def business_counts(pg):
    with pg.owner.connect() as conn:
        return tuple(
            conn.scalar(text(f"SELECT count(*) FROM {name}"))
            for name in (
                "orders",
                "confirmed_revisions",
                "statements",
                "statement_lines",
                "statement_events",
                "command_results",
                "audit_events",
            )
        )


def test_usd_partial_delivery_statement_replay_and_void_preserve_currency(pg):
    order, delivery = delivered(pg, "USD")
    evidence = pg.api.request("GET", f"/api/v1/documents/{order['revision_id']}/download").content
    current = pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()
    assert current["currency"] == "USD"
    assert current["lines"][0]["remaining_quantity"] == "70"
    body, key = draft_input(pg, "USD", delivery), uuid4()
    statement = command(pg, "/api/v1/statements", body, key)
    assert statement["currency"] == statement["lines"][0]["source"]["currency"] == "USD"
    assert statement["calculation"]["total"] == "70.37"
    assert command(pg, "/api/v1/statements", body, key) == statement
    before = business_counts(pg)
    conflict = pg.api.command("/api/v1/statements", body | {"currency": "CNY"}, key)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert business_counts(pg) == before
    command(
        pg,
        f"/api/v1/deliveries/{delivery['id']}/void",
        {
            "expected_version": 1,
            "reason": "Synthetic correction",
        },
    )
    assert detail(pg, statement["id"])["calculation"]["total"] == "0.00"
    assert detail(pg, statement["id"])["currency"] == "USD"
    assert (
        pg.api.request("GET", f"/api/v1/orders/{order['id']}").json()["lines"][0][
            "remaining_quantity"
        ]
        == "100"
    )
    assert (
        pg.api.request("GET", f"/api/v1/documents/{order['revision_id']}/download").content
        == evidence
    )


@pytest.mark.parametrize("currency,other", [("CNY", "USD"), ("USD", "CNY")])
def test_order_currency_cannot_change_by_revision_or_sql(pg, currency, other):
    body = order_input(pg, currency)
    confirmed = command(pg, "/api/v1/orders", body)
    before = business_counts(pg)
    response = pg.api.command(
        f"/api/v1/orders/{confirmed['order_id']}/revisions",
        {
            "order": body | {"currency": other},
            "expected_version": 1,
            "reason": "Synthetic currency edit",
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "ORDER_CURRENCY_IMMUTABLE"
    assert business_counts(pg) == before
    with pytest.raises(DBAPIError, match="currency"), pg.owner.begin() as conn:
        conn.execute(
            text("UPDATE orders SET currency=:currency WHERE id=:id"),
            {"currency": other, "id": confirmed["order_id"]},
        )


def test_same_customer_period_has_separate_currencies_and_rejects_mixed_lines(pg):
    _, usd = delivered(pg, "USD")
    _, cny = delivered(pg, "CNY")
    dollar = command(pg, "/api/v1/statements", draft_input(pg, "USD", usd))
    yuan = command(pg, "/api/v1/statements", draft_input(pg, "CNY", cny))
    assert dollar["id"] != yuan["id"]
    before = business_counts(pg)
    mixed = draft_input(pg, "USD", cny, "2026-10-02")
    mixed["lines"][0]["quantity"] = "0"
    mixed["lines"][0]["reason"] = "Synthetic defer"
    response = pg.api.command("/api/v1/statements", mixed)
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "STATEMENT_CURRENCY_MISMATCH"
    assert business_counts(pg) == before
    # SQL cannot spoof the JSON currency to match a different header.
    with pytest.raises(DBAPIError, match="currency"), pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO statement_lines
            (organization_id,statement_id,customer_id,delivery_id,order_line_id,quantity,
             unit_price,status,reason,source,external_document_number)
            SELECT organization_id,:target,customer_id,delivery_id,order_line_id,0,
            unit_price,'deferred','Synthetic defer',
            jsonb_set(source,'{currency}','"USD"'),external_document_number
            FROM statement_lines WHERE statement_id=:source"""),
            {"target": dollar["id"], "source": yuan["id"]},
        )


def test_statement_currency_is_immutable_and_other_organization_cannot_read(pg):
    statement = command(pg, "/api/v1/statements", draft_input(pg, "USD"))
    response = pg.api.command(
        f"/api/v1/statements/{statement['id']}/save",
        {
            **draft_input(pg, "CNY"),
            "expected_version": 1,
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["code"] == "STATEMENT_CURRENCY_IMMUTABLE"
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("UPDATE statements SET currency='CNY' WHERE id=:id"), {"id": statement["id"]}
        )
    outsider = Actor(uuid4(), pg.actor.user_id, pg.actor.username, pg.actor.role)
    with pytest.raises(BusinessError, match="STATEMENT_NOT_FOUND"):
        pg.runtime.statements.detail(outsider, UUID(statement["id"]))


def test_usd_late_audit_failure_rolls_back_whole_command(pg, monkeypatch):
    _, delivery = delivered(pg, "USD")
    before = business_counts(pg)

    def fail(*_args, **_kwargs):
        raise RuntimeError("Synthetic late audit failure")

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic late audit failure"):
        pg.runtime.statements.create(pg.actor, uuid4(), draft_input(pg, "USD", delivery))
    assert business_counts(pg) == before
    with pg.owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM statement_balances")) == 0


def test_concurrent_same_currency_period_keeps_database_uniqueness(pg):
    barrier = Barrier(2)

    def create(_):
        barrier.wait()
        try:
            pg.runtime.statements.create(pg.actor, uuid4(), draft_input(pg, "USD"))
            return "created"
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == ["STATEMENT_PERIOD_EXISTS", "created"]
    assert command(pg, "/api/v1/statements", draft_input(pg, "CNY"))["currency"] == "CNY"


def test_currency_filter_keeps_pagination_and_only_matching_overlaps(pg):
    _, usd = delivered(pg, "USD")
    delivered(pg, "CNY")
    dollar = command(pg, "/api/v1/statements", draft_input(pg, "USD", usd))
    command(pg, "/api/v1/statements", draft_input(pg, "CNY"))
    params = {
        "customer_id": pg.customer_id,
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "currency": "USD",
        "limit": 1,
    }
    items, cursors = [], set()
    while True:
        response = pg.api.request("GET", "/api/v1/statement-candidates", params=params)
        assert response.status_code == 200, response.text
        page = response.json()
        items.extend(page["items"])
        assert page["overlapping_statements"] == [dollar["id"]]
        if not page["next_cursor"]:
            break
        assert page["next_cursor"] not in cursors
        cursors.add(page["next_cursor"])
        params["cursor"] = page["next_cursor"]
    assert len(items) == 1 and items[0]["currency"] == "USD"


def test_lifecycle_rejects_cross_currency_review_and_reservation_in_service_and_database(pg):
    statement, source, sent, feedback = setup_statement(pg, currency="USD")
    approval = approve(pg, statement, source, sent, feedback, "90")
    review = command(
        pg,
        f"/api/v1/statements/{statement['id']}/review",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            **source,
            "quantity": "10",
            "reason": "Synthetic review",
        },
    )
    other = blank(pg, "2026-10-01", "2026-10-31", "CNY")
    bodies = {
        "reserve": {
            "expected_version": 1,
            "approval_id": approval["id"],
            "approval_version": approval["version"],
            "quantity": "1",
            "reason": "Synthetic cross currency",
        },
        "claim-review": {
            "expected_version": 1,
            "review_id": review["id"],
            "review_version": review["version"],
            "quantity": "1",
            "unit_price": "10",
            "reason": "Synthetic cross currency",
        },
    }
    before = business_counts(pg)
    for action, body in bodies.items():
        response = pg.api.command(f"/api/v1/statements/{other['id']}/{action}", body)
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "STATEMENT_CURRENCY_MISMATCH"
    assert business_counts(pg) == before
    params = {
        "org": pg.actor.organization_id,
        "actor": pg.actor.user_id,
        "customer": pg.customer_id,
        "statement": other["id"],
        "approval": approval["id"],
        "review": review["id"],
    }
    for query in [
        """INSERT INTO statement_allocations(organization_id,id,customer_id,approval_id,
           statement_id,quantity,unit_price,status,reason,actor_id)
           VALUES(:org,gen_random_uuid(),:customer,:approval,:statement,1,10,
           'reserved','Synthetic',:actor)""",
        """INSERT INTO statement_review_transfers(organization_id,id,customer_id,review_id,
           statement_id,quantity,status,reason,actor_id)
           VALUES(:org,gen_random_uuid(),:customer,:review,:statement,1,'claimed','Synthetic',:actor)""",
    ]:
        with pytest.raises(DBAPIError, match="currency"), pg.owner.begin() as conn:
            conn.execute(text(query), params)
    assert detail(pg, other["id"])["version"] == 1


def test_runtime_temporary_tables_cannot_spoof_authoritative_order_currency(pg):
    _, cny = delivered(pg, "CNY")
    yuan = command(pg, "/api/v1/statements", draft_input(pg, "CNY", cny))
    dollar = command(pg, "/api/v1/statements", draft_input(pg, "USD"))
    with pytest.raises(DBAPIError, match="currency"), pg.runtime.engine.begin() as conn:
        conn.execute(text("CREATE TEMP TABLE orders AS SELECT * FROM public.orders"))
        conn.execute(text("UPDATE pg_temp.orders SET currency='USD'"))
        conn.execute(text("CREATE TEMP TABLE order_lines AS SELECT * FROM public.order_lines"))
        conn.execute(
            text("""INSERT INTO public.statement_lines
            (organization_id,statement_id,customer_id,delivery_id,order_line_id,quantity,
             unit_price,status,reason,source,external_document_number)
            SELECT organization_id,:target,customer_id,delivery_id,order_line_id,0,
            unit_price,'deferred','Synthetic spoof',
            jsonb_set(source,'{currency}','"USD"'),external_document_number
            FROM public.statement_lines WHERE statement_id=:source"""),
            {"target": dollar["id"], "source": yuan["id"]},
        )
