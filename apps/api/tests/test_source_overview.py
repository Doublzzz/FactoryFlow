"""Current extraction state is a read projection, not an upload replay mutation."""

from uuid import UUID, uuid4

import pytest
from factoryflow.kernel.contracts import Actor, BusinessError
from test_postgres_extraction import PNG, extracted
from test_postgres_orders import order_body


def test_source_overview_reports_latest_failure_and_ready_without_new_runs(pg, monkeypatch):
    source = pg.runtime.extraction.upload(
        pg.actor, uuid4(), "synthetic-state.png", "image/png", PNG
    )
    path = "/api/v1/sources/" + source["source_id"]
    before = pg.api.request("GET", path)
    assert before.status_code == 200, before.text
    assert before.json()["extraction_id"] is None
    assert before.json()["extraction_status"] is None
    monkeypatch.setattr(
        pg.runtime.extraction.extractor,
        "extract",
        lambda *_: {
            "status": "failed",
            "error_code": "PDF_PAGE_LIMIT",
            "pages": [],
            "engine": "synthetic-test",
        },
    )
    failed = pg.runtime.extraction.extract(pg.actor, uuid4(), UUID(source["source_id"]))
    assert pg.api.request("GET", path).json()["extraction_status"] == "failed"
    assert (
        pg.api.request("GET", "/api/v1/sources").json()["items"][0]["extraction_status"] == "failed"
    )
    monkeypatch.setattr(
        pg.runtime.extraction.extractor,
        "extract",
        lambda *_: {"status": "ready", "error_code": None, "pages": [], "engine": "synthetic-test"},
    )
    ready = pg.runtime.extraction.extract(pg.actor, uuid4(), UUID(source["source_id"]))
    assert ready["extraction_id"] != failed["extraction_id"]
    after = pg.api.request("GET", path).json()
    assert after["extraction_status"] == "ready"
    assert after["extraction_id"] == ready["extraction_id"]


def test_confirmed_source_overview_and_old_upload_replay_remain_distinct(pg, monkeypatch):
    key = uuid4()
    uploaded = pg.runtime.extraction.upload(pg.actor, key, "synthetic.png", "image/png", PNG)
    source, run = extracted(pg, monkeypatch)
    assert uploaded["source_id"] == source["source_id"]
    created = pg.api.command(
        "/api/v1/orders",
        order_body(pg, "SYN-SOURCE-STATE") | {"extraction_id": run["extraction_id"]},
    )
    assert created.status_code == 200, created.text
    overview = pg.api.request("GET", "/api/v1/sources/" + source["source_id"])
    assert overview.status_code == 200, overview.text
    assert overview.json()["order_id"] == created.json()["order_id"]
    assert overview.json()["extraction_id"] == run["extraction_id"]
    assert (
        pg.runtime.extraction.upload(pg.actor, key, "synthetic.png", "image/png", PNG) == uploaded
    )


def test_source_overview_is_scoped_to_organization_and_requires_login(pg):
    source = pg.runtime.extraction.upload(pg.actor, uuid4(), "synthetic.png", "image/png", PNG)
    stranger = Actor(uuid4(), uuid4(), "synthetic-other", "admin")
    with pytest.raises(BusinessError, match="SOURCE_NOT_FOUND"):
        pg.runtime.extraction.summary(stranger, UUID(source["source_id"]))
    path = "/api/v1/sources/" + source["source_id"]
    assert pg.api.request("GET", "/api/v1/sources/" + str(uuid4())).status_code == 404
    pg.api.cookies.clear()
    assert pg.api.request("GET", path).status_code == 401
