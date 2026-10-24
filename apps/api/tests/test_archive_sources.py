import base64
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.public import ArchiveDocuments
from factoryflow.modules.orders.public import ArchiveOrders
from factoryflow.modules.statements.public import ArchiveStatements

ID = UUID(int=1)
ACTOR = SimpleNamespace(organization_id=ID)


class Store:
    def __init__(self, envelope):
        self.envelope = json.dumps(envelope).encode()

    def read(self, digest):
        return self.envelope


def source_setup():
    content = b"synthetic original"
    digest = hashlib.sha256(content).hexdigest()
    row = {
        "id": ID,
        "filename": "test.png",
        "media_type": "image/png",
        "byte_size": len(content),
        "original_sha256": digest,
        "blob_hash": "blob",
        "order_id": None,
    }
    repository = SimpleNamespace(
        get=lambda actor, identifier: row, listing=lambda actor, cursor, limit: [row]
    )
    store = Store(
        {
            "format": "source-file-v1",
            "media_type": "image/png",
            "original_sha256": digest,
            "base64": base64.b64encode(content).decode(),
        }
    )
    return ArchiveDocuments(repository, store, None), row, store, content


def test_unconfirmed_source_preserves_bytes_and_unknown_classification():
    facade, _, _, content = source_setup()
    metadata, captured = facade.capture(ACTOR, f"source:{ID}")
    assert captured == content
    assert metadata["customer_id"] is None
    assert metadata["business_date"] is None
    assert metadata["state_label"] == "待归类"
    assert facade.catalog(ACTOR, None, 50)["next_cursor"] is None


@pytest.mark.parametrize(
    "field,value", [("format", "wrong"), ("original_sha256", "wrong"), ("base64", "!")]
)
def test_source_rejects_corrupt_envelope(field, value):
    facade, _, store, _ = source_setup()
    envelope = json.loads(store.envelope)
    envelope[field] = value
    store.envelope = json.dumps(envelope).encode()
    with pytest.raises(BusinessError, match="EVIDENCE_INTEGRITY_FAILED"):
        facade.capture(ACTOR, f"source:{ID}")


def test_order_description_ignores_delivery_version_but_tracks_revision_status_and_name():
    row = {
        "id": str(ID),
        "customer_id": str(ID),
        "order_number": "synthetic",
        "business_date": "2026-10-01",
        "revision_id": str(ID),
        "status": "active",
        "version": 1,
    }
    customer = {"full_name": "合成客户"}
    facade = ArchiveOrders(
        SimpleNamespace(get=lambda actor, identifier: row),
        SimpleNamespace(require=lambda actor, identifier: customer),
    )
    original = facade.describe(ACTOR, str(ID))
    row["version"] += 1
    assert facade.describe(ACTOR, str(ID)) == original
    row["revision_id"] = str(UUID(int=2))
    assert facade.describe(ACTOR, str(ID)) != original
    row["revision_id"] = str(ID)
    customer["full_name"] = "合成新名"
    assert facade.describe(ACTOR, str(ID)) != original


def export_setup():
    content = b"synthetic workbook"
    digest = hashlib.sha256(content).hexdigest()
    row = {
        "id": str(ID),
        "statement_version": 2,
        "template_id": "standard-v1",
        "template_version": 1,
        "status": "ready",
        "current": False,
        "file_hash": digest,
        "object_hash": "blob",
        "snapshot": {
            "statement": {
                "customer_id": str(ID),
                "customer_name": "合成客户",
                "period_start": "2026-09-01",
                "period_end": "2026-10-01",
            }
        },
    }
    repo = SimpleNamespace(
        get=lambda actor, key: row, listing=lambda actor, cursor, limit: [f"statement_export:{ID}"]
    )
    store = Store(
        {
            "type": "statement-xlsx-v1",
            "sha256": digest,
            "content": base64.b64encode(content).decode(),
        }
    )
    return ArchiveStatements(repo, store), row, store, content


def test_historical_export_capture_preserves_snapshot_and_bytes():
    facade, _, _, content = export_setup()
    metadata, captured = facade.capture(ACTOR, f"statement_export:{ID}")
    assert captured == content
    assert metadata["current"] is False
    assert metadata["business_date"] == "2026-09-01"
    assert metadata["period_end"] == "2026-10-01"
    assert metadata["byte_size"] == len(content)


def test_export_rejects_envelope_hash_mismatch():
    facade, _, store, _ = export_setup()
    envelope = json.loads(store.envelope)
    envelope["sha256"] = "wrong"
    store.envelope = json.dumps(envelope).encode()
    with pytest.raises(BusinessError, match="EVIDENCE_INTEGRITY_FAILED"):
        facade.capture(ACTOR, f"statement_export:{ID}")


def test_unexported_statement_is_explicit_unavailable_and_cannot_capture():
    facade, row, _, _ = export_setup()
    row.clear()
    row.update(
        id=str(ID),
        customer_id=str(ID),
        customer_name="合成客户",
        period_start="2026-10-01",
        period_end="2026-10-31",
        version=1,
        status="draft",
    )
    metadata = facade.describe(ACTOR, f"statement_pending:{ID}")
    assert metadata["available"] is False
    assert metadata["state_label"] == "未生成"
    with pytest.raises(BusinessError, match="STATEMENT_EXPORT_NOT_READY"):
        facade.capture(ACTOR, f"statement_pending:{ID}")


@pytest.mark.parametrize("limit", [0, 51, True])
def test_catalog_limit_is_bounded(limit):
    facade, _, _, _ = source_setup()
    with pytest.raises(BusinessError, match="INVALID_INPUT"):
        facade.catalog(ACTOR, None, limit)


def test_source_catalog_exposes_more_without_returning_more_than_requested():
    facade, row, _, _ = source_setup()
    facade.repository.listing = lambda actor, cursor, limit: [
        row | {"id": UUID(int=3)},
        row | {"id": UUID(int=2)},
        row,
    ]
    page = facade.catalog(ACTOR, None, 2)
    assert len(page["items"]) == 2
    assert page["next_cursor"] == str(UUID(int=2))


@pytest.mark.parametrize("status", ["pending", "failed"])
def test_unready_exports_are_listed_but_capture_is_forbidden(status):
    facade, row, _, _ = export_setup()
    row["status"] = status
    metadata = facade.catalog(ACTOR, None, 50)["items"][0]
    assert metadata["available"] is False
    assert metadata["byte_size"] == 0
    with pytest.raises(BusinessError, match="STATEMENT_EXPORT_NOT_READY"):
        facade.capture(ACTOR, f"statement_export:{ID}")
