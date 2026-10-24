"""Catch overwritten or silently repaired evidence and import-time resource creation."""

import hashlib

import pytest
from factoryflow.bootstrap import create_app
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.adapters.local_store import LocalEvidenceStore
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://example.invalid/factoryflow",
        "postgresql+psycopg://127.0.0.1/factoryflow?host=example.invalid",
        "postgresql+psycopg:///factoryflow",
    ],
)
def test_database_configuration_cannot_escape_local_loopback(url):
    with pytest.raises(ValueError, match="loopback"):
        engine_for(url)


def test_non_ascii_csrf_is_rejected_without_transport_error(monkeypatch):
    from types import SimpleNamespace

    from factoryflow.platform import http

    identity = SimpleNamespace(authenticate=lambda token: (object(), "synthetic-csrf"))
    monkeypatch.setattr(http, "services", lambda request: SimpleNamespace(identity=identity))
    with pytest.raises(BusinessError) as error:
        http.require_actor(SimpleNamespace(method="POST"), "synthetic-session", "é")
    assert error.value.code == "CSRF_REQUIRED"


def test_evidence_duplicate_is_verified_without_replacing_existing_bytes(tmp_path):
    store = LocalEvidenceStore(tmp_path)
    body = b'{"synthetic":true}\n'
    digest = store.put(body)
    assert digest == hashlib.sha256(body).hexdigest()
    path = tmp_path / f"{digest}.json"
    original = path.stat().st_mtime_ns
    assert store.put(body) == digest
    assert path.stat().st_mtime_ns == original
    assert store.read(digest) == body
    assert not list(tmp_path.glob("staging-*"))


def test_corrupted_evidence_is_rejected_not_overwritten(tmp_path):
    store = LocalEvidenceStore(tmp_path)
    body = b'{"synthetic":true}\n'
    digest = store.put(body)
    path = tmp_path / f"{digest}.json"
    path.write_bytes(b"synthetic corruption")
    with pytest.raises(BusinessError) as error:
        store.put(body)
    assert error.value.code == "EVIDENCE_INTEGRITY_FAILED"
    assert path.read_bytes() == b"synthetic corruption"
    assert not list(tmp_path.glob("staging-*"))


def test_app_construction_does_not_connect_or_create_object_directories(tmp_path):
    root = tmp_path / "not-created"
    app = create_app(settings=Settings("postgresql+psycopg://127.0.0.1:1/not-running", root))
    assert app.openapi()["info"]["title"] == "FactoryFlow API"
    assert not root.exists()
    app.state.services.close()
