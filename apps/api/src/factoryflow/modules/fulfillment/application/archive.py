"""Read-only delivery work-file snapshots on the caller's supplied transaction."""

import json
from copy import deepcopy
from hashlib import sha256
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.fulfillment.domain.print_layout import default_layout


class ArchiveDeliveries:
    def __init__(self, repository, layouts, sources, renderer):
        self.repository = repository
        self.layouts = layouts
        self.sources = sources
        self.renderer = renderer

    @staticmethod
    def identifier(key):
        try:
            kind, value = key.split(":", 1)
            if kind != "delivery":
                raise ValueError
            return UUID(value)
        except ValueError, AttributeError:
            raise BusinessError("ARCHIVE_SOURCE_INVALID", 422) from None

    def catalog(self, actor, cursor: str | None, limit: int):
        if type(limit) is not int or not 1 <= limit <= 50:
            raise BusinessError("INVALID_INPUT", 422, "limit")
        if cursor is not None:
            try:
                cursor = str(UUID(cursor))
            except ValueError, TypeError, AttributeError:
                raise BusinessError("INVALID_CURSOR", 422, "cursor") from None
        page = self.repository.list(actor, None, cursor, limit, None)
        return {
            "items": [self.describe(actor, f"delivery:{row['id']}") for row in page["items"]],
            "next_cursor": page["next_cursor"],
        }

    def snapshot(self, actor, key):
        delivery = deepcopy(self.repository.get(actor, self.identifier(key)))
        saved = self.layouts.current(actor) or {"version": 0, "config": default_layout()}
        references = {
            (delivery["order_id"], delivery["revision_id"], line["order_line_id"])
            for line in delivery["lines"]
        }
        sources = self.sources.read(actor, references)
        for line in delivery["lines"]:
            source = sources[(delivery["order_id"], delivery["revision_id"], line["order_line_id"])]
            for field in ("item_code", "item_name", "specification"):
                line[field] = source.get(field)
        return delivery, saved

    @staticmethod
    def metadata(delivery, saved):
        metadata = {
            "key": f"delivery:{delivery['id']}",
            "kind": "delivery",
            "source_id": delivery["id"],
            "title": delivery["order_number"],
            "customer_id": delivery["customer_id"],
            "customer_name": delivery["customer_name"],
            "business_date": delivery["delivery_date"],
            "period_end": None,
            "version_label": f"送货 v{delivery['version']} · 模板 v{saved['version']}",
            "state_label": "已作废" if delivery["status"] == "void" else "有效",
            "extension": "html",
            "current": True,
            "available": True,
            "byte_size": None,
        }
        # Currentity is a source query, independent of rendering code or file availability.
        # Preview separately includes exact output hashes before any batch is created.
        token_input = {"delivery": delivery, "layout": saved}
        metadata["token"] = sha256(
            json.dumps(
                token_input, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        return metadata

    def capture(self, actor, key) -> tuple[dict, bytes]:
        delivery, saved = self.snapshot(actor, key)
        metadata = self.metadata(delivery, saved)
        content = self.renderer(delivery, saved["config"], saved["version"])
        return {**metadata, "byte_size": len(content)}, content

    def describe(self, actor, key) -> dict:
        return self.metadata(*self.snapshot(actor, key))
