"""Fixed draft Excel or formal materials, with immutable evidence references."""

import base64
import hashlib
import json
from io import BytesIO
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from factoryflow.kernel.contracts import BusinessError

MAX_BYTES = 50 * 1024 * 1024


class ArchiveStatements:
    def __init__(self, repository, store):
        self.repository, self.store = repository, store

    @staticmethod
    def validate_key(key):
        try:
            prefix, identifier = key.split(":", 1)
            if prefix not in {"statement_export", "statement_pending"}:
                raise ValueError
            return f"{prefix}:{UUID(identifier)}"
        except ValueError, AttributeError:
            raise BusinessError("INVALID_INPUT", field="key") from None

    @staticmethod
    def date_text(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    def metadata(self, key, row, content=None):
        pending = key.startswith("statement_pending:")
        statement = row if pending else row["snapshot"]["statement"]
        formal = statement.get("status", "draft") == "confirmed"
        available = not pending and row["status"] == "ready"
        metadata = {
            "key": key,
            "kind": "statement_export",
            "source_id": str(row["id"]),
            "title": "正式对账资料包" if formal else "对账 Excel",
            "customer_id": str(statement["customer_id"]),
            "customer_name": statement["customer_name"],
            "business_date": self.date_text(statement["period_start"]),
            "period_end": self.date_text(statement["period_end"]),
            "version_label": f"{'正式对账' if formal else '对账'} "
            f"v{row['version'] if pending else row['statement_version']}",
            "state_label": "未生成"
            if pending
            else {
                "pending": "生成中",
                "failed": "生成失败",
                "ready": "已生成",
            }[row["status"]],
            "extension": "zip" if formal else "xlsx",
            "current": row["status"] in {"draft", "confirmed"} if pending else row["current"],
            "available": available,
            "byte_size": len(content) if content is not None else (None if available else 0),
        }
        fingerprint = {
            "metadata": {k: v for k, v in metadata.items() if k != "byte_size"},
            "file_hash": None if pending else row["file_hash"],
            "statement_status": row["status"] if pending else None,
            "template_id": None if pending else row["template_id"],
            "template_version": None if pending else row["template_version"],
        }
        metadata["token"] = hashlib.sha256(
            json.dumps(
                fingerprint,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        return metadata

    def content(self, row):
        try:
            envelope = json.loads(self.store.read(row["object_hash"]))
            content = base64.b64decode(envelope["content"], validate=True)
            if (
                envelope["type"] != "statement-xlsx-v1"
                or envelope["sha256"] != row["file_hash"]
                or hashlib.sha256(content).hexdigest() != row["file_hash"]
            ):
                raise ValueError
        except KeyError, ValueError, TypeError:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None
        return content

    def describe(self, actor, key: str) -> dict:
        key = self.validate_key(key)
        row = self.repository.get(actor, key)
        content = None
        if (
            not key.startswith("statement_pending:")
            and row["status"] == "ready"
            and row["snapshot"]["statement"].get("status") == "confirmed"
        ):
            content = self.formal_package(actor, row)
        return self.metadata(key, row, content)

    def formal_package(self, actor, row):
        material = self.repository.formal_material(actor, row)
        statement = row["snapshot"]["statement"]
        prefix = f"statements/{UUID(statement['id'])}/v{row['statement_version']}"
        files, total = {}, 0

        def add(path, content):
            nonlocal total
            total += len(content)
            if total > MAX_BYTES:
                raise BusinessError("ARCHIVE_LIMIT_EXCEEDED", 413)
            files[path] = content

        def encoded(value):
            return json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()

        add(f"{prefix}/statement.xlsx", self.content(row))
        add(
            f"{prefix}/confirmation.json",
            encoded(
                {
                    "format": "statement-formal-package-v1",
                    "export_id": str(row["id"]),
                    "file_hash": row["file_hash"],
                    "statement": statement,
                }
            ),
        )
        for event in material["events"]:
            add(
                f"{prefix}/formal-history/v{event['record']['version']}.json",
                event["json"].encode(),
            )
        for item in material["approvals"]:
            approval = item["record"]
            add(
                f"approvals/{UUID(approval['id'])}/v{approval['version']}.json",
                item["json"].encode(),
            )
        for evidence in material["evidence"]:
            identifier = str(UUID(evidence["id"]))
            add(f"evidence/{identifier}.json", encoded(evidence))
            if evidence["object_hash"]:
                try:
                    envelope = json.loads(self.store.read(evidence["object_hash"]))
                    content = base64.b64decode(envelope["base64"], validate=True)
                    if (
                        envelope["format"] != "statement-feedback-v1"
                        or hashlib.sha256(content).hexdigest() != envelope["sha256"]
                    ):
                        raise ValueError
                    extension = {"image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf"}[
                        evidence["media_type"]
                    ]
                except KeyError, ValueError, TypeError:
                    raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503) from None
                add(f"evidence/{identifier}.{extension}", content)
        for sent_export in material["sent_exports"]:
            add(f"sent-exports/{UUID(sent_export['id'])}.xlsx", self.content(sent_export))
        stream = BytesIO()
        with ZipFile(stream, "w", compression=ZIP_DEFLATED) as zipped:
            for path, content in sorted(files.items()):
                entry = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.create_system = 3
                entry.external_attr = 0o100644 << 16
                zipped.writestr(entry, content)
        content = stream.getvalue()
        if len(content) > MAX_BYTES:
            raise BusinessError("ARCHIVE_LIMIT_EXCEEDED", 413)
        return content

    def catalog(self, actor, cursor: str | None, limit: int) -> dict:
        if type(limit) is not int or not 1 <= limit <= 50:
            raise BusinessError("INVALID_INPUT", field="limit")
        if cursor is not None:
            try:
                cursor = self.validate_key(cursor)
            except BusinessError:
                raise BusinessError("INVALID_CURSOR", field="cursor") from None
        keys = self.repository.listing(actor, cursor, limit + 1)
        return {
            "items": [self.describe(actor, key) for key in keys[:limit]],
            "next_cursor": keys[limit - 1] if len(keys) > limit else None,
        }

    def capture(self, actor, key: str) -> tuple[dict, bytes]:
        key = self.validate_key(key)
        row = self.repository.get(actor, key)
        if key.startswith("statement_pending:") or row["status"] != "ready":
            raise BusinessError("STATEMENT_EXPORT_NOT_READY", 409)
        content = (
            self.formal_package(actor, row)
            if row["snapshot"]["statement"].get("status") == "confirmed"
            else self.content(row)
        )
        return self.metadata(key, row, content), content
