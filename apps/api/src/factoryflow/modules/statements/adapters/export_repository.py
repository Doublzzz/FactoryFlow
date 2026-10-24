import json

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class StatementExportRepository:
    def __init__(self, conn):
        self.conn = conn

    def create(self, actor, snapshot):
        statement = snapshot["statement"]
        # Omit the nullable extension for builtin layouts; legacy-backup seeding stays valid.
        custom_columns = "customer_template_id," if "customer_template" in snapshot else ""
        custom_value = ":custom," if "customer_template" in snapshot else ""
        self.conn.execute(
            text(
                "INSERT INTO statement_exports(organization_id,id,statement_id,customer_id,"
                f"statement_version,template_id,template_version,{custom_columns}snapshot) "
                f"VALUES(:org,:id,:statement,:customer,:version,:template,:template_version,{custom_value}"
                "CAST(:snapshot AS jsonb))"
            ),
            {
                "org": actor.organization_id,
                "id": snapshot["id"],
                "statement": statement["id"],
                "customer": statement["customer_id"],
                "version": statement["version"],
                "template": snapshot["template_id"],
                "template_version": snapshot["template_version"],
                "custom": snapshot.get("customer_template", {}).get("id"),
                "snapshot": json.dumps(snapshot),
            },
        )

    def get(self, actor, identifier):
        row = (
            self.conn.execute(
                text(
                    "SELECT e.*, COALESCE(e.snapshot->'statement'->>'status','draft') "
                    "AS statement_status, "
                    "(s.status IN ('draft','confirmed') AND s.version=e.statement_version) "
                    "AS current "
                    "FROM statement_exports e JOIN statements s "
                    "ON s.organization_id=e.organization_id "
                    "AND s.id=e.statement_id WHERE e.organization_id=:org AND e.id=:id"
                ),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("STATEMENT_EXPORT_NOT_FOUND", 404)
        return {
            **dict(row),
            "id": str(row["id"]),
            "statement_id": str(row["statement_id"]),
            "customer_id": str(row["customer_id"]),
            "created_at": row["created_at"].isoformat(),
        }

    def listing(self, actor, statement_id, cursor=None, limit=50):
        ids = list(
            self.conn.execute(
                text(
                    "SELECT id FROM statement_exports WHERE organization_id=:org "
                    "AND statement_id=:id "
                    "AND (CAST(:cursor AS uuid) IS NULL OR id<CAST(:cursor AS uuid)) "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {
                    "org": actor.organization_id,
                    "id": statement_id,
                    "cursor": cursor,
                    "limit": limit + 1,
                },
            ).scalars()
        )
        return {
            "items": [self.get(actor, i) for i in ids[:limit]],
            "next_cursor": str(ids[limit - 1]) if len(ids) > limit else None,
        }

    def finish(
        self, actor, identifier, digest=None, file_hash=None, error_code="EXPORT_RENDER_FAILED"
    ):
        self.conn.execute(
            text(
                "UPDATE statement_exports SET status=:status,object_hash=:digest,file_hash=:file,"
                "error_code=:error WHERE organization_id=:org AND id=:id AND status<>'ready'"
            ),
            {
                "org": actor.organization_id,
                "id": identifier,
                "status": "ready" if digest else "failed",
                "digest": digest,
                "file": file_hash,
                "error": None if digest else error_code,
            },
        )

    def backup_hashes(self):
        if self.conn.execute(text("SELECT to_regclass('statement_exports')")).scalar() is None:
            return []
        return list(
            self.conn.execute(
                text("SELECT DISTINCT object_hash FROM statement_exports WHERE status='ready'")
            ).scalars()
        )
