"""Owns confirmation evidence and its public, transaction-participating facade."""

import json
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import Actor, BusinessError


class RevisionRepository(Protocol):
    def insert(self, evidence: dict) -> None: ...
    def get(self, organization_id: UUID, revision_id: UUID) -> dict | None: ...
    def history(self, organization_id: UUID, order_id: UUID) -> list[dict]: ...


class EvidenceStore(Protocol):
    def put(self, content: bytes) -> str: ...
    def read(self, digest: str) -> bytes: ...


class Documents:
    def __init__(self, repository: RevisionRepository, store: EvidenceStore, sources=None):
        self.repository, self.store, self.sources = repository, store, sources

    def confirm(
        self,
        actor: Actor,
        order_id: UUID,
        customer_id: UUID,
        content: dict,
        parent_id: UUID | None = None,
        number: int = 1,
        extraction_id: UUID | None = None,
        inherited_source: dict | None = None,
    ) -> dict:
        revision_id = uuid7()
        source = inherited_source
        if extraction_id is not None:
            run = self.sources.claim(actor.organization_id, extraction_id, revision_id, order_id)
            self.store.read(run["trace_hash"])
            self.store.read(run["blob_hash"])
            source = {
                "source_id": str(run["source_id"]),
                "extraction_id": str(extraction_id),
                "original_sha256": run["original_sha256"],
                "source_hash": run["blob_hash"],
                "trace_hash": run["trace_hash"],
            }
        evidence = {
            "schema_version": (
                3 if any("item_name" in line for line in content["lines"]) else 2 if source else 1
            ),
            "revision_id": str(revision_id),
            "organization_id": str(actor.organization_id),
            "customer_id": str(customer_id),
            "order_id": str(order_id),
            "parent_revision_id": str(parent_id) if parent_id else None,
            "revision_number": number,
            "actor_id": str(actor.user_id),
            "confirmed_at": datetime.now(UTC).isoformat(),
            "order": content,
        }
        if source:
            evidence["source"] = source
        encoded = (
            json.dumps(evidence, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        digest = self.store.put(encoded)
        indexed = {**evidence, "blob_hash": digest}
        self.repository.insert(indexed)
        return {"revision_id": str(revision_id), "sha256": digest, "revision_number": number}

    def read(self, actor: Actor, revision_id: UUID) -> dict:
        indexed = self.repository.get(actor.organization_id, revision_id)
        if indexed is None:
            raise BusinessError("REVISION_NOT_FOUND", 404)
        content = json.loads(self.store.read(indexed["blob_hash"]))
        return {"revision_id": str(revision_id), "sha256": indexed["blob_hash"], "content": content}

    def history(self, actor: Actor, order_id: UUID) -> list[dict]:
        return self.repository.history(actor.organization_id, order_id)
