from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.database import Journal
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_deliveries import delivery_body


def source(pg):
    body = delivery_body(pg)
    response = pg.api.command("/api/v1/deliveries", body)
    assert response.status_code == 200, response.text
    return response.json()


def draft(pg, delivery, quantity="0.1", start="2026-10-01", end="2026-10-31"):
    return {
        "customer_id": pg.customer_id,
        "period_start": start,
        "period_end": end,
        "tax_mode": "untaxed_final",
        "tax_rate": "0",
        "adjustments": [],
        "lines": [
            {
                "delivery_id": delivery["id"],
                "order_line_id": delivery["lines"][0]["order_line_id"],
                "quantity": quantity,
                "unit_price": "2.3456",
                "reason": "Synthetic partial",
            }
        ],
    }


def test_partial_save_release_and_replay(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    key = uuid4()
    response = pg.api.command("/api/v1/statements", body, key)
    assert response.status_code == 200, response.text
    created = response.json()
    assert created["calculation"]["total"] == "0.23"
    assert pg.api.command("/api/v1/statements", body, key).json() == created
    body["lines"][0]["quantity"] = "0.125"
    result = pg.api.command(
        f"/api/v1/statements/{created['id']}/save", body | {"expected_version": 1}
    )
    assert result.status_code == 200, result.text
    abandoned = pg.api.command(
        f"/api/v1/statements/{created['id']}/abandon",
        {"expected_version": 2, "reason": "Synthetic abandon"},
    )
    assert abandoned.status_code == 200, abandoned.text
    assert abandoned.json()["status"] == "abandoned"


def test_source_void_removes_current_amount_preserves_history(pg):
    delivery = source(pg)
    response = pg.api.command("/api/v1/statements", draft(pg, delivery))
    assert response.status_code == 200, response.text
    created = response.json()
    void = pg.api.command(
        f"/api/v1/deliveries/{delivery['id']}/void",
        {"expected_version": 1, "reason": "Synthetic correction"},
    )
    assert void.status_code == 200, void.text
    updated = pg.api.request("GET", f"/api/v1/statements/{created['id']}").json()
    assert updated["version"] == 2
    assert updated["lines"][0]["status"] == "source_void"
    assert updated["calculation"]["total"] == "0.00"
    assert len(updated["history"]) == 2


def test_candidates_carry_forward_paginate_and_keep_original_prices(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    created = pg.api.command("/api/v1/statements", body).json()
    params = {
        "customer_id": pg.customer_id,
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "limit": 1,
    }
    result = pg.api.request("GET", "/api/v1/statement-candidates", params=params)
    assert result.status_code == 200, result.text
    pages = [result.json()]
    while pages[-1]["next_cursor"]:
        pages.append(
            pg.api.request(
                "GET",
                "/api/v1/statement-candidates",
                params=params | {"cursor": pages[-1]["next_cursor"]},
            ).json()
        )
    rows = [item for page in pages for item in page["items"]]
    assert len(rows) == 2
    matched = next(row for row in rows if row["order_line_id"] == body["lines"][0]["order_line_id"])
    assert matched["available_quantity"] == "0.025"
    assert matched["source_unit_price"] is None
    assert matched["cross_period"] is True
    own = pg.api.request(
        "GET",
        "/api/v1/statement-candidates",
        params=params | {"limit": 100, "statement_id": created["id"]},
    ).json()
    assert (
        next(row for row in own["items"] if row["order_line_id"] == matched["order_line_id"])[
            "available_quantity"
        ]
        == "0.125"
    )
    assert (
        pg.runtime.statements.list(pg.actor, UUID(pg.customer_id))["items"][0]["id"]
        == created["id"]
    )
    listing = pg.api.request("GET", "/api/v1/statements", params={"customer_id": pg.customer_id})
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["id"] == created["id"]


@pytest.mark.parametrize("quantity,successes", [("0.1", 1), ("0.06", 2)])
def test_competing_drafts_never_overallocate(pg, quantity, successes):
    delivery = source(pg)
    barrier = Barrier(2)

    def run(index):
        body = draft(pg, delivery, quantity, f"2026-10-{index + 1:02d}")
        barrier.wait()
        try:
            return pg.runtime.statements.create(pg.actor, uuid4(), body)["status"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert results.count("draft") == successes, results
    if successes == 1:
        assert "STATEMENT_QUANTITY_EXCEEDED" in results


def test_database_serializes_competing_updates_without_service(pg):
    delivery = source(pg)
    drafts = [
        pg.runtime.statements.create(
            pg.actor, uuid4(), draft(pg, delivery, "0.01", f"2026-10-{index + 1:02d}")
        )
        for index in range(2)
    ]
    barrier = Barrier(2)

    def run(item):
        barrier.wait()
        try:
            with pg.owner.begin() as conn:
                conn.execute(
                    text("UPDATE statement_lines SET quantity=0.1 WHERE statement_id=:id"),
                    {"id": item["id"]},
                )
            return "committed"
        except DBAPIError as error:
            return error.orig.sqlstate

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, drafts))
    assert results.count("committed") == 1, results
    assert results.count("23514") == 1, results
    with pg.owner.connect() as conn:
        assert (
            str(conn.execute(text("SELECT claimed FROM statement_balances")).scalar_one()) == "0.11"
        )


def test_database_guards_precision_ownership_and_source_snapshots(pg):
    delivery = source(pg)
    pg.runtime.statements.create(pg.actor, uuid4(), draft(pg, delivery))
    for sql in [
        "UPDATE statement_lines SET quantity=0.2",
        "UPDATE statement_lines SET quantity=0.1000",
        "UPDATE statement_lines SET quantity='NaN'",
        "UPDATE statement_lines SET unit_price=0.12345",
        "UPDATE statement_lines SET source='{}'::jsonb",
        "UPDATE statement_lines SET customer_id=gen_random_uuid()",
        "UPDATE statement_balances SET claimed=0",
        "DELETE FROM statement_balances",
        "UPDATE statement_balances SET order_line_id=gen_random_uuid()",
        "DELETE FROM statement_lines",
        "DELETE FROM statement_events",
        "UPDATE statements SET status='abandoned',version=version+1",
    ]:
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(sql))


