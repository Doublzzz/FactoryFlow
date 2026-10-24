"""Original uploaded bytes with only human-confirmed order classification."""

import base64
import hashlib
import json
from typing import TYPE_CHECKING
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError

if TYPE_CHECKING:
    from factoryflow.modules.orders.public import ArchiveOrders


class ArchiveDocuments:
    def __init__(self, repository, store, orders: ArchiveOrders):
        self.repository, self.store, self.orders = repository, store, orders

    @staticmethod
    def identifier(key):
        try:
            prefix, identifier = key.split(":", 1)
            if prefix != "source":
                raise ValueError
            return UUID(identifier)
        except ValueError, AttributeError:
            raise BusinessError("INVALID_INPUT", field="key") from None

    def metadata(self, actor, row):
        order = self.orders.describe(actor, str(row["order_id"])) if row["order_id"] else {}
        extension = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}
        if row["media_type"] not in extension:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        metadata = {
            "key": f"source:{row['id']}",
            "kind": "source",
            "source_id": str(row["id"]),
            "title": row["filename"],
            "customer_id": order.get("customer_id"),
            "customer_name": order.get("customer_name"),
            "business_date": order.get("business_date"),
            "period_end": None,
            "version_label": order.get("version_label", "未确认"),
            "state_label": order.get("state_label", "待归类"),
            "extension": extension[row["media_type"]],
            "current": True,
            "available": True,
            "byte_size": row["byte_size"],
        }
        metadata["token"] = hashlib.sha256(
            json.dumps(
                {"metadata": metadata, "file_hash": row["original_sha256"], "order": order},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return metadata

    def catalog(self, actor, cursor: str | None, limit: int) -> dict:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise BusinessError("INVALID_INPUT", field="limit")
        if cursor is not None:
            try:
                cursor = str(UUID(cursor))
            except ValueError, TypeError, AttributeError:
                raise BusinessError("INVALID_CURSOR", field="cursor") from None
        rows = self.repository.listing(actor, cursor, limit + 1)
        return {
            "items": [self.metadata(actor, row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }

    def describe(self, actor, key: str) -> dict:
        return self.metadata(actor, self.repository.get(actor, self.identifier(key)))

    def capture(self, actor, key: str) -> tuple[dict, bytes]:
        row = self.repository.get(actor, self.identifier(key))
        try:
            envelope = json.loads(self.store.read(row["blob_hash"]))
            content = base64.b64decode(envelope["base64"], validate=True)
            digest = hashlib.sha256(content).hexdigest()
            if (
                envelope["format"] != "source-file-v1"
                or envelope["media_type"] != row["media_type"]
                or envelope["original_sha256"] != row["original_sha256"]
                or digest != row["original_sha256"]
                or len(content) != row["byte_size"]
            ):
                raise ValueError
        except KeyError, ValueError, TypeError:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None
        return self.metadata(actor, row), content
