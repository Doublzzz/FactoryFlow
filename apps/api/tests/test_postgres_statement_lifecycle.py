"""Synthetic formal lifecycle: real HTTP, transactions and retained evidence."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from factoryflow.platform.database import Journal
from sqlalchemy import text


def command(pg, path, body, key=None):
    response = pg.api.command(path, body, key)
    assert response.status_code == 200, response.text
    return response.json()


def setup_statement(pg, quantity="100", start="2026-10-01", end="2026-10-31"):
    order = command(
        pg,
        "/api/v1/orders",
        {
            "customer_id": pg.customer_id,
            "order_number": "SYN-LIFE-" + uuid4().hex,
            "business_date": "2026-10-01",
            "currency": "CNY",
            "lines": [
                {
                    "description": "Synthetic lifecycle part",
                    "quantity": quantity,
                    "unit": "PCS",
                    "source_unit_price": "10",
                    "source_amount": None,
                }
            ],
        },
    )
    current = pg.api.request("GET", f"/api/v1/orders/{order['order_id']}").json()
    delivery = command(
        pg,
        "/api/v1/deliveries",
        {
            "order_id": current["id"],
            "customer_id": pg.customer_id,
            "revision_id": current["revision_id"],
            "expected_version": current["version"],
            "delivery_date": "2026-10-01",
            "lines": [{"order_line_id": current["lines"][0]["id"], "quantity": quantity}],
        },
    )
    source = {"delivery_id": delivery["id"], "order_line_id": delivery["lines"][0]["order_line_id"]}
    statement = command(
        pg,
        "/api/v1/statements",
        {
            "customer_id": pg.customer_id,
            "period_start": start,
            "period_end": end,
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "adjustments": [],
            "lines": [{**source, "quantity": quantity, "unit_price": "10", "reason": "Synthetic"}],
        },
    )
    export = command(pg, f"/api/v1/statements/{statement['id']}/exports", {"expected_version": 1})
    ready = pg.api.request("POST", f"/api/v1/statement-exports/{export['id']}/generate")
    assert ready.status_code == 200 and ready.json()["status"] == "ready", ready.text
    sent = command(
        pg,
        f"/api/v1/statements/{statement['id']}/sent",
        {
            "expected_version": 1,
            "export_id": export["id"],
            "person": "Synthetic Sender",
            "occurred_on": "2026-10-02",
            "note": "Synthetic actual send registration",
        },
    )
    feedback = command(
        pg,
        f"/api/v1/statements/{statement['id']}/feedback",
        {
            "person": "Synthetic Customer Contact",
            "occurred_on": "2026-10-03",
            "note": "Synthetic telephone confirmation; quantity and price checked",
        },
    )
    return statement, source, sent, feedback


def detail(pg, identifier):
    response = pg.api.request("GET", f"/api/v1/statements/{identifier}")
    assert response.status_code == 200, response.text
    return response.json()


def approve(pg, statement, source, sent, feedback, quantity="90"):
    return command(
        pg,
        f"/api/v1/statements/{statement['id']}/approve",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            **source,
            "sent_id": sent["id"],
            "feedback_id": feedback["id"],
            "quantity": quantity,
            "unit_price": "10",
            "target_start": "2026-10-01",
            "target_end": "2026-10-31",
            "reason": "Synthetic recognition",
        },
    )


def reserve(pg, statement, approval, quantity):
    return command(
        pg,
        f"/api/v1/statements/{statement['id']}/reserve",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            "approval_id": approval["id"],
            "approval_version": approval["version"],
            "quantity": quantity,
            "reason": "Synthetic settlement selection",
        },
    )


def settle(pg, statement):
    body = {
        "expected_version": detail(pg, statement["id"])["version"],
        "fees_confirmed": True,
        "reconfirmation": "not_required",
        "reason": "Synthetic no outstanding fee; confirmation requirements checked",
    }
    preview = command(pg, f"/api/v1/statements/{statement['id']}/settlement-preview", body)
    assert preview["blockers"] == [], preview
    return command(
        pg,
        f"/api/v1/statements/{statement['id']}/settle",
        body | {"preview_token": preview["token"]},
    )


def blank(pg, start, end):
    return command(
        pg,
        "/api/v1/statements",
        {
            "customer_id": pg.customer_id,
            "period_start": start,
            "period_end": end,
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "lines": [],
            "adjustments": [],
        },
    )


def test_two_period_recognition_review_and_formal_history(pg):
    statement, source, sent, feedback = setup_statement(pg)
    approval = approve(pg, statement, source, sent, feedback)
    review = command(
        pg,
        f"/api/v1/statements/{statement['id']}/review",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            **source,
            "quantity": "10",
            "reason": "Synthetic disputed quantity",
        },
    )
    reserve(pg, statement, approval, "60")
    first = settle(pg, statement)
    assert first["status"] == "confirmed" and first["calculation"]["total"] == "600.00"
    following = blank(pg, "2026-11-01", "2026-11-30")
    target = {
        "expected_version": approval["version"],
        "target_start": "2026-11-01",
        "target_end": "2026-11-30",
        "reason": "Synthetic remaining quantity carried forward",
    }
    preview = command(pg, f"/api/v1/statement-approvals/{approval['id']}/defer-preview", target)
    approval = command(
        pg,
        f"/api/v1/statement-approvals/{approval['id']}/defer",
        target | {"preview_token": preview["token"]},
    )
    reserve(pg, following, approval, "30")
    second = settle(pg, following)
    assert second["calculation"]["total"] == "300.00"
    assert detail(pg, statement["id"]) == first
    with pg.owner.connect() as conn:
        assert conn.execute(
            text("SELECT sum(claimed) FROM statement_balances")
        ).scalar_one() == Decimal(90)
    third = blank(pg, "2026-12-01", "2026-12-31")
    command(
        pg,
        f"/api/v1/statements/{third['id']}/claim-review",
        {
            "expected_version": 1,
            "review_id": review["id"],
            "review_version": review["version"],
            "quantity": "6",
            "unit_price": "10",
            "reason": "Synthetic issue resolved for six",
        },
    )
    assert detail(pg, statement["id"]) == first
    reviews = pg.api.request(
        "GET", "/api/v1/statement-reviews", params={"customer_id": pg.customer_id}
    ).json()
    assert reviews["items"][0]["remaining_quantity"] == "4"


def record_evidence(pg, statement):
    export = command(
        pg,
        f"/api/v1/statements/{statement['id']}/exports",
        {"expected_version": statement["version"]},
    )
    ready = pg.api.request("POST", f"/api/v1/statement-exports/{export['id']}/generate")
    assert ready.status_code == 200 and ready.json()["status"] == "ready", ready.text
    sent = command(
        pg,
        f"/api/v1/statements/{statement['id']}/sent",
        {
            "expected_version": statement["version"],
            "export_id": export["id"],
            "person": "Synthetic Sender",
            "occurred_on": "2026-12-02",
            "note": "Synthetic send",
        },
    )
    feedback = command(
        pg,
        f"/api/v1/statements/{statement['id']}/feedback",
        {
            "person": "Synthetic Contact",
            "occurred_on": "2026-12-03",
            "note": "Synthetic checked",
        },
    )
    return sent, feedback


def test_claimed_review_can_approve_and_settle_or_restore_on_abandon(pg):
    original, source, sent, feedback = setup_statement(pg)
    review = command(
        pg,
        f"/api/v1/statements/{original['id']}/review",
        {
            "expected_version": 1,
            **source,
            "quantity": "100",
            "reason": "Synthetic all disputed",
        },
    )
    target = blank(pg, "2026-12-01", "2026-12-31")
    body = {
        "expected_version": 1,
        "review_id": review["id"],
        "review_version": review["version"],
        "quantity": "6",
        "unit_price": "10",
        "reason": "Synthetic six resolved",
    }
    claimed = command(pg, f"/api/v1/statements/{target['id']}/claim-review", body)
    abandoned = command(
        pg,
        f"/api/v1/statements/{target['id']}/abandon",
        {"expected_version": claimed["version"], "reason": "Synthetic cancel"},
    )
    current_review = pg.api.request(
        "GET", "/api/v1/statement-reviews", params={"customer_id": pg.customer_id}
    ).json()["items"][0]
    assert current_review["remaining_quantity"] == "100" and current_review["version"] > 1
    command(
        pg,
        f"/api/v1/statements/{target['id']}/reopen",
        {
            "customer_id": pg.customer_id,
            "period_start": "2026-12-01",
            "period_end": "2026-12-31",
            "tax_mode": "untaxed_final",
            "tax_rate": "0",
            "lines": [],
            "adjustments": [],
            "reason": "Synthetic reopen",
            "expected_version": abandoned["version"],
        },
    )
    claimed = command(
        pg,
        f"/api/v1/statements/{target['id']}/claim-review",
        body
        | {
            "expected_version": detail(pg, target["id"])["version"],
            "review_version": current_review["version"],
        },
    )
    sent, feedback = record_evidence(pg, claimed)
    approval = command(
        pg,
        f"/api/v1/statements/{target['id']}/approve",
        {
            "expected_version": claimed["version"],
            **source,
            "sent_id": sent["id"],
            "feedback_id": feedback["id"],
            "quantity": "6",
            "unit_price": "10",
            "target_start": "2026-12-01",
            "target_end": "2026-12-31",
            "reason": "Synthetic approved six",
        },
    )
    reserve(pg, target, approval, "6")
    assert settle(pg, target)["calculation"]["total"] == "60.00"
    current_review = pg.api.request(
        "GET", "/api/v1/statement-reviews", params={"customer_id": pg.customer_id}
    ).json()["items"][0]
    assert current_review["remaining_quantity"] == "94"


def test_partial_review_recognition_and_later_decrease_keep_precise_links(pg):
    original, source, _, _ = setup_statement(pg)
    review = command(
        pg,
        f"/api/v1/statements/{original['id']}/review",
        {
            "expected_version": 1,
            **source,
            "quantity": "100",
            "reason": "Synthetic unresolved source",
        },
    )
    target = blank(pg, "2026-11-01", "2026-11-30")
    claimed = command(
        pg,
        f"/api/v1/statements/{target['id']}/claim-review",
        {
            "expected_version": 1,
            "review_id": review["id"],
            "review_version": review["version"],
            "quantity": "6",
            "unit_price": "10",
            "reason": "Synthetic six under review",
        },
    )
    sent, feedback = record_evidence(pg, claimed)
    recognized = []
    for q, price in (("4", "10"), ("2", "12")):
        recognized.append(
            command(
                pg,
                f"/api/v1/statements/{target['id']}/approve",
                {
                    "expected_version": detail(pg, target["id"])["version"],
                    **source,
                    "sent_id": sent["id"],
                    "feedback_id": feedback["id"],
                    "quantity": q,
                    "unit_price": price,
                    "target_start": "2026-11-01",
                    "target_end": "2026-11-30",
                    "reason": "Synthetic separate price recognition",
                },
            )
        )
    before = pg.runtime.statement_lifecycle.view(pg.actor, target["id"])
    assert sorted(
        (row["quantity"], row["approval_id"])
        for row in before["review_transfers"]
        if row["status"] == "approved"
    ) == [("2", recognized[1]["id"]), ("4", recognized[0]["id"])]
    assert any(
        row["quantity"] == "6" and row["status"] == "released" for row in before["review_transfers"]
    )
    assert not any(row["status"] == "claimed" for row in before["review_transfers"])
    correction = {
        "expected_version": recognized[0]["version"],
        "quantity": "3",
        "unit_price": "10",
        "disposition": "review",
        "evidence_id": feedback["id"],
        "cause": "customer_change",
        "reason": "Synthetic one returned to review",
    }
    path = f"/api/v1/statement-approvals/{recognized[0]['id']}/correct"
    preview = command(pg, path + "-preview", correction)
    corrected = command(pg, path, correction | {"preview_token": preview["token"]})
    assert corrected["quantity"] == "3" and corrected["review_quantity"] == "4"
    after = pg.runtime.statement_lifecycle.view(pg.actor, target["id"])
    assert after["review_transfers"] == before["review_transfers"]
    reviews = pg.api.request(
        "GET", "/api/v1/statement-reviews", params={"customer_id": pg.customer_id}
    ).json()["items"]
    assert sorted(Decimal(row["remaining_quantity"]) for row in reviews) == [
        Decimal(1),
        Decimal(94),
    ]
    reserve(pg, target, corrected, "3")
    reserve(pg, target, recognized[1], "2")
    formal = settle(pg, target)
    assert formal["calculation"]["total"] == "54.00"
    assert sorted((row["quantity"], row["unit_price"]) for row in formal["settlement_lines"]) == [
        ("2", "12"),
        ("3", "10"),
    ]


def test_preview_replay_correction_and_late_audit_rollback(pg, monkeypatch):
    statement, source, sent, feedback = setup_statement(pg)
    approval = approve(pg, statement, source, sent, feedback, "100")
    allocation = reserve(pg, statement, approval, "80")
    body = {
        "expected_version": 1,
        "quantity": "70",
        "unit_price": "10",
        "disposition": "review",
        "evidence_id": feedback["id"],
        "cause": "entry_error",
        "reason": "Synthetic correction",
    }
    path = f"/api/v1/statement-approvals/{approval['id']}/correct"
    preview = command(pg, path + "-preview", body)
    assert preview["affected_allocations"][0]["id"] == allocation["id"]
    extra = reserve(pg, statement, approval, "10")
    stale = pg.api.command(path, body | {"preview_token": preview["token"]})
    assert stale.status_code == 409 and stale.json()["code"] == "STATEMENT_PREVIEW_STALE"
    preview = command(pg, path + "-preview", body)
    assert len(preview["affected_allocations"]) == 2
    key = uuid4()
    request = body | {"preview_token": preview["token"]}
    before = detail(pg, statement["id"])
    real = Journal.audit

    def fail(self, actor, action, identifier):
        if action == "statement.correct_approval":
            raise RuntimeError("Synthetic late audit failure")
        return real(self, actor, action, identifier)

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic late audit failure"):
        pg.runtime.statement_lifecycle.change_approval(
            pg.actor, key, approval["id"], "correct_approval", request
        )
    assert detail(pg, statement["id"]) == before
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM statement_reviews")).scalar_one() == 0
        assert (
            conn.execute(
                text("SELECT count(*) FROM command_results WHERE idempotency_key=:key"),
                {"key": key},
            ).scalar_one()
            == 0
        )
    monkeypatch.setattr(Journal, "audit", real)
    corrected = command(pg, path, request, key)
    assert corrected["quantity"] == "70" and corrected["reserved_quantity"] == "0"
    assert command(pg, path, request, key) == corrected
    assert (
        pg.api.command(path, request | {"quantity": "69"}, key).json()["code"]
        == "IDEMPOTENCY_CONFLICT"
    )
    assert pg.api.command(path, request).json()["code"] == "VERSION_CONFLICT"
    assert extra["quantity"] == "10"
    candidates = pg.api.request(
        "GET",
        "/api/v1/statement-candidates",
        params={
            "customer_id": pg.customer_id,
            "period_start": "2026-11-01",
            "period_end": "2026-11-30",
        },
    ).json()
    assert candidates["items"][0]["available_quantity"] == "0"
    reserve(pg, statement, corrected, "60")
    assert settle(pg, statement)["calculation"]["total"] == "600.00"


def test_formal_simple_correction_keeps_old_event_and_explicit_quantity_destination(pg):
    statement, source, sent, feedback = setup_statement(pg)
    approval = approve(pg, statement, source, sent, feedback, "100")
    allocation = reserve(pg, statement, approval, "100")
    first = settle(pg, statement)
    body = {
        "expected_version": first["version"],
        "allocation_id": allocation["id"],
        "quantity": "90",
        "unit_price": "10",
        "disposition": "review",
        "evidence_id": feedback["id"],
        "cause": "entry_error",
        "no_downstream_effects": True,
        "reason": "Synthetic evidence proves ninety",
    }
    preview = command(pg, f"/api/v1/statements/{statement['id']}/correction-preview", body)
    assert preview["blockers"] == []
    revised = command(
        pg,
        f"/api/v1/statements/{statement['id']}/correct",
        body | {"preview_token": preview["token"]},
    )
    assert preview["calculation"]["total"] == "900.00"
    assert revised["correction"]["evidence_id"] == feedback["id"]
    assert revised["calculation"]["total"] == "900.00"
    assert revised["history"][-2]["snapshot"]["calculation"]["total"] == "1000.00"
    assert len(revised["settlement_lines"]) == 1
    with pg.owner.connect() as conn:
        rows = conn.execute(
            text("SELECT status,sum(quantity) FROM statement_allocations GROUP BY status")
        ).all()
        assert dict(rows) == {"settled": Decimal(90), "superseded": Decimal(100)}
        assert conn.execute(text("SELECT claimed FROM statement_balances")).scalar_one() == Decimal(
            90
        )
        assert conn.execute(text("SELECT quantity FROM statement_reviews")).scalar_one() == Decimal(
            10
        )


def test_send_required_unknowns_block_final_and_source_void_is_atomic(pg):
    statement, source, sent, feedback = setup_statement(pg)
    body = {
        "expected_version": 1,
        "fees_confirmed": False,
        "reconfirmation": "unknown",
        "reason": "Synthetic",
    }
    preview = command(pg, f"/api/v1/statements/{statement['id']}/settlement-preview", body)
    assert {
        "STATEMENT_UNAPPROVED_QUANTITY",
        "STATEMENT_FEES_UNKNOWN",
        "STATEMENT_RECONFIRMATION_UNKNOWN",
    } <= set(preview["blockers"])
    approval = approve(pg, statement, source, sent, feedback, "100")
    before = pg.runtime.deliveries.detail(pg.actor, source["delivery_id"])
    response = pg.api.command(
        f"/api/v1/deliveries/{source['delivery_id']}/void",
        {"expected_version": 1, "reason": "Synthetic protected source"},
    )
    assert response.json()["code"] == "STATEMENT_APPROVED_SOURCE_PROTECTED"
    assert pg.runtime.deliveries.detail(pg.actor, source["delivery_id"]) == before
    with pg.owner.connect() as conn:
        assert conn.execute(
            text("SELECT delivered_quantity FROM order_lines")
        ).scalar_one() == Decimal(100)
    reserve(pg, statement, approval, "100")
    final = settle(pg, statement)
    repeat = pg.api.command(
        f"/api/v1/statements/{statement['id']}/settle",
        {
            **body,
            "expected_version": final["version"],
            "preview_token": "a" * 64,
            "fees_confirmed": True,
            "reconfirmation": "not_required",
        },
    )
    assert repeat.json()["code"] == "STATEMENT_STATE_CONFLICT"


def save_payload(statement, *, lines=None):
    return {
        k: statement[k]
        for k in (
            "customer_id",
            "period_start",
            "period_end",
            "tax_mode",
            "tax_rate",
            "adjustments",
        )
    } | {
        "expected_version": statement["version"],
        "reason": "Synthetic draft change",
        "lines": [
            {
                k: line[k]
                for k in ("delivery_id", "order_line_id", "quantity", "unit_price", "reason")
            }
            for line in (statement["lines"] if lines is None else lines)
            if line["status"] in ("included", "deferred")
        ],
    }


def test_formal_correction_cannot_confirm_negative_total(pg):
    statement, source, sent, feedback = setup_statement(pg)
    body = save_payload(statement) | {
        "adjustments": [
            {
                "stage": "after_tax",
                "kind": "Synthetic fixed fee",
                "amount": "-900",
                "reason": "Synthetic known deduction",
            }
        ]
    }
    command(pg, f"/api/v1/statements/{statement['id']}/save", body)
    approval = approve(pg, statement, source, sent, feedback, "100")
    allocation = reserve(pg, statement, approval, "100")
    first = settle(pg, statement)
    assert first["calculation"]["total"] == "100.00"
    correction = {
        "expected_version": first["version"],
        "allocation_id": allocation["id"],
        "quantity": "10",
        "unit_price": "10",
        "disposition": "review",
        "evidence_id": feedback["id"],
        "cause": "entry_error",
        "no_downstream_effects": True,
        "reason": "Synthetic cannot become negative",
    }
    preview = command(pg, f"/api/v1/statements/{statement['id']}/correction-preview", correction)
    assert "STATEMENT_AMOUNT_UNCONFIRMED" in preview["blockers"]
    result = pg.api.command(
        f"/api/v1/statements/{statement['id']}/correct",
        correction | {"preview_token": preview["token"]},
    )
    assert result.status_code == 409 and detail(pg, statement["id"]) == first


def test_linked_adjustment_can_be_reviewed_after_recognition_release_and_reserve(pg):
    statement, source, sent, feedback = setup_statement(pg)
    command(
        pg,
        f"/api/v1/statements/{statement['id']}/save",
        save_payload(statement)
        | {
            "adjustments": [
                {
                    **source,
                    "stage": "after_tax",
                    "kind": "Synthetic freight",
                    "amount": "-20",
                    "reason": "Synthetic known freight",
                }
            ]
        },
    )
    approval = approve(pg, statement, source, sent, feedback, "100")
    allocation = reserve(pg, statement, approval, "100")
    command(
        pg,
        f"/api/v1/statements/{statement['id']}/release",
        {
            "expected_version": detail(pg, statement["id"])["version"],
            "allocation_id": allocation["id"],
            "allocation_version": 1,
            "reason": "Synthetic recheck",
        },
    )
    reserve(pg, statement, approval, "100")
    current = detail(pg, statement["id"])
    request = save_payload(current, lines=[])
    request["adjustments"] = [
        {k: v for k, v in x.items() if k != "status"} for x in request["adjustments"]
    ]
    command(pg, f"/api/v1/statements/{statement['id']}/save", request)
    assert settle(pg, statement)["calculation"]["total"] == "980.00"


def test_concurrent_review_claims_use_remaining_and_version(pg):
    statement, source, sent, feedback = setup_statement(pg)
    review = command(
        pg,
        f"/api/v1/statements/{statement['id']}/review",
        {"expected_version": 1, **source, "quantity": "100", "reason": "Synthetic review"},
    )
    targets = [blank(pg, "2026-11-01", "2026-11-30"), blank(pg, "2026-12-01", "2026-12-31")]
    barrier = Barrier(2)

    def attempt(target):
        from factoryflow.kernel.contracts import BusinessError

        barrier.wait()
        try:
            return pg.runtime.statement_lifecycle.command(
                pg.actor,
                uuid4(),
                target["id"],
                "claim_review",
                {
                    "expected_version": 1,
                    "review_id": review["id"],
                    "review_version": review["version"],
                    "quantity": "60",
                    "unit_price": "10",
                    "reason": "Synthetic concurrent claim",
                },
            )["status"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, targets)) == ["VERSION_CONFLICT", "draft"]
    with pg.owner.connect() as conn:
        assert conn.execute(
            text("SELECT sum(quantity) FROM statement_review_transfers WHERE status='claimed'")
        ).scalar_one() == Decimal(60)


def test_approval_and_draft_save_compete_on_same_version(pg):
    statement, source, sent, feedback = setup_statement(pg)
    body = {
        "expected_version": 1,
        **source,
        "sent_id": sent["id"],
        "feedback_id": feedback["id"],
        "quantity": "100",
        "unit_price": "10",
        "target_start": "2026-10-01",
        "target_end": "2026-10-31",
        "reason": "Synthetic simultaneous approval",
    }
    barrier = Barrier(2)

    def attempt(action):
        from factoryflow.kernel.contracts import BusinessError

        barrier.wait()
        try:
            if action == "approve":
                pg.runtime.statement_lifecycle.command(
                    pg.actor, uuid4(), statement["id"], action, body
                )
            else:
                pg.runtime.statements.save(
                    pg.actor, uuid4(), statement["id"], 1, save_payload(statement)
                )
            return "ok"
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, ["approve", "save"])) == ["VERSION_CONFLICT", "ok"]
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT claimed FROM statement_balances")).scalar_one() == Decimal(
            100
        )


@pytest.mark.parametrize("action", ["approve", "settle", "defer", "claim_review"])
def test_lifecycle_journal_failure_rolls_back_every_effect(pg, monkeypatch, action):
    statement, source, sent, feedback = setup_statement(pg)
    body = {
        "expected_version": 1,
        **source,
        "sent_id": sent["id"],
        "feedback_id": feedback["id"],
        "quantity": "100",
        "unit_price": "10",
        "target_start": "2026-10-01",
        "target_end": "2026-10-31",
        "reason": "Synthetic rollback proof",
    }
    identifier = statement["id"]
    if action == "claim_review":
        review = command(
            pg,
            f"/api/v1/statements/{statement['id']}/review",
            {"expected_version": 1, **source, "quantity": "100", "reason": "Synthetic review"},
        )
        target = blank(pg, "2026-11-01", "2026-11-30")
        identifier = target["id"]
        body = {
            "expected_version": 1,
            "review_id": review["id"],
            "review_version": review["version"],
            "quantity": "6",
            "unit_price": "10",
            "reason": "Synthetic rollback proof",
        }
    elif action in ("settle", "defer"):
        approval = approve(pg, statement, source, sent, feedback, "100")
        reserve(pg, statement, approval, "80")
        if action == "settle":
            body = {
                "expected_version": detail(pg, identifier)["version"],
                "fees_confirmed": True,
                "reconfirmation": "not_required",
                "reason": "Synthetic rollback proof",
            }
            preview = command(pg, f"/api/v1/statements/{identifier}/settlement-preview", body)
        else:
            identifier = approval["id"]
            body = {
                "expected_version": 1,
                "target_start": "2026-11-01",
                "target_end": "2026-11-30",
                "reason": "Synthetic rollback proof",
            }
            preview = command(pg, f"/api/v1/statement-approvals/{identifier}/defer-preview", body)
        body["preview_token"] = preview["token"]
    tables = (
        "statements",
        "statement_lines",
        "statement_balances",
        "statement_approvals",
        "statement_allocations",
        "statement_reviews",
        "statement_review_transfers",
        "statement_events",
        "statement_lifecycle_events",
        "audit_events",
        "command_results",
    )

    def snapshot():
        with pg.owner.connect() as conn:
            return {
                table: conn.execute(
                    text(
                        "SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]') "
                        f"FROM {table} t"
                    )
                ).scalar_one()
                for table in tables
            }

    before = snapshot()
    real = Journal.audit

    def fail(self, actor, command_type, entity):
        if command_type == "statement." + action:
            raise RuntimeError("Synthetic audit rollback")
        return real(self, actor, command_type, entity)

    monkeypatch.setattr(Journal, "audit", fail)
    with pytest.raises(RuntimeError, match="Synthetic audit rollback"):
        if action == "defer":
            pg.runtime.statement_lifecycle.change_approval(
                pg.actor, uuid4(), identifier, action, body
            )
        else:
            pg.runtime.statement_lifecycle.command(pg.actor, uuid4(), identifier, action, body)
    assert snapshot() == before
