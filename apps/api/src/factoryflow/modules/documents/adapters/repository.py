from sqlalchemy import text


class RevisionRepository:
    def __init__(self, conn):
        self.conn = conn

    def backup_hashes(self):
        has_sources = self.conn.execute(text("SELECT to_regclass('public.source_files')")).scalar()
        query = "SELECT blob_hash FROM confirmed_revisions"
        if has_sources:
            query += (
                " UNION SELECT blob_hash FROM source_files"
                " UNION SELECT trace_hash FROM extraction_runs"
            )
        return list(self.conn.execute(text(query)).scalars())

    def insert(self, evidence):
        self.conn.execute(
            text("""INSERT INTO confirmed_revisions
         (id,organization_id,customer_id,order_id,parent_id,revision_number,schema_version,blob_hash,actor_id)
         VALUES (:revision_id,:organization_id,:customer_id,:order_id,:parent_revision_id,
                 :revision_number,:schema_version,:blob_hash,:actor_id)"""),
            evidence,
        )

    def get(self, organization_id, revision_id):
        result = (
            self.conn.execute(
                text("SELECT * FROM confirmed_revisions WHERE organization_id=:org AND id=:id"),
                {"org": organization_id, "id": revision_id},
            )
            .mappings()
            .first()
        )
        return dict(result) if result else None

    def history(self, organization_id, order_id):
        rows = self.conn.execute(
            text(
                "SELECT id,blob_hash,revision_number,parent_id,created_at "
                "FROM confirmed_revisions WHERE organization_id=:org "
                "AND order_id=:order ORDER BY revision_number"
            ),
            {"org": organization_id, "order": order_id},
        ).mappings()
        return [
            {
                "revision_id": str(r["id"]),
                "sha256": r["blob_hash"],
                "revision_number": r["revision_number"],
                "parent_revision_id": str(r["parent_id"]) if r["parent_id"] else None,
                "confirmed_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
