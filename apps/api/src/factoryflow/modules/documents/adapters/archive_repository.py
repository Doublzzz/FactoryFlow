"""Read source-owned records using the caller's transaction connection."""

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class ArchiveDocumentRepository:
    def __init__(self, conn):
        self.conn = conn

    def get(self, actor, identifier):
        row = (
            self.conn.execute(
                text(
                    "SELECT s.*, i.order_id FROM source_files s LEFT JOIN source_imports i "
                    "ON i.organization_id=s.organization_id AND i.source_id=s.id "
                    "WHERE s.organization_id=:org AND s.id=:id"
                ),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("SOURCE_NOT_FOUND", 404)
        return dict(row)

    def listing(self, actor, cursor, limit):
        return [
            dict(row)
            for row in self.conn.execute(
                text(
                    "SELECT s.*, i.order_id FROM source_files s LEFT JOIN source_imports i "
                    "ON i.organization_id=s.organization_id AND i.source_id=s.id "
                    "WHERE s.organization_id=:org "
                    "AND (CAST(:cursor AS uuid) IS NULL OR s.id<CAST(:cursor AS uuid)) "
                    "ORDER BY s.id DESC LIMIT :limit"
                ),
                {"org": actor.organization_id, "cursor": cursor, "limit": limit},
            ).mappings()
        ]
