"""Export catalog and explicit unexported placeholders, scoped to one organization."""

import json
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.adapters.export_repository import StatementExportRepository
from sqlalchemy import text


class ArchiveStatementRepository:
    def __init__(self, conn):
        self.conn = conn
        self.exports = StatementExportRepository(conn)

    def listing(self, actor, cursor, limit):
        return list(
            self.conn.execute(
                text(
                    "SELECT key FROM ("
                    "SELECT 'statement_export:' || id::text AS key FROM statement_exports "
                    "WHERE organization_id=:org UNION ALL "
                    "SELECT 'statement_pending:' || s.id::text AS key FROM statements s "
                    "WHERE s.organization_id=:org AND NOT EXISTS "
                    "(SELECT 1 FROM statement_exports e WHERE e.organization_id=s.organization_id "
                    "AND e.statement_id=s.id AND e.statement_version=s.version)) catalog "
                    "WHERE CAST(:cursor AS text) IS NULL OR key<:cursor "
                    "ORDER BY key DESC LIMIT :limit"
                ),
                {"org": actor.organization_id, "cursor": cursor, "limit": limit},
            ).scalars()
        )

    def get(self, actor, key):
        prefix, identifier = key.split(":", 1)
        if prefix == "statement_export":
            return self.exports.get(actor, UUID(identifier))
        row = (
            self.conn.execute(
                text(
                    "SELECT s.* FROM statements s WHERE s.organization_id=:org AND s.id=:id "
                    "AND NOT EXISTS (SELECT 1 FROM statement_exports e "
                    "WHERE e.organization_id=s.organization_id AND e.statement_id=s.id "
                    "AND e.statement_version=s.version)"
                ),
                {"org": actor.organization_id, "id": UUID(identifier)},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("STATEMENT_NOT_FOUND", 404)
        return dict(row)

    def formal_material(self, actor, export):
        """Resolve only immutable versions pinned by the selected formal snapshots."""
        statement = export["snapshot"]["statement"]
        params = {
            "org": actor.organization_id,
            "statement": export["statement_id"],
            "version": export["statement_version"],
        }
        event_json = list(
            self.conn.execute(
                text(
                    "SELECT to_jsonb(e)::text FROM statement_events e WHERE organization_id=:org "
                    "AND statement_id=:statement AND version<=:version "
                    "AND action IN ('settle','correct_settlement') ORDER BY version"
                ),
                params,
            ).scalars()
        )
        events = [json.loads(content) for content in event_json]
        if not events or events[-1]["version"] != export["statement_version"]:
            raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
        approvals, evidence, sent_exports = {}, {}, {}

        def add_evidence(identifier, kind="feedback", parent=None):
            identifier = str(UUID(identifier))
            row = self.conn.execute(
                text(
                    "SELECT to_jsonb(e) FROM statement_evidence e WHERE organization_id=:org "
                    "AND id=:id AND customer_id=:customer"
                ),
                {
                    "org": actor.organization_id,
                    "id": identifier,
                    "customer": statement["customer_id"],
                },
            ).scalar_one_or_none()
            if (
                row is None
                or (kind is not None and row["kind"] != kind)
                or (parent and row["statement_id"] != parent)
            ):
                raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
            evidence[identifier] = row
            if row["kind"] == "sent":
                sent_export = self.exports.get(actor, UUID(row["export_id"]))
                if (
                    sent_export["status"] != "ready"
                    or sent_export["statement_id"] != row["statement_id"]
                    or sent_export["statement_version"] != row["statement_version"]
                ):
                    raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
                sent_exports[sent_export["id"]] = sent_export

        for snapshot in [statement, *(event["snapshot"] for event in events)]:
            if "approval_refs" not in snapshot or "confirmation_evidence_ids" not in snapshot:
                raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
            for identifier in snapshot["confirmation_evidence_ids"]:
                add_evidence(identifier, kind=None, parent=snapshot["id"])
            correction = snapshot.get("correction")
            if correction:
                add_evidence(correction["evidence_id"])
            for ref in snapshot["approval_refs"]:
                identifier = str(UUID(ref["approval_id"]))
                version = ref["version"]
                approval_json = self.conn.execute(
                    text(
                        "SELECT snapshot::text FROM statement_lifecycle_events "
                        "WHERE organization_id=:org "
                        "AND kind='statement_approvals' AND entity_id=:id AND version=:version"
                    ),
                    {"org": actor.organization_id, "id": identifier, "version": version},
                ).scalar_one_or_none()
                approval = json.loads(approval_json) if approval_json is not None else None
                if (
                    approval is None
                    or approval["customer_id"] != statement["customer_id"]
                    or approval["sent_id"] != ref["sent_id"]
                    or approval["feedback_id"] != ref["feedback_id"]
                ):
                    raise BusinessError("EVIDENCE_INTEGRITY_FAILED", 503)
                approvals[(identifier, version)] = {"record": approval, "json": approval_json}
                add_evidence(ref["sent_id"], "sent", approval["statement_id"])
                add_evidence(ref["feedback_id"], "feedback", approval["statement_id"])
                if approval.get("correction"):
                    add_evidence(approval["correction"]["evidence_id"])
        return {
            "events": [
                {"record": event, "json": content}
                for event, content in zip(events, event_json, strict=True)
            ],
            "approvals": [approvals[key] for key in sorted(approvals)],
            "evidence": [evidence[key] for key in sorted(evidence)],
            "sent_exports": [sent_exports[key] for key in sorted(sent_exports)],
        }