def test_late_audit_failure_rolls_back_draft_and_delivery_void(pg, monkeypatch):
    delivery = source(pg)
    real_audit = Journal.audit

    def fail(self, actor, command, identifier):
        if command.startswith("statement."):
            raise RuntimeError("synthetic audit failure")
        return real_audit(self, actor, command, identifier)

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        pg.runtime.statements.create(pg.actor, uuid4(), draft(pg, delivery))
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM statements")).scalar_one() == 0
        assert conn.execute(text("SELECT count(*) FROM statement_balances")).scalar_one() == 0
    monkeypatch.setattr(Journal, "audit", real_audit)
    created = pg.runtime.statements.create(pg.actor, uuid4(), draft(pg, delivery))
    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        pg.runtime.deliveries.void(pg.actor, uuid4(), delivery["id"], 1, "Synthetic rollback")
    assert pg.runtime.deliveries.detail(pg.actor, delivery["id"])["status"] == "active"
    assert pg.runtime.statements.detail(pg.actor, created["id"])["version"] == 1


def test_same_period_version_conflict_release_and_explicit_reopen(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    created = pg.api.command("/api/v1/statements", body).json()
    path = f"/api/v1/statements/{created['id']}"
    assert pg.api.command("/api/v1/statements", body).json()["code"] == "STATEMENT_PERIOD_EXISTS"
    assert (
        pg.api.command(path + "/save", body | {"expected_version": 2}).json()["code"]
        == "VERSION_CONFLICT"
    )
    key = uuid4()
    request = {"expected_version": 1, "reason": "Synthetic abandoned"}
    result = pg.api.command(path + "/abandon", request, key)
    assert result.status_code == 200, result.text
    assert pg.api.command(path + "/abandon", request, key).json() == result.json()
    reopened = pg.api.command(
        path + "/reopen", body | {"expected_version": 2, "reason": "Synthetic reopened"}
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["id"] == created["id"] and reopened.json()["version"] == 3
    assert len(reopened.json()["history"]) == 3
    assert (
        pg.api.command(path + "/abandon", request | {"reason": "changed"}, key).json()["code"]
        == "IDEMPOTENCY_CONFLICT"
    )


def test_tax_adjustment_void_and_customer_defaults_do_not_rewrite_draft(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    body["tax_mode"], body["tax_rate"] = "add_tax", "10"
    body["adjustments"] = [
        {
            "stage": "before_tax",
            "kind": "discount",
            "amount": "-0.01",
            "reason": "Synthetic discount",
            "delivery_id": delivery["id"],
            "order_line_id": body["lines"][0]["order_line_id"],
        }
    ]
    created = pg.api.command("/api/v1/statements", body)
    assert created.status_code == 200, created.text
    settings = pg.api.command(
        f"/api/v1/customers/{pg.customer_id}/statement-settings",
        {
            "expected_version": 0,
            "cycle_day": 20,
            "tax_mode": "included",
            "tax_rate": "5",
            "reason": "Synthetic default",
        },
    )
    assert settings.status_code == 200, settings.text
    assert pg.runtime.statements.detail(pg.actor, created.json()["id"])["tax_rate"] == "10"
    pg.runtime.deliveries.void(pg.actor, uuid4(), delivery["id"], 1, "Synthetic void")
    changed = pg.runtime.statements.detail(pg.actor, created.json()["id"])
    assert changed["adjustments"][0]["status"] == "needs_review"
    assert changed["calculation"]["total"] is None
    assert "ADJUSTMENT_REVIEW_REQUIRED" in changed["calculation"]["warnings"]


def test_ownership_permissions_and_fractional_pieces(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    other = pg.api.command("/api/v1/customers", {"full_name": "Synthetic Other"}).json()["id"]
    assert (
        pg.api.command("/api/v1/statements", body | {"customer_id": other}).json()["code"]
        == "STATEMENT_SOURCE_INVALID"
    )
    foreign = Actor(uuid4(), uuid4(), "synthetic-other", "operator")
    with pytest.raises(BusinessError):
        pg.runtime.statements.create(foreign, uuid4(), body)
    viewer = Actor(pg.actor.organization_id, pg.actor.user_id, "synthetic-viewer", "viewer")
    with pytest.raises(BusinessError, match="WRITE_FORBIDDEN"):
        pg.runtime.statements.create(viewer, uuid4(), body)
    body["lines"][0]["order_line_id"] = delivery["lines"][1]["order_line_id"]
    assert (
        pg.api.command("/api/v1/statements", body).json()["code"]
        == "UNIT_REQUIRES_INTEGER_QUANTITY"
    )


def test_source_void_races_with_save(pg):
    delivery = source(pg)
    body = draft(pg, delivery)
    created = pg.runtime.statements.create(pg.actor, uuid4(), body)
    barrier = Barrier(2)

    def run(index):
        barrier.wait()
        try:
            if index:
                return pg.runtime.statements.save(pg.actor, uuid4(), created["id"], 1, body)[
                    "status"
                ]
            return pg.runtime.deliveries.void(
                pg.actor, uuid4(), delivery["id"], 1, "Synthetic race"
            )["status"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(run, range(2)))
    assert "void" in result, result
    final = pg.runtime.statements.detail(pg.actor, created["id"])
    assert final["calculation"]["total"] == "0.00"
    assert final["lines"][0]["status"] == "source_void"
