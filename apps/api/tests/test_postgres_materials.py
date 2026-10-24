"""Synthetic PostgreSQL: stable identities, customer codes, replay and ownership."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import pytest
from conftest import SYNTHETIC_PASSWORD
from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError


def create_material(pg, **overrides):
    body = {"name": "Synthetic bracket", "specification": "S-1", "unit": "PCS"} | overrides
    result = pg.api.command("/api/v1/materials", body)
    assert result.status_code == 200, result.text
    return result.json()


def test_manual_and_auto_codes_preserve_text_and_retry(pg):
    explicit = create_material(pg, own_code="000128-A")
    assert explicit["own_code"] == "000128-A"
    key = uuid4()
    body = {"name": "Synthetic blank-unit item"}
    created = pg.api.command("/api/v1/materials", body, key)
    assert created.status_code == 200, created.text
    assert created.json()["own_code"].startswith("WL")
    assert created.json()["unit"] is None
    assert pg.api.command("/api/v1/materials", body, key).json() == created.json()
    assert pg.api.command("/api/v1/materials", body | {"name": "Changed"}, key).status_code == 409
    assert len(pg.api.request("GET", "/api/v1/materials").json()["items"]) == 2
    current = created.json()
    update = {
        "name": current["name"],
        "own_code": "000129-B",
        "specification": "S-1",
        "unit": "PCS",
        "active": True,
        "expected_version": 1,
        "reason": "Synthetic fill missing fields",
    }
    filled = pg.api.command(f"/api/v1/materials/{current['id']}", update)
    assert filled.status_code == 200 and filled.json()["id"] == current["id"]
    assert filled.json()["change"]["before"]["unit"] is None
    forbidden = pg.api.command(
        f"/api/v1/materials/{current['id']}", update | {"expected_version": 2, "unit": "KG"}
    )
    assert (
        forbidden.status_code == 409 and forbidden.json()["code"] == "MATERIAL_IDENTITY_IMMUTABLE"
    )
    assert pg.api.command("/api/v1/materials", body, key).json() == current


def test_customer_codes_are_scoped_and_master_correction_is_versioned(pg):
    material = create_material(pg)
    other = pg.api.command("/api/v1/customers", {"full_name": "Synthetic Customer B"}).json()
    for customer_id, code in ((pg.customer_id, "A-017"), (other["id"], "P-903")):
        result = pg.api.command(
            "/api/v1/material-codes",
            {
                "customer_id": customer_id,
                "customer_code": code,
                "material_id": material["id"],
                "expected_material_version": 1,
                "item_name": "Synthetic bracket",
                "specification": "S-1",
                "unit": "PCS",
            },
        )
        assert result.status_code == 200, result.text
    found = pg.api.request("GET", "/api/v1/materials?q=P-903").json()["items"]
    assert [item["id"] for item in found] == [material["id"]]
    assert found[0]["matched_customer_codes"] == [
        {"customer_name": "Synthetic Customer B", "customer_code": "P-903"}
    ]
    changed = pg.api.command(
        f"/api/v1/materials/{material['id']}",
        {
            "expected_version": 1,
            "reason": "Synthetic correction",
            "name": "Synthetic bracket fixed",
            "own_code": material["own_code"],
            "specification": "S-1",
            "unit": "PCS",
            "active": True,
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["version"] == 2
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM customer_material_codes")).scalar_one() == 2


def test_auto_number_skips_thousand_existing_codes_and_concurrent_requests(pg):
    with pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO materials(organization_id,id,own_code,name,created_by,updated_by)
            SELECT :org, gen_random_uuid(), 'WL'||lpad(i::text,6,'0'),
              'Synthetic reserved code',:actor,:actor
            FROM generate_series(1,1000) AS i"""),
            {"org": pg.actor.organization_id, "actor": pg.actor.user_id},
        )
    with ThreadPoolExecutor(max_workers=4) as pool:
        values = list(
            pool.map(
                lambda _: pg.runtime.materials.create(
                    pg.actor, uuid4(), {"name": "Synthetic concurrent"}
                ),
                range(4),
            )
        )
    assert len({v["own_code"] for v in values}) == 4
    assert all(int(v["own_code"][2:]) > 1000 for v in values)
    with pg.owner.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM materials")).scalar_one() == 1004


