"""Persisted proposals and immutable source objects, separate from order commands."""

import base64
import hashlib
import json
from dataclasses import dataclass
from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.domain.candidate import propose
from factoryflow.modules.documents.domain.purchase_sheet import map_purchase_sheet


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


@dataclass
class ExtractionWork:
    sources: object
    journal: object


class ExtractionService:
    def __init__(self, transaction, store, extractor, spreadsheet_reader=None):
        self.transaction, self.store, self.extractor = transaction, store, extractor
        self.spreadsheet_reader = spreadsheet_reader

    def upload(self, actor, key, filename, media_type, content, purpose="sales_order"):
        actor.require_write()
        if purpose not in ("sales_order", "purchase_order"):
            raise BusinessError("SOURCE_PURPOSE_MISMATCH")
        signatures = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
            "application/pdf": b"%PDF-",
        }
        if purpose == "purchase_order":
            signatures["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"] = (
                b"PK\x03\x04"
            )
        if media_type not in signatures or not content.startswith(signatures[media_type]):
            raise BusinessError("FILE_TYPE_UNSUPPORTED", 422)
        if not 0 < len(content) <= 10 * 1024 * 1024:
            raise BusinessError("FILE_TOO_LARGE", 413)
        if media_type.endswith("spreadsheetml.sheet"):
            if self.spreadsheet_reader is None:
                raise BusinessError("FILE_TYPE_UNSUPPORTED")
            self.spreadsheet_reader(content)
        filename = filename.strip()
        if not filename or len(filename) > 180 or any(ord(c) < 32 for c in filename):
            raise BusinessError("INVALID_INPUT", 422)
        original = hashlib.sha256(content).hexdigest()
        payload = {"filename": filename, "media_type": media_type, "sha256": original}
        # Default sales retries keep the original payload hash and command name.
        if purpose != "sales_order":
            payload["purpose"] = purpose
        with self.transaction() as work:
            prior = work.journal.claim(actor, "source.upload", key, payload)
            if prior is not None:
                return prior
            blob = self.store.put(
                encode(
                    {
                        "format": "source-file-v1",
                        "media_type": media_type,
                        "original_sha256": original,
                        "base64": base64.b64encode(content).decode("ascii"),
                    }
                )
            )
            row = work.sources.add_source(
                {
                    "id": uuid7(),
                    "organization_id": actor.organization_id,
                    "actor_id": actor.user_id,
                    "filename": filename,
                    "media_type": media_type,
                    "byte_size": len(content),
                    "original_sha256": original,
                    "blob_hash": blob,
                    "purpose": purpose,
                }
            )
            result = {"source_id": str(row["id"]), "original_sha256": original}
            work.journal.audit(actor, "source.upload", row["id"])
            work.journal.finish(actor, "source.upload", key, result)
            return result

    def original(self, actor, source_id):
        with self.transaction() as work:
            row = work.sources.source(actor.organization_id, source_id)
        envelope = json.loads(self.store.read(row["blob_hash"]))
        content = base64.b64decode(envelope["base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != row["original_sha256"]:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        return row, content

    def extract(self, actor, key, source_id):
        actor.require_write()
        # Keep the v1 request fingerprint so a response-lost retry after an upgrade
        # still replays its immutable result. The actual parser version lives in the trace.
        payload = {"source_id": str(source_id), "parser_version": "simple-rows-v1"}
        with self.transaction() as work:
            prior = work.journal.claim(actor, "source.extract", key, payload)
            if prior is not None:
                return prior
        row, content = self.original(actor, source_id)
        is_sheet = row["media_type"].endswith("spreadsheetml.sheet")
        trace = (
            self.spreadsheet_reader(content)
            if is_sheet
            else self.extractor.extract(content, row["media_type"])
        )
        trace.update(
            format="extraction-trace-v1",
            parser_version="purchase-sheet-v2" if is_sheet else "table-rows-v15",
            original_sha256=row["original_sha256"],
        )
        if not is_sheet:
            trace["candidate"] = propose(
                [line for page in trace["pages"] for line in page["rows"]],
                pages=trace["pages"],
                line_limit=201 if row["purpose"] == "purchase_order" else 200,
            )
        if row["purpose"] == "purchase_order" and len(trace["candidate"]["lines"]) > 200:
            trace.update(status="failed", error_code="PURCHASE_IMPORT_TOO_MANY_LINES")
            trace["candidate"]["lines"] = []
        digest = self.store.put(encode(trace))
        with self.transaction() as work:
            prior = work.journal.claim(actor, "source.extract", key, payload)
            if prior is not None:
                return prior
            run_id = uuid7()
            work.sources.add_run(
                {
                    "id": run_id,
                    "organization_id": actor.organization_id,
                    "source_id": source_id,
                    "actor_id": actor.user_id,
                    "status": trace["status"],
                    "trace_hash": digest,
                }
            )
            result = {"extraction_id": str(run_id), "status": trace["status"]}
            work.journal.audit(actor, "source.extract", run_id)
            work.journal.finish(actor, "source.extract", key, result)
            return result

    def detail(self, actor, run_id):
        with self.transaction() as work:
            run = work.sources.run(actor.organization_id, run_id)
        trace = json.loads(self.store.read(run["trace_hash"]))
        return {
            "extraction_id": str(run_id),
            "source_id": str(run["source_id"]),
            "trace_hash": run["trace_hash"],
            "original_sha256": run["original_sha256"],
            "purpose": run["purpose"],
            "media_type": run["media_type"],
            **trace,
        }

    def preview_purchase_sheet(self, actor, run_id, mapping):
        actor.require_write()
        detail = self.detail(actor, run_id)
        if detail["purpose"] != "purchase_order":
            raise BusinessError("SOURCE_PURPOSE_MISMATCH", 409)
        if detail.get("error_code") in {
            "PURCHASE_IMPORT_TOO_MANY_LINES",
            "PURCHASE_SHEET_MERGED_DETAIL",
        }:
            raise BusinessError(detail["error_code"], field="lines")
        if not detail.get("spreadsheet"):
            raise BusinessError("PURCHASE_SHEET_REQUIRED")
        return map_purchase_sheet(detail["spreadsheet"], mapping)

    @staticmethod
    def _summary(row):
        return {
            "source_id": str(row["id"]),
            "filename": row["filename"],
            "media_type": row["media_type"],
            "purpose": row["purpose"],
            "created_at": row["created_at"].isoformat(),
            "extraction_id": str(row["extraction_id"]) if row["extraction_id"] else None,
            "extraction_status": row["extraction_status"],
            "order_id": str(row["order_id"]) if row["order_id"] else None,
        }

    def summary(self, actor, source_id):
        with self.transaction() as work:
            return self._summary(work.sources.summary(actor.organization_id, source_id))

    def list(self, actor, cursor, limit, purpose="sales_order"):
        with self.transaction() as work:
            rows = work.sources.list(actor.organization_id, cursor, limit + 1, purpose)
        return {
            "items": [self._summary(row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }
