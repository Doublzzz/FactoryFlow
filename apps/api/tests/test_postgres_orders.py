"""Catch partial commits, duplicate effects, ownership leaks and mutable confirmation evidence."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import UUID, uuid4, uuid7

import httpx
import pytest
from conftest import API, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import create_app
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.platform.config import Settings
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_order_contract import payload


def order_body(pg, number="SYN-ORDER-001"):
    result = payload()
    result.update(customer_id=pg.customer_id, order_number=number)
    return result


def confirm(pg, **kwargs):
    response = pg.api.command("/api/v1/orders", order_body(pg, **kwargs))
    assert response.status_code == 200, response.text
    return response.json()


def counts(pg):
    with pg.owner.connect() as conn:
        return tuple(
            conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            for table in (
                "orders",
                "order_lines",
                "confirmed_revisions",
                "order_events",
                "command_results",
                "audit_events",
            )
        )


def test_confirmed_order_survives_new_service_and_returns_exact_evidence(pg):
    result = confirm(pg)
    replacement = create_app(settings=pg.settings)
    try:
        client = API(replacement)
        client.cookies = pg.api.cookies
        detail = client.request("GET", f"/api/v1/orders/{result['order_id']}").json()
        assert [line["quantity"] for line in detail["lines"]] == ["1.125", "2"]
        assert detail["lines"][1]["source_quantity_text"] == "2.000"
        assert detail["lines"][0]["source_unit_price"] is None
        evidence = client.request("GET", f"/api/v1/documents/{result['revision_id']}/download")
        assert evidence.status_code == 200
        assert hashlib.sha256(evidence.content).hexdigest() == result["sha256"]
        body = evidence.json()
        assert body["order"]["lines"][0]["source_amount"] == "99.00"
        assert body["order"]["lines"][1]["source_quantity_text"] == "2.000"
        assert body["schema_version"] == 1
    finally:
        replacement.state.services.close()


def test_retry_replays_and_same_key_changed_source_conflicts_without_effect(pg):
    key = uuid4()
    body = order_body(pg)
    first = pg.api.command("/api/v1/orders", body, key)
    assert first.status_code == 200
    snapshot = counts(pg)
    second = pg.api.command("/api/v1/orders", body, key)
    assert second.json() == first.json()
    body["lines"][1]["quantity"] = "2"
    conflict = pg.api.command("/api/v1/orders", body, key)
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "IDEMPOTENCY_CONFLICT"
    assert counts(pg) == snapshot


def test_duplicate_number_is_reserved_even_after_soft_delete_and_restore_keeps_id(pg):
    first = confirm(pg)
    key = uuid4()
    request = {"expected_version": 1, "reason": "Synthetic correction"}
    deleted = pg.api.command(f"/api/v1/orders/{first['order_id']}/delete", request, key)
    assert deleted.status_code == 200
    assert deleted.json()["version"] == 2
    assert (
        pg.api.command(f"/api/v1/orders/{first['order_id']}/delete", request, key).json()
        == deleted.json()
    )
    assert pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"] == []
    duplicate = pg.api.command("/api/v1/orders", order_body(pg))
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "ORDER_NUMBER_EXISTS"
    restored = pg.api.command(
        f"/api/v1/orders/{first['order_id']}/restore",
        {"expected_version": 2, "reason": "Synthetic restored"},
    )
    assert restored.status_code == 200
    assert restored.json()["order_id"] == first["order_id"]
    assert restored.json()["version"] == 3
    assert len(pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"]) == 2


def test_revision_is_new_evidence_with_parent_and_stale_write_is_rejected(pg):
    first = confirm(pg)
    old_path = pg.objects / (first["sha256"] + ".json")
    old_bytes = old_path.read_bytes()
    body = order_body(pg)
    body["lines"][0]["quantity"] = "1.250"
    result = pg.api.command(
        f"/api/v1/orders/{first['order_id']}/revisions",
        {"order": body, "expected_version": 1, "reason": "Synthetic revision"},
    )
    assert result.status_code == 200, result.text
    revised = result.json()
    assert revised["revision_id"] != first["revision_id"]
    assert revised["revision_number"] == 2
    assert old_path.read_bytes() == old_bytes
    new_doc = pg.api.request("GET", f"/api/v1/documents/{revised['revision_id']}").json()
    assert new_doc["content"]["parent_revision_id"] == first["revision_id"]
    stale = pg.api.command(
        f"/api/v1/orders/{first['order_id']}/delete",
        {"expected_version": 1, "reason": "Synthetic stale"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "VERSION_CONFLICT"
    lines = pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"]
    assert [line["remaining_quantity"] for line in lines] == ["1.25", "2"]
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM order_lines")).scalar_one() == 4


def test_customer_is_explicit_and_unknown_unit_warning_roundtrips(pg):
    body = order_body(pg)
    body["customer_id"] = str(uuid4())
    rejected = pg.api.command("/api/v1/orders", body)
    assert rejected.status_code == 404
    assert counts(pg)[0] == 0
    body["customer_id"] = pg.customer_id
    body["lines"][0]["unit"] = ""
    result = pg.api.command("/api/v1/orders", body)
    assert result.status_code == 200
    lines = pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"]
    assert lines[0]["quantity_policy"]["warning_codes"] == ["UNIT_PRECISION_UNCONFIRMED"]


@pytest.mark.parametrize("phase", ["object", "line", "audit"])
def test_confirmation_failures_leave_no_committed_half_order(pg, phase):
    before = counts(pg)
    client = pg.api
    alternate = None
    if phase == "object":
        settings = Settings(pg.settings.database_url, pg.objects / "absent")
        alternate = create_app(settings=settings)
        client = API(alternate)
        client.cookies, client.csrf = pg.api.cookies, pg.api.csrf
    else:
        table = "order_lines" if phase == "line" else "audit_events"
        condition = "NEW.line_number=2" if phase == "line" else "NEW.command_type='order.confirm'"
        with pg.owner.begin() as conn:
            conn.execute(
                text(f"""CREATE FUNCTION inject_test_failure() RETURNS trigger
                LANGUAGE plpgsql AS $$
                BEGIN IF {condition} THEN RAISE EXCEPTION 'synthetic failure'; END IF;
                RETURN NEW; END; $$;
                CREATE TRIGGER test_failure BEFORE INSERT ON {table}
                FOR EACH ROW EXECUTE FUNCTION inject_test_failure();""")
            )
    try:
        response = client.command("/api/v1/orders", order_body(pg))
        assert response.status_code == 503, response.text
        assert counts(pg) == before
        assert "synthetic failure" not in response.text
        if phase != "object":
            files = list(pg.objects.glob("*.json"))
            assert len(files) == 1  # unpublished orphan retained, not an order
            revision_id = json.loads(files[0].read_bytes())["revision_id"]
            assert pg.api.request("GET", f"/api/v1/documents/{revision_id}").status_code == 404
    finally:
        if alternate:
            alternate.state.services.close()


def test_two_connections_replay_one_command(pg):
    barrier = Barrier(2)
    key = uuid4()

    def write():
        barrier.wait(timeout=10)
        return pg.runtime.orders.confirm(pg.actor, key, order_body(pg))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert results[0] == results[1]
    assert counts(pg)[:4] == (1, 2, 1, 1)
    with pg.owner.connect() as conn:
        assert (
            conn.execute(
                text("SELECT count(*) FROM audit_events WHERE command_type='order.confirm'")
            ).scalar_one()
            == 1
        )


def test_database_unique_constraint_arbitrates_distinct_commands_for_same_order(pg):
    barrier = Barrier(2)

    def write():
        barrier.wait(timeout=10)
        try:
            pg.runtime.orders.confirm(pg.actor, uuid4(), order_body(pg))
            return "created"
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: write(), range(2)))
    assert sorted(results) == ["ORDER_NUMBER_EXISTS", "created"]
    assert counts(pg)[:4] == (1, 2, 1, 1)


@pytest.mark.parametrize(
    "quantity", ["1.2345", "1.0000", "NaN", "Infinity", "-1", "9223372036854775.808"]
)
def test_database_rejects_invalid_numeric_without_rounding(pg, quantity):
    confirm(pg)
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("UPDATE order_lines SET quantity=CAST(:quantity AS numeric) WHERE line_number=1"),
            {"quantity": quantity},
        )
    assert (
        pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"][0]["quantity"] == "1.125"
    )


@pytest.mark.parametrize(
    "table,column",
    [
        ("confirmed_revisions", "blob_hash"),
        ("order_events", "reason"),
        ("audit_events", "command_type"),
        ("command_results", "command_type"),
    ],
)
def test_database_rejects_evidence_overwrite_even_by_owner(pg, table, column):
    confirm(pg)
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(text(f"UPDATE {table} SET {column}={column}"))
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))


def test_changed_file_is_detected_instead_of_served_as_valid_evidence(pg):
    result = confirm(pg)
    (pg.objects / (result["sha256"] + ".json")).write_bytes(b"synthetic corruption")
    response = pg.api.request("GET", f"/api/v1/documents/{result['revision_id']}")
    assert response.status_code == 503
    assert response.json()["code"] == "EVIDENCE_INTEGRITY_FAILED"


def test_active_delivery_blocks_revision_and_delete(pg):
    result = confirm(pg)
    detail = pg.api.request("GET", f"/api/v1/orders/{result['order_id']}").json()
    delivery = pg.api.command(
        "/api/v1/deliveries",
        {
            "order_id": result["order_id"],
            "customer_id": pg.customer_id,
            "revision_id": result["revision_id"],
            "expected_version": 1,
            "delivery_date": "2026-10-01",
            "lines": [{"order_line_id": detail["lines"][0]["id"], "quantity": "1"}],
        },
    )
    assert delivery.status_code == 200

    for suffix, body in [
        ("delete", {"expected_version": 2, "reason": "Synthetic blocked"}),
        (
            "revisions",
            {"expected_version": 2, "reason": "Synthetic blocked", "order": order_body(pg)},
        ),
    ]:
        response = pg.api.command(f"/api/v1/orders/{result['order_id']}/{suffix}", body)
        assert response.status_code == 409
        assert response.json()["code"] == "ACTIVE_DELIVERY_BLOCKS_CHANGE"


def test_cursor_has_stable_no_duplicate_pages_and_is_not_an_unbounded_offset(pg):
    confirm(pg, number="SYN-ORDER-A")
    confirm(pg, number="SYN-ORDER-B")
    seen = []
    cursor = None
    for _ in range(4):
        params = {"limit": 1, "customer_id": pg.customer_id}
        if cursor:
            params["cursor"] = cursor
        response = pg.api.request("GET", "/api/v1/orders/open-lines", params=params)
        assert response.status_code == 200
        page = response.json()
        seen.extend((line["order_number"], line["line_number"]) for line in page["items"])
        cursor = page["next_cursor"]
    assert seen == [("SYN-ORDER-B", 1), ("SYN-ORDER-B", 2), ("SYN-ORDER-A", 1), ("SYN-ORDER-A", 2)]
    assert cursor is None
    assert (
        pg.api.request("GET", "/api/v1/orders/open-lines", params={"cursor": "bad"}).status_code
        == 422
    )


def test_foreign_organization_is_hidden_and_database_blocks_cross_ownership(pg):
    result = confirm(pg)
    foreign = Actor(uuid7(), uuid7(), "synthetic-other", "operator")
    with pg.owner.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations(id,name) VALUES (:id,'Synthetic Other Factory')"),
            {"id": foreign.organization_id},
        )
        conn.execute(
            text(
                "INSERT INTO users(id,organization_id,username,password_hash,role) "
                "VALUES (:id,:org,:username,'unused','operator')"
            ),
            {"id": foreign.user_id, "org": foreign.organization_id, "username": foreign.username},
        )
    for operation in [
        lambda: pg.runtime.orders.detail(foreign, UUID(result["order_id"])),
        lambda: pg.runtime.orders.evidence(foreign, UUID(result["revision_id"])),
        lambda: pg.runtime.orders.confirm(foreign, uuid4(), order_body(pg)),
    ]:
        with pytest.raises(BusinessError) as error:
            operation()
        assert error.value.status == 404
    assert pg.runtime.orders.open_lines(foreign)["items"] == []
    foreign_customer = pg.runtime.customers.create(foreign, uuid4(), "Synthetic Other Customer")
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("UPDATE orders SET customer_id=:foreign WHERE id=:id"),
            {"foreign": foreign_customer["id"], "id": result["order_id"]},
        )


def test_local_sessions_authorization_csrf_and_revocation(pg):
    anonymous = API(pg.app)
    assert anonymous.request("GET", "/api/v1/customers").status_code == 401
    viewer = pg.runtime.identity.add_user(
        pg.actor, "synthetic-viewer", SYNTHETIC_PASSWORD, "viewer"
    )
    assert viewer.role == "viewer"
    client = API(pg.app)
    login = client.login("synthetic-viewer")
    cookie = login.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/api/v1" in cookie
    assert client.request("GET", "/api/v1/customers").status_code == 200
    assert client.command("/api/v1/orders", order_body(pg)).status_code == 403
    missing_csrf = pg.api.request(
        "POST",
        "/api/v1/customers",
        json={"full_name": "Synthetic Untrusted"},
        headers={"x-csrf-token": "", "Idempotency-Key": str(uuid4())},
    )
    assert missing_csrf.status_code == 403
    assert (
        pg.api.request(
            "POST",
            "/api/v1/auth/login",
            json={"username": "synthetic-admin", "password": SYNTHETIC_PASSWORD},
            headers={"Origin": "https://external.invalid"},
        ).status_code
        == 403
    )
    old_cookies = httpx.Cookies(client.cookies)
    assert client.request("POST", "/api/v1/auth/logout").status_code == 204
    client.cookies = old_cookies
    assert client.request("GET", "/api/v1/customers").status_code == 401


def test_wrong_password_lockout_and_expired_sessions_do_not_authenticate(pg):
    client = API(pg.app)
    for _ in range(5):
        assert (
            client.request(
                "POST",
                "/api/v1/auth/login",
                json={"username": "synthetic-admin", "password": "Synthetic-wrong-password"},
            ).status_code
            == 401
        )
    assert (
        client.request(
            "POST",
            "/api/v1/auth/login",
            json={"username": "synthetic-admin", "password": SYNTHETIC_PASSWORD},
        ).status_code
        == 401
    )
    with pg.owner.begin() as conn:
        conn.execute(text("UPDATE sessions SET expires_at=now()-interval '1 second'"))
    assert pg.api.request("GET", "/api/v1/customers").status_code == 401


def test_runtime_role_cannot_change_schema_or_immutable_rows(pg):
    result = confirm(pg)
    for statement in [
        "CREATE TABLE forbidden(id integer)",
        "DELETE FROM confirmed_revisions",
        "UPDATE confirmed_revisions SET blob_hash=blob_hash",
        "UPDATE order_lines SET quantity=0",
    ]:
        with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
            conn.execute(text(statement))
    assert pg.api.request("GET", f"/api/v1/documents/{result['revision_id']}").status_code == 200


def test_preview_is_read_only_and_exposes_unknown_unit_before_confirmation(pg):
    before = counts(pg)
    body = order_body(pg)
    body["lines"][0]["unit"] = "unknown"
    response = pg.api.request("POST", "/api/v1/orders/preview", json=body)
    assert response.status_code == 200
    assert response.json()["order"]["lines"][0]["quantity_policy"]["warning_codes"] == [
        "UNIT_PRECISION_UNCONFIRMED"
    ]
    assert counts(pg) == before
    assert not list(pg.objects.glob("*.json"))


def test_outdated_schema_fails_closed_without_automatic_migration(pg):
    with pg.owner.begin() as conn:
        conn.execute(text("UPDATE alembic_version SET version_num='0001_local_orders'"))
    for method, path, kwargs in [
        ("GET", "/api/v1/health/ready", {}),
        ("GET", "/api/v1/customers", {}),
        ("POST", "/api/v1/orders", {"json": order_body(pg)}),
    ]:
        response = pg.api.request(method, path, **kwargs)
        assert response.status_code == 503
        assert response.json()["code"] == "SCHEMA_MISMATCH"
    assert pg.api.request("GET", "/api/v1/health/live").status_code == 200
    with pg.owner.connect() as conn:
        assert (
            conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_local_orders"
        )