def test_mapping_concurrent_creation_has_one_winner_and_database_owns_uniqueness(pg):
    materials = [create_material(pg), create_material(pg)]

    def write(material):
        try:
            return pg.runtime.materials.save_code(
                pg.actor,
                uuid4(),
                {
                    "customer_id": pg.customer_id,
                    "customer_code": "SAME",
                    "material_id": material["id"],
                    "expected_material_version": 1,
                    "unit": "PCS",
                },
            )["material_id"]
        except BusinessError as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, materials))
    assert results.count("MATERIAL_MAPPING_CONFLICT") == 1
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO customer_material_codes
            (organization_id,customer_id,customer_code,material_id)
            VALUES(:org,:customer,'SAME',:material)"""),
            {
                "org": pg.actor.organization_id,
                "customer": pg.customer_id,
                "material": materials[0]["id"],
            },
        )


def test_mapping_concurrent_corrections_do_not_overwrite_each_other(pg):
    original, first, second = [create_material(pg) for _ in range(3)]
    operator = pg.runtime.identity.add_user(
        pg.actor, "synthetic-other-operator", SYNTHETIC_PASSWORD, "operator"
    )
    payload = {
        "customer_id": pg.customer_id,
        "customer_code": "SAME",
        "material_id": original["id"],
        "expected_material_version": 1,
        "unit": "PCS",
    }
    pg.runtime.materials.save_code(pg.actor, uuid4(), payload)

    def correct(selection):
        actor, material = selection
        try:
            return pg.runtime.materials.save_code(
                actor,
                uuid4(),
                payload
                | {
                    "material_id": material["id"],
                    "expected_mapping_version": 1,
                    "reason": "Synthetic concurrent correction",
                },
            )["material_id"]
        except BusinessError as failure:
            return failure.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(correct, [(pg.actor, first), (operator, second)]))
    assert results.count("MATERIAL_MAPPING_CONFLICT") == 1
    saved = pg.api.request("GET", f"/api/v1/material-codes?customer_id={pg.customer_id}").json()[
        "items"
    ][0]
    assert saved["version"] == 2 and saved["material_id"] in results


def test_ownership_role_and_foreign_key_protection(pg):
    material = create_material(pg)
    foreign = replace(pg.actor, organization_id=uuid4())
    with pytest.raises(BusinessError, match="MATERIAL_NOT_FOUND"):
        with pg.runtime.materials.transaction() as work:
            work.catalog.require(foreign, material["id"])
    viewer = pg.runtime.identity.add_user(
        pg.actor, "synthetic-viewer", SYNTHETIC_PASSWORD, "viewer"
    )
    with pytest.raises(BusinessError, match="WRITE_FORBIDDEN"):
        pg.runtime.materials.create(viewer, uuid4(), {"name": "Forbidden"})
    with pytest.raises(DBAPIError), pg.owner.begin() as conn:
        conn.execute(
            text("""INSERT INTO customer_material_codes
            (organization_id,customer_id,customer_code,material_id)
            VALUES(:org,:customer,'FOREIGN',:material)"""),
            {"org": uuid4(), "customer": pg.customer_id, "material": material["id"]},
        )


def test_two_operators_corrections_retain_actor_time_and_old_retry_result(pg):
    material = create_material(pg)
    operator = pg.runtime.identity.add_user(
        pg.actor, "synthetic-operator", SYNTHETIC_PASSWORD, "operator"
    )
    payload = {
        "customer_id": pg.customer_id,
        "customer_code": "A-017",
        "material_id": material["id"],
        "expected_material_version": 1,
        "unit": "PCS",
        "item_name": "Synthetic first",
    }
    key = uuid4()
    first = pg.runtime.materials.save_code(pg.actor, key, payload)
    second = pg.runtime.materials.save_code(
        operator,
        uuid4(),
        payload
        | {
            "expected_mapping_version": 1,
            "item_name": "Synthetic corrected",
            "reason": "Customer spelling",
        },
    )
    assert first["change"]["actor_id"] == str(pg.actor.user_id)
    assert second["change"]["actor_id"] == str(operator.user_id)
    assert second["change"]["before"]["version"] == 1 and second["version"] == 2
    assert second["change"]["occurred_at"] and second["change"]["reason"] == "Customer spelling"
    assert pg.runtime.materials.save_code(pg.actor, key, payload) == first


def test_runtime_cannot_rewrite_material_identity_or_order_source(pg):
    material = create_material(pg)
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(
            text("UPDATE materials SET id=:new WHERE id=:old"),
            {"old": material["id"], "new": uuid4()},
        )
    with pytest.raises(DBAPIError), pg.runtime.engine.begin() as conn:
        conn.execute(text("UPDATE order_lines SET item_code='forbidden'"))
