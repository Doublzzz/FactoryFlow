"""Persisted proposals and immutable source objects, separate from order commands."""

import base64
import hashlib
import json
from dataclasses import dataclass
from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.documents.domain.candidate import propose


def encode(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


@dataclass
class ExtractionWork:
    sources: object
    journal: object


class ExtractionService:
    def __init__(self, transaction, store, extractor):
        self.transaction, self.store, self.extractor = transaction, store, extractor

    def upload(self, actor, key, filename, media_type, content):
        actor.require_write()
        signatures = {
            "image/png": b"\x89PNG\r\n\x1a\n",
            "image/jpeg": b"\xff\xd8\xff",
            "application/pdf": b"%PDF-",
        }
        if media_type not in signatures or not content.startswith(signatures[media_type]):
            raise BusinessError("FILE_TYPE_UNSUPPORTED", 422)
        if not 0 < len(content) <= 10 * 1024 * 1024:
            raise BusinessError("FILE_TOO_LARGE", 413)
        filename = filename.strip()
        if not filename or len(filename) > 180 or any(ord(c) < 32 for c in filename):
            raise BusinessError("INVALID_INPUT", 422)
        original = hashlib.sha256(content).hexdigest()
        payload = {"filename": filename, "media_type": media_type, "sha256": original}
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
        trace = self.extractor.extract(content, row["media_type"])
        trace.update(
            format="extraction-trace-v1",
            parser_version="table-rows-v13",
            original_sha256=row["original_sha256"],
        )
        trace["candidate"] = propose(
            [line for page in trace["pages"] for line in page["rows"]], pages=trace["pages"]
        )
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
            **trace,
        }

    def list(self, actor, cursor, limit):
        with self.transaction() as work:
            rows = work.sources.list(actor.organization_id, cursor, limit + 1)
        return {
            "items": [
                {
                    "source_id": str(r["id"]),
                    "filename": r["filename"],
                    "media_type": r["media_type"],
                    "created_at": r["created_at"].isoformat(),
                    "extraction_id": str(r["extraction_id"]) if r["extraction_id"] else None,
                    "order_id": str(r["order_id"]) if r["order_id"] else None,
                }
                for r in rows[:limit]
            ],
            "next_cursor": str(rows[limit - 1]["id"]) if len(rows) > limit else None,
        }
