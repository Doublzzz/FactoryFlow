import json

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class DeliveryLayoutRepository:
    def __init__(self, conn):
        self.conn = conn

    def current(self, actor):
        row = (
            self.conn.execute(
                text(
                    "SELECT version,config,created_at FROM delivery_layout_versions "
                    "WHERE organization_id=:org ORDER BY version DESC LIMIT 1"
                ),
                {"org": actor.organization_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            return None
        return {
            "version": row["version"],
            "config": row["config"],
            "updated_at": row["created_at"].isoformat(),
        }

    def append(self, actor, expected, config):
        # Concurrent first saves and updates compete on the same next version.
        version = self.conn.execute(
            text(
                "INSERT INTO delivery_layout_versions(organization_id,version,config,actor_id) "
                "VALUES(:org,:version,CAST(:config AS jsonb),:actor) "
                "ON CONFLICT(organization_id,version) DO NOTHING RETURNING version"
            ),
            {
                "org": actor.organization_id,
                "version": expected + 1,
                "config": json.dumps(config),
                "actor": actor.user_id,
            },
        ).scalar_one_or_none()
        if version is None:
            raise BusinessError("VERSION_CONFLICT", 409)
