from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class SourceRepository:
    def __init__(self, conn):
        self.conn = conn

    def add_source(self, params):
        self.conn.execute(
            text("""INSERT INTO source_files
          (id,organization_id,actor_id,filename,media_type,byte_size,original_sha256,blob_hash)
          VALUES (:id,:organization_id,:actor_id,:filename,:media_type,
                  :byte_size,:original_sha256,:blob_hash)
          ON CONFLICT (organization_id,original_sha256) DO NOTHING"""),
            params,
        )
        return dict(
            self.conn.execute(
                text(
                    "SELECT * FROM source_files "
                    "WHERE organization_id=:org AND original_sha256=:hash"
                ),
                {"org": params["organization_id"], "hash": params["original_sha256"]},
            )
            .mappings()
            .one()
        )

    def source(self, org, source_id):
        row = (
            self.conn.execute(
                text("SELECT * FROM source_files WHERE organization_id=:org AND id=:id"),
                {"org": org, "id": source_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("SOURCE_NOT_FOUND", 404)
        return dict(row)

    def list(self, org, cursor, limit):
        rows = self.conn.execute(
            text(
                """SELECT s.*, i.order_id,
          (SELECT r.id FROM extraction_runs r WHERE r.organization_id=s.organization_id
           AND r.source_id=s.id
           ORDER BY r.id DESC LIMIT 1) AS extraction_id
          FROM source_files s LEFT JOIN source_imports i
          ON i.organization_id=s.organization_id AND i.source_id=s.id
          WHERE s.organization_id=:org
          AND (CAST(:cursor AS uuid) IS NULL OR s.id<CAST(:cursor AS uuid))
          ORDER BY s.id DESC LIMIT :limit"""
            ),
            {"org": org, "cursor": str(cursor) if cursor else None, "limit": limit},
        ).mappings()
        return [dict(row) for row in rows]

    def add_run(self, params):
        self.conn.execute(
            text("""INSERT INTO extraction_runs
          (id,organization_id,source_id,actor_id,status,trace_hash)
          VALUES (:id,:organization_id,:source_id,:actor_id,:status,:trace_hash)"""),
            params,
        )

    def run(self, org, run_id):
        row = (
            self.conn.execute(
                text("""SELECT r.*, s.original_sha256, s.blob_hash, s.media_type
          FROM extraction_runs r JOIN source_files s
          ON s.organization_id=r.organization_id AND s.id=r.source_id
          WHERE r.organization_id=:org AND r.id=:id"""),
                {"org": org, "id": run_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("EXTRACTION_NOT_FOUND", 404)
        return dict(row)

    def claim(self, org, run_id, revision_id, order_id):
        run = self.run(org, run_id)
        inserted = self.conn.execute(
            text("""INSERT INTO source_imports
          (organization_id,source_id,extraction_id,revision_id,order_id)
          VALUES (:org,:source,:run,:revision,:order)
          ON CONFLICT DO NOTHING RETURNING source_id"""),
            {
                "org": org,
                "source": run["source_id"],
                "run": run_id,
                "revision": revision_id,
                "order": order_id,
            },
        ).scalar()
        if inserted is None:
            raise BusinessError("SOURCE_ALREADY_IMPORTED", 409)
        return run
