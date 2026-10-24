from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from conftest import API, ROOT, SYNTHETIC_PASSWORD
from factoryflow.bootstrap import build_services
from factoryflow.kernel.contracts import Actor, BusinessError
from factoryflow.modules.fulfillment.domain.print_layout import default_layout
from factoryflow.platform.backup import restore_backup
from factoryflow.platform.config import Settings
from factoryflow.platform.database import Journal
from psycopg import sql
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from test_postgres_deliveries import delivery_body

PATH = "/api/v1/delivery-layout"


def save(pg, expected=0, config=None, key=None):
    return pg.api.command(
        PATH, {"expected_version": expected, "config": config or default_layout()}, key
    )


def test_layout_save_replay_conflict_and_versions_are_immutable(pg):
    initial = pg.api.request("GET", PATH).json()
    assert initial["version"] == 0 and initial["config"]["paper_width_mm"] == 243
    config = initial["config"] | {"company_name": "Synthetic layout factory"}
    key = uuid4()
    first = save(pg, config=config, key=key)
    assert first.status_code == 200, first.text
    assert save(pg, config=config, key=key).json() == first.json()
    assert save(pg, config=config).status_code == 409
    assert save(pg, config=config | {"phone": "Synthetic"}, key=key).status_code == 409
    second = save(pg, 1)
    assert second.status_code == 200 and second.json()["version"] == 2
    assert second.json()["config"] == default_layout()
    with pg.owner.connect() as conn:
        rows = conn.execute(
            text("SELECT version,config FROM delivery_layout_versions ORDER BY version")
        ).all()
        assert [r.version for r in rows] == [1, 2]
        assert rows[0].config == config
    for query in (
        "UPDATE delivery_layout_versions SET config=config",
        "DELETE FROM delivery_layout_versions",
    ):
        with pytest.raises(DBAPIError), pg.owner.begin() as conn:
            conn.execute(text(query))


