"""Read-only discovery and committed confirmation receipts, on disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import uuid4, uuid7

import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import Actor
from factoryflow.platform.database import Journal
from sqlalchemy import text
from test_postgres_orders import counts, order_body


def viewer(pg):
    pg.runtime.identity.add_user(pg.actor, "synthetic-query-viewer", SYNTHETIC_PASSWORD, "viewer")
    client = API(pg.app)
    client.login("synthetic-query-viewer")
    return client


def lookup(client, customer_id, number):
    return client.request(
        "GET",
        "/api/v1/orders/lookup",
        params={"customer_id": customer_id, "order_number": number},
    )


def receipt(client, key):
    return client.request("GET", f"/api/v1/orders/confirmations/{key}")


def foreign_actor(pg):
    actor = Actor(uuid7(), uuid7(), "synthetic-query-foreign", "operator")
    with pg.owner.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations(id,name) VALUES (:id,'Synthetic Query Factory')"),
            {"id": actor.organization_id},
        )
        conn.execute(
            text(
                "INSERT INTO users(id,organization_id,username,password_hash,role) "
                "VALUES (:id,:org,:username,'unused','operator')"
            ),
            {"id": actor.user_id, "org": actor.organization_id, "username": actor.username},
        )
    return actor


def test_customer_search_reaches_beyond_legacy_cap_and_pages_multiple_candidates(pg):
    # The old list's first 1000 names must not hide an exact match later in the catalog.
    with pg.owner.begin() as conn:
        conn.execute(
            text("INSERT INTO customers(id,organization_id,full_name) VALUES (:id,:org,:name)"),
            [
                {"id": uuid7(), "org": pg.actor.organization_id, "name": f"AAA SYN {i:04}"}
                for i in range(1001)
            ],
        )
    first = pg.runtime.customers.create(pg.actor, uuid4(), "ZZ 合成客户 FindMe")
    second = pg.runtime.customers.create(pg.actor, uuid4(), "ZZ 合成客户 FindMe Branch")
    client = viewer(pg)
    before = counts(pg)
    query = {"name": "  合成客户 findme  ", "limit": 1}
    page = client.request("GET", "/api/v1/customers/search", params=query)
    assert page.status_code == 200, page.text
    assert page.json()["items"] == [first]
    assert page.json()["next_cursor"] == first["id"]
    query["cursor"] = page.json()["next_cursor"]
    page2 = client.request("GET", "/api/v1/customers/search", params=query)
    assert page2.json() == {"items": [second], "next_cursor": None}
    assert counts(pg) == before


def test_customer_search_treats_wildcards_as_literal_and_hides_other_org(pg):
    found = pg.runtime.customers.create(pg.actor, uuid4(), "SYN 50%_O'Reilly")
    pg.runtime.customers.create(pg.actor, uuid4(), "SYN 50xAO'Reilly")
    foreign = foreign_actor(pg)
    pg.runtime.customers.create(foreign, uuid4(), "SYN 50%_O'Reilly Foreign")
    response = viewer(pg).request("GET", "/api/v1/customers/search", params={"name": "%_O'"})
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [found], "next_cursor": None}


@pytest.mark.parametrize("name,query", [("SYN ÉCOLE", "école"), ("SYN Straße", "STRASSE")])
def test_customer_search_preserves_unicode_caseless_matching(pg, name, query):
    found = pg.runtime.customers.create(pg.actor, uuid4(), name)
    response = viewer(pg).request("GET", "/api/v1/customers/search", params={"name": query})
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [found], "next_cursor": None}


@pytest.mark.parametrize(
    "params", [{"name": " "}, {"name": "SYN", "limit": 0}, {"name": "SYN", "cursor": "bad"}]
)
def test_customer_search_rejects_invalid_query(pg, params):
    response = pg.api.request("GET", "/api/v1/customers/search", params=params)
    assert response.status_code == 422


def test_exact_lookup_requires_customer_and_includes_fully_delivered_order(pg):
    body = order_body(pg, "SYN-SAME-NUMBER")
    first = pg.api.command("/api/v1/orders", body).json()
    second_customer = pg.runtime.customers.create(pg.actor, uuid4(), "Synthetic Second Customer")
    second_body = {**body, "customer_id": second_customer["id"]}
    second = pg.api.command("/api/v1/orders", second_body).json()
    detail = pg.api.request("GET", f"/api/v1/orders/{first['order_id']}").json()
    delivered = pg.api.command(
        "/api/v1/deliveries",
        {
            "order_id": first["order_id"],
            "customer_id": pg.customer_id,
            "revision_id": first["revision_id"],
            "expected_version": 1,
            "delivery_date": "2026-10-01",
            "lines": [
                {"order_line_id": detail["lines"][0]["id"], "quantity": "1.125"},
                {"order_line_id": detail["lines"][1]["id"], "quantity": "2"},
            ],
        },
    )
    assert delivered.status_code == 200, delivered.text
    client = viewer(pg)
    before = counts(pg)
    response = lookup(client, pg.customer_id, " SYN-SAME-NUMBER ")
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["id"] == first["order_id"]
    assert [line["remaining_quantity"] for line in order["lines"]] == ["0", "0"]
    assert order["lines"][0]["source_amount"] == "99.00"
    assert order["lines"][1]["source_unit_price"] == "0"
    assert order["lines"][1]["source_quantity_text"] == "2.000"
    assert (
        lookup(client, second_customer["id"], "SYN-SAME-NUMBER").json()["id"] == second["order_id"]
    )
    assert lookup(client, pg.customer_id, "SYN-SAME").status_code == 404
    assert lookup(client, uuid4(), "SYN-SAME-NUMBER").status_code == 404
    assert counts(pg) == before


def test_confirmation_receipt_survives_revision_and_soft_delete_without_rewriting_history(pg):
    key = uuid4()
    body = order_body(pg)
    original = pg.api.command("/api/v1/orders", body, key).json()
    body["lines"][0]["quantity"] = "1.250"
    revised = pg.api.command(
        f"/api/v1/orders/{original['order_id']}/revisions",
        {"order": body, "expected_version": 1, "reason": "Synthetic revision"},
    )
    assert revised.status_code == 200
    deleted = pg.api.command(
        f"/api/v1/orders/{original['order_id']}/delete",
        {"expected_version": 2, "reason": "Synthetic deletion"},
    )
    assert deleted.status_code == 200
    client = viewer(pg)
    before = counts(pg)
    result = receipt(client, key)
    assert result.status_code == 200, result.text
    assert result.json()["idempotency_key"] == str(key)
    assert result.json()["outcome"] == "confirmed"
    assert result.json()["command_result"] == original
    current = lookup(client, pg.customer_id, body["order_number"]).json()
    assert current["status"] == "deleted" and current["version"] == 3
    assert current["revision_id"] == revised.json()["revision_id"]
    assert len(current["revisions"]) == 2
    assert counts(pg) == before


def test_confirmation_unknown_does_not_replay_or_find_another_command_or_organization(pg):
    key = uuid4()
    original = pg.api.command("/api/v1/orders", order_body(pg), key).json()
    foreign = foreign_actor(pg)
    foreign_customer = pg.runtime.customers.create(foreign, uuid4(), "Foreign SYN Customer")
    foreign_result = pg.runtime.orders.confirm(
        foreign, key, {**order_body(pg), "customer_id": foreign_customer["id"]}
    )
    foreign_key = uuid4()
    pg.runtime.orders.confirm(
        foreign,
        foreign_key,
        {**order_body(pg, "SYN-FOREIGN"), "customer_id": foreign_customer["id"]},
    )
    customer_key = uuid4()
    pg.runtime.customers.create(pg.actor, customer_key, "SYN Other Command")
    client = viewer(pg)
    before = counts(pg)
    assert receipt(client, key).json()["command_result"] == original
    for absent in [uuid4(), foreign_key, customer_key]:
        response = receipt(client, absent)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "idempotency_key": str(absent),
            "outcome": "unknown",
            "command_result": None,
        }
    assert lookup(client, foreign_customer["id"], "SYN-ORDER-001").status_code == 404
    assert client.request("GET", f"/api/v1/orders/{foreign_result['order_id']}").status_code == 404
    assert counts(pg) == before


def test_confirmation_is_unknown_until_transaction_commit_then_same_key_replays(pg, monkeypatch):
    key = uuid4()
    staged, release = Event(), Event()
    finish = Journal.finish

    def hold(self, actor, command, token, result):
        finish(self, actor, command, token, result)
        if command == "order.confirm" and token == key:
            staged.set()
            assert release.wait(10)

    monkeypatch.setattr(Journal, "finish", hold)
    client = viewer(pg)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(pg.runtime.orders.confirm, pg.actor, key, order_body(pg))
        try:
            assert staged.wait(10)
            response = receipt(client, key)
            assert response.status_code == 200, response.text
            assert response.json()["outcome"] == "unknown"
            assert response.json()["command_result"] is None
        finally:
            release.set()
        result = pending.result(timeout=10)
    assert receipt(client, key).json()["command_result"]["order_id"] == result["order_id"]
    before = counts(pg)
    replay = pg.api.command("/api/v1/orders", order_body(pg), key)
    assert replay.json()["order_id"] == result["order_id"]
    assert counts(pg) == before


def test_rolled_back_confirmation_has_no_receipt(pg, monkeypatch):
    key = uuid4()
    finish = Journal.finish

    def fail_after_journal(self, actor, command, token, result):
        finish(self, actor, command, token, result)
        if command == "order.confirm":
            raise RuntimeError("Synthetic transaction interruption")

    monkeypatch.setattr(Journal, "finish", fail_after_journal)
    with pytest.raises(RuntimeError, match="Synthetic transaction"):
        pg.runtime.orders.confirm(pg.actor, key, order_body(pg))
    before = counts(pg)
    response = receipt(pg.api, key)
    assert response.status_code == 200, response.text
    assert response.json()["outcome"] == "unknown"
    assert counts(pg) == before and before[0] == 0


def test_new_queries_require_authentication_and_viewer_cannot_confirm(pg):
    client = API(pg.app)
    assert (
        client.request("GET", "/api/v1/customers/search", params={"name": "SYN"}).status_code == 401
    )
    assert lookup(client, pg.customer_id, "SYN").status_code == 401
    assert receipt(client, uuid4()).status_code == 401
    assert viewer(pg).command("/api/v1/orders", order_body(pg)).status_code == 403


def test_order_lookup_rejects_blank_missing_or_malformed_identity(pg):
    assert lookup(pg.api, pg.customer_id, " ").status_code == 422
    assert lookup(pg.api, "../other", "SYN").status_code == 422
    assert (
        pg.api.request("GET", "/api/v1/orders/lookup", params={"order_number": "SYN"}).status_code
        == 422
    )
    assert receipt(pg.api, "not-a-uuid").status_code == 422
