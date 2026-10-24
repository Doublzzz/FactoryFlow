"""Separate source identity fields survive confirmation, revision and old evidence."""

from uuid import uuid4

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.orders.application.service import evidence_content
from factoryflow.modules.orders.domain.order import prepare_order
from test_order_contract import payload
from test_postgres_orders import counts, order_body


def structured_line():
    return {
        "description": "ignored compatibility projection",
        "item_code": "SYN-PART-01",
        "item_name": "Synthetic connector",
        "specification": "Black cable\nL=140mm, 4PIN",
        "quantity": "2",
        "unit": "PCS",
        "source_unit_price": "0.08036",
        "source_amount": "0.99",
    }


def test_separate_fields_and_source_decimals_form_canonical_evidence():
    body = payload()
    body["lines"] = [structured_line()]
    line = evidence_content(prepare_order(body))["lines"][0]
    assert line["item_code"] == "SYN-PART-01"
    assert line["item_name"] == "Synthetic connector"
    assert line["specification"] == "Black cable\nL=140mm, 4PIN"
    assert line["description"] == "SYN-PART-01 Synthetic connector Black cable\nL=140mm, 4PIN"
    assert line["source_unit_price"] == "0.08036"
    assert line["source_amount"] == "0.99"  # Independent original amount, never recomputed.


def test_legacy_evidence_shape_remains_unchanged():
    body = payload()
    original = evidence_content(prepare_order(body))
    for row in body["lines"]:
        row.update(item_code=None, item_name=None, specification=None)
    assert evidence_content(prepare_order(body)) == original
    assert all("item_name" not in row for row in original["lines"])


@pytest.mark.parametrize(
    "field,value", [("item_code", "x" * 101), ("item_name", 2), ("specification", "x" * 1001)]
)
def test_invalid_structured_identity_rejected(field, value):
    body = payload()
    body["lines"] = [structured_line() | {field: value}]
    with pytest.raises(BusinessError, match="INVALID_INPUT"):
        prepare_order(body)


def test_structured_code_and_spec_can_exist_without_invented_name():
    body = payload()
    body["lines"] = [structured_line() | {"item_name": ""}]
    line = evidence_content(prepare_order(body))["lines"][0]
    assert line["item_name"] == ""
    assert line["description"].startswith("SYN-PART-01 Black cable")
    body["lines"] = [structured_line() | {"item_code": "", "item_name": "", "specification": ""}]
    with pytest.raises(BusinessError, match="INVALID_INPUT"):
        prepare_order(body)


def test_postgres_structured_fields_roundtrip_replay_revision_and_immutable_evidence(pg):
    body = order_body(pg, "SYN-STRUCTURED")
    body["lines"] = [structured_line()]
    key = uuid4()
    first = pg.api.command("/api/v1/orders", body, key)
    assert first.status_code == 200, first.text
    assert pg.api.command("/api/v1/orders", body, key).json() == first.json()
    result = first.json()
    evidence_path = f"/api/v1/documents/{result['revision_id']}/download"
    original_bytes = pg.api.request("GET", evidence_path).content
    original = pg.api.request("GET", evidence_path).json()
    assert original["schema_version"] == 3
    detail = pg.api.request("GET", f"/api/v1/orders/{result['order_id']}").json()
    assert detail["lines"][0]["specification"] == structured_line()["specification"]
    assert detail["lines"][0]["item_name"] == "Synthetic connector"
    open_line = pg.api.request("GET", "/api/v1/orders/open-lines").json()["items"][0]
    assert open_line["item_code"] == "SYN-PART-01"
    conflicting = body | {"lines": [structured_line() | {"specification": "Changed"}]}
    assert (
        pg.api.command("/api/v1/orders", conflicting, key).json()["code"] == "IDEMPOTENCY_CONFLICT"
    )
    revised = pg.api.command(
        f"/api/v1/orders/{result['order_id']}/revisions",
        {
            "expected_version": 1,
            "reason": "Synthetic specification correction",
            "order": conflicting,
        },
    )
    assert revised.status_code == 200, revised.text
    assert pg.api.request("GET", evidence_path).content == original_bytes
    updated = pg.api.request("GET", f"/api/v1/orders/{result['order_id']}").json()
    assert updated["lines"][0]["specification"] == "Changed"


def test_structured_confirmation_audit_failure_rolls_back_all_rows(pg, monkeypatch):
    from factoryflow.platform.database import Journal

    original = counts(pg)
    body = order_body(pg, "SYN-STRUCTURED-ROLLBACK")
    body["lines"] = [structured_line()]

    def reject(*_):
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(Journal, "audit", reject)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        pg.runtime.orders.confirm(pg.actor, uuid4(), body)
    assert counts(pg) == original
