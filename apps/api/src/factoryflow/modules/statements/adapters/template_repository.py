import json

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class StatementTemplateRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, actor, customer_id, identifier):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM statement_templates WHERE organization_id=:org "
                    "AND customer_id=:customer AND id=:id"
                ),
                {"org": actor.organization_id, "customer": customer_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("STATEMENT_TEMPLATE_NOT_FOUND", 404)
        return {
            **dict(row),
            "id": str(row["id"]),
            "customer_id": str(row["customer_id"]),
            "created_at": row["created_at"].isoformat(),
        }

    def create(self, actor, customer_id, identifier, name, file_hash, object_hash, mapping):
        # Caller holds the customer lock; SQL uniqueness also protects sequential versions.
        self.conn.execute(
            text(
                "INSERT INTO statement_templates(organization_id,id,customer_id,version,name,"
                "file_hash,object_hash,mapping,actor_id) SELECT :org,:id,:customer,"
                "COALESCE(max(version),0)+1,:name,:file,:object,CAST(:mapping AS jsonb),:actor "
                "FROM statement_templates WHERE organization_id=:org AND customer_id=:customer"
            ),
            {
                "org": actor.organization_id,
                "id": identifier,
                "customer": customer_id,
                "name": name,
                "file": file_hash,
                "object": object_hash,
                "mapping": json.dumps(mapping),
                "actor": actor.user_id,
            },
        )

    def listing(self, actor, customer_id, cursor=None, limit=50):
        rows = list(
            self.conn.execute(
                text(
                    "SELECT id FROM statement_templates WHERE organization_id=:org "
                    "AND customer_id=:customer "
                    "AND (CAST(:cursor AS uuid) IS NULL OR id<CAST(:cursor AS uuid)) "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {
                    "org": actor.organization_id,
                    "customer": customer_id,
                    "cursor": cursor,
                    "limit": limit + 1,
                },
            ).scalars()
        )
        return {
            "items": [self.get(actor, customer_id, row) for row in rows[:limit]],
            "next_cursor": str(rows[limit - 1]) if len(rows) > limit else None,
        }

    def backup_hashes(self):
        if self.conn.scalar(text("SELECT to_regclass('statement_templates')")) is None:
            return []
        return list(
            self.conn.execute(
                text("SELECT DISTINCT object_hash FROM statement_templates")
            ).scalars()
        )
