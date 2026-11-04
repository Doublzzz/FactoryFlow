"""Source-owned integrity checks participating in the purchase command's transaction."""

import base64
import hashlib
import json

from factoryflow.kernel.contracts import BusinessError


class PurchaseEvidence:
    def __init__(self, sources, store):
        self.sources, self.store = sources, store

    def verify(self, actor, source_id, extraction_id=None):
        source = self.sources.source(actor.organization_id, source_id)
        if source["purpose"] != "purchase_order":
            raise BusinessError("SOURCE_PURPOSE_MISMATCH", 409)
        envelope = json.loads(self.store.read(source["blob_hash"]))
        content = base64.b64decode(envelope["base64"], validate=True)
        if hashlib.sha256(content).hexdigest() != source["original_sha256"]:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        if source["media_type"].endswith("spreadsheetml.sheet") and extraction_id is None:
            raise BusinessError("PURCHASE_EXTRACTION_REQUIRED", field="extraction_id")
        if extraction_id is not None:
            run = self.sources.run(actor.organization_id, extraction_id)
            if str(run["source_id"]) != str(source_id):
                raise BusinessError("SOURCE_RUN_MISMATCH", 409)
            trace = json.loads(self.store.read(run["trace_hash"]))
            if trace["original_sha256"] != source["original_sha256"]:
                raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
            if trace.get("error_code") in {
                "PURCHASE_IMPORT_TOO_MANY_LINES",
                "PURCHASE_SHEET_MERGED_DETAIL",
            }:
                raise BusinessError(trace["error_code"], field="lines")
        return {
            "source_id": str(source_id),
            "extraction_id": str(extraction_id) if extraction_id else None,
        }