def test_layout_authorization_organization_scope_and_validation(pg):
    assert API(pg.app).request("GET", PATH).status_code == 401
    pg.runtime.identity.add_user(pg.actor, "synthetic-layout-viewer", SYNTHETIC_PASSWORD, "viewer")
    viewer = API(pg.app)
    viewer.login("synthetic-layout-viewer")
    assert viewer.request("GET", PATH).status_code == 200
    body = {"expected_version": 0, "config": default_layout()}
    assert viewer.command(PATH, body).status_code == 403
    assert (
        pg.api.request(
            "POST",
            PATH,
            json=body,
            headers={"X-CSRF-Token": "wrong", "Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )
    assert save(pg, config=default_layout() | {"paper_width_mm": 100}).status_code == 422
    assert save(pg, config=default_layout() | {"title": "   "}).status_code == 422
    assert save(pg, config=default_layout() | {"quantity": "999"}).status_code == 422
    assert save(pg, config=default_layout() | {"row_height_mm": 8.5}).status_code == 422
    config = default_layout() | {"company_name": "Synthetic org A"}
    assert save(pg, config=config).status_code == 200
    # The product intentionally provisions only one factory. A foreign tenant here
    # is a test-only ownership fixture, not a second product initialization.
    other = Actor(uuid4(), uuid4(), "synthetic-other-layout", "operator")
    with pg.owner.begin() as conn:
        conn.execute(
            text("INSERT INTO organizations(id,name) VALUES(:id,'Synthetic other')"),
            {"id": other.organization_id},
        )
        conn.execute(
            text(
                "INSERT INTO users(id,organization_id,username,password_hash,role) "
                "VALUES(:id,:org,:name,'synthetic-unused','operator')"
            ),
            {"id": other.user_id, "org": other.organization_id, "name": other.username},
        )
    assert pg.runtime.delivery_layouts.get(other)["version"] == 0
    pg.runtime.delivery_layouts.save(
        other, uuid4(), 0, default_layout() | {"company_name": "Synthetic org B"}
    )
    assert pg.runtime.delivery_layouts.get(pg.actor)["config"] == config


def test_layout_concurrent_saves_have_one_winner(pg):
    barrier = Barrier(2)

    def submit(name):
        barrier.wait(timeout=5)
        try:
            return pg.runtime.delivery_layouts.save(
                pg.actor, uuid4(), 0, default_layout() | {"company_name": name}
            )["version"]
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, ["Synthetic A", "Synthetic B"]))
    assert sorted(results, key=str) == [1, "VERSION_CONFLICT"]
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM delivery_layout_versions")).scalar_one() == 1


def test_layout_late_audit_failure_rolls_back_version_and_journal(pg, monkeypatch):
    original = Journal.audit

    def fail(*args):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(Journal, "audit", fail)
    key = uuid4()
    with pytest.raises(RuntimeError, match="Synthetic"):
        pg.runtime.delivery_layouts.save(pg.actor, key, 0, default_layout())
    assert pg.runtime.delivery_layouts.get(pg.actor)["version"] == 0
    monkeypatch.setattr(Journal, "audit", original)
    assert pg.runtime.delivery_layouts.save(pg.actor, key, 0, default_layout())["version"] == 1


def test_layout_preview_is_read_only_and_print_uses_saved_configuration(pg):
    body = delivery_body(pg)
    created = pg.api.command("/api/v1/deliveries", body).json()
    before = pg.runtime.orders.detail(pg.actor, body["order_id"])
    config = default_layout() | {
        "company_name": "Synthetic <script>never</script>",
        "title": "Synthetic preview",
    }
    response = pg.api.request(
        "POST", PATH + "/preview", json={"delivery_id": created["id"], "config": config}
    )
    assert response.status_code == 200, response.text
    assert "&lt;script&gt;never&lt;/script&gt;" in response.text
    assert "<script>never</script>" not in response.text
    assert created["id"] in response.text and body["revision_id"] in response.text
    assert "frame-ancestors 'self'" == response.headers["Content-Security-Policy"]
    assert pg.runtime.delivery_layouts.get(pg.actor)["version"] == 0
    assert save(pg, config=config).status_code == 200
    printed = pg.api.request("GET", f"/api/v1/deliveries/{created['id']}/print")
    assert "Synthetic preview" in printed.text and "v1" in printed.text
    assert pg.runtime.orders.detail(pg.actor, body["order_id"]) == before
    foreign = Actor(uuid4(), uuid4(), "synthetic-foreign", "viewer")
    with pytest.raises(BusinessError) as failure:
        pg.runtime.delivery_layouts.printable(foreign, created["id"], config)
    assert failure.value.status == 404


def test_print_locale_only_translates_defaults_and_system_labels(pg):
    body = delivery_body(pg)
    delivery = pg.api.command("/api/v1/deliveries", body).json()
    before = pg.runtime.orders.detail(pg.actor, body["order_id"])
    initial = pg.api.request("GET", PATH + "?locale=en").json()
    assert initial["version"] == 0
    assert initial["config"]["title"] == "Delivery note"
    assert pg.runtime.delivery_layouts.get(pg.actor)["config"] == default_layout()
    printed = pg.api.request("GET", f"/api/v1/deliveries/{delivery['id']}/print?locale=en")
    assert printed.status_code == 200
    assert '<html lang="en">' in printed.text and "Delivery note" in printed.text
    # Even a label identical to the Chinese built-in label is user-owned once saved.
    config = default_layout() | {"company_name": "合成客户抬头"}
    assert save(pg, config=config).status_code == 200
    saved = pg.api.request("GET", PATH + "?locale=en").json()
    assert saved["config"] == config
    assert saved["defaults"]["title"] == "Delivery note"
    preview = pg.api.request(
        "POST",
        PATH + "/preview",
        json={"delivery_id": delivery["id"], "config": config, "locale": "en"},
    )
    assert preview.status_code == 200
    assert "合成客户抬头" in preview.text and config["title"] in preview.text
    assert '<html lang="en">' in preview.text
    assert pg.api.request("GET", PATH + "?locale=fr").status_code == 422
    assert (
        pg.api.request("GET", f"/api/v1/deliveries/{delivery['id']}/print?locale=fr").status_code
        == 422
    )
    assert (
        pg.api.request(
            "POST",
            PATH + "/preview",
            json={"delivery_id": delivery["id"], "config": config, "locale": "fr"},
        ).status_code
        == 422
    )
    assert pg.runtime.orders.detail(pg.actor, body["order_id"]) == before


def test_layout_versions_survive_backup_restore(pg, tmp_path):
    body = delivery_body(pg)
    created = pg.api.command("/api/v1/deliveries", body).json()
    assert save(pg).status_code == 200
    config = default_layout() | {"company_name": "Synthetic restored template"}
    assert save(pg, 1, config).status_code == 200
    backup = tmp_path / "layout-backup"
    binary = ROOT / ".tools/postgresql-18.6-4/pgsql/bin"
    pg.runtime.backup(backup, binary)
    target_name = "ff_layout_restore_" + uuid4().hex
    target = None
    admin = pg.admin_url.set(drivername="postgresql", database="postgres")
    try:
        restore_backup(admin, target_name, tmp_path / "restored", backup, binary, ROOT)
        target = build_services(
            Settings(
                pg.admin_url.set(database=target_name).render_as_string(hide_password=False),
                tmp_path / "restored",
            )
        )
        restored = target.delivery_layouts.get(pg.actor)
        assert restored["version"] == 2 and restored["config"] == config
        assert target.deliveries.detail(pg.actor, created["id"]) == created
        with target.engine.connect() as conn:
            assert (
                conn.execute(text("SELECT count(*) FROM delivery_layout_versions")).scalar_one()
                == 2
            )
        assert target.delivery_layouts.save(pg.actor, uuid4(), 2, default_layout())["version"] == 3
    finally:
        if target:
            target.close()
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            assert target_name.startswith("ff_layout_restore_")
            conn.execute(
                sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                    sql.Identifier(target_name)
                )
            )
