import json

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class ArchiveRepository:
    def __init__(self, conn):
        self.conn = conn

    def settings(self, actor):
        row = (
            self.conn.execute(
                text(
                    "SELECT version,rule,created_at FROM archive_settings "
                    "WHERE organization_id=:org "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"org": actor.organization_id},
            )
            .mappings()
            .first()
        )
        return (
            {
                "version": row["version"],
                "rule": row["rule"],
                "updated_at": row["created_at"].isoformat(),
            }
            if row
            else {"version": 0, "rule": "month_customer", "updated_at": None}
        )

    def save_settings(self, actor, expected, rule):
        result = self.conn.execute(
            text(
                "INSERT INTO archive_settings(organization_id,version,rule,actor_id) "
                "VALUES(:org,:version,:rule,:actor) ON CONFLICT DO NOTHING RETURNING version"
            ),
            {
                "org": actor.organization_id,
                "version": expected + 1,
                "rule": rule,
                "actor": actor.user_id,
            },
        ).scalar()
        if result is None:
            raise BusinessError("VERSION_CONFLICT", 409)

    def find(self, actor, fingerprint):
        return self.conn.execute(
            text("SELECT id FROM archive_batches WHERE organization_id=:org AND fingerprint=:hash"),
            {"org": actor.organization_id, "hash": fingerprint},
        ).scalar()

    def create(self, actor, identifier, fingerprint, rule, digest, manifest):
        self.conn.execute(
            text(
                "INSERT INTO archive_batches(organization_id,id,fingerprint,rule,"
                "input_hash,manifest,"
                "actor_id) VALUES(:org,:id,:hash,:rule,:input,CAST(:manifest AS jsonb),:actor) "
                "ON CONFLICT(organization_id,fingerprint) DO NOTHING"
            ),
            {
                "org": actor.organization_id,
                "id": identifier,
                "hash": fingerprint,
                "rule": rule,
                "input": digest,
                "manifest": json.dumps(manifest),
                "actor": actor.user_id,
            },
        )

    def get(self, actor, identifier, lock=False):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM archive_batches WHERE organization_id=:org AND id=:id"
                    + (" FOR UPDATE" if lock else "")
                ),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("ARCHIVE_NOT_FOUND", 404)
        return {**dict(row), "id": str(row["id"]), "created_at": row["created_at"].isoformat()}

    def listing(self, actor, cursor=None, limit=25):
        ids = list(
            self.conn.execute(
                text(
                    "SELECT id FROM archive_batches WHERE organization_id=:org "
                    "AND (CAST(:cursor AS uuid) IS NULL OR id<CAST(:cursor AS uuid)) "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {"org": actor.organization_id, "cursor": cursor, "limit": limit + 1},
            ).scalars()
        )
        return {
            "items": [self.get(actor, i) for i in ids[:limit]],
            "next_cursor": str(ids[limit - 1]) if len(ids) > limit else None,
        }

    def finish(self, actor, identifier, digest=None, file_hash=None, error=None):
        self.conn.execute(
            text(
                "UPDATE archive_batches SET status=:status,object_hash=:digest,file_hash=:file,"
                "error_code=:error WHERE organization_id=:org AND id=:id AND status<>'ready'"
            ),
            {
                "org": actor.organization_id,
                "id": identifier,
                "status": "ready" if digest else "failed",
                "digest": digest,
                "file": file_hash,
                "error": None if digest else error,
            },
        )

    def backup_hashes(self):
        if self.conn.execute(text("SELECT to_regclass('archive_batches')")).scalar() is None:
            return []
        return list(
            self.conn.execute(
                text(
                    "SELECT input_hash FROM archive_batches UNION "
                    "SELECT object_hash FROM archive_batches WHERE object_hash IS NOT NULL"
                )
            ).scalars()
        )
