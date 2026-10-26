"""Explicit engine construction and shared atomic command journal."""

import hashlib
import json
from uuid import UUID, uuid7

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from factoryflow.kernel.contracts import Actor, BusinessError

REVISION = "0015_order_currencies"


def engine_for(url: str):
    target = make_url(url)
    if (
        target.drivername != "postgresql+psycopg"
        or target.host not in {"127.0.0.1", "localhost", "::1"}
        or target.query
    ):
        raise ValueError("FactoryFlow requires an explicit PostgreSQL loopback URL without query")
    return create_engine(
        url,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={
            "hostaddr": "::1" if target.host == "::1" else "127.0.0.1",
            "connect_timeout": 5,
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        },
    )


def check_ready(engine, object_root):
    with engine.connect() as conn:
        if conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != REVISION:
            raise BusinessError("SCHEMA_MISMATCH", 503)
    if not object_root.is_dir():
        raise BusinessError("OBJECT_STORE_UNAVAILABLE", 503)


class Journal:
    def __init__(self, conn):
        self.conn = conn

    def claim(self, actor: Actor, command: str, key: UUID, payload: dict):
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        params = {"org": actor.organization_id, "command": command, "key": key}
        self.conn.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:scope, 0))"),
            {"scope": f"{actor.organization_id}:{command}:{key}"},
        )
        prior = (
            self.conn.execute(
                text(
                    "SELECT payload_hash, result FROM command_results "
                    "WHERE organization_id=:org AND command_type=:command "
                    "AND idempotency_key=:key"
                ),
                params,
            )
            .mappings()
            .first()
        )
        if prior:
            if prior["payload_hash"] != digest:
                raise BusinessError("IDEMPOTENCY_CONFLICT", 409)
            return prior["result"]
        self.digest = digest
        return None

    def finish(self, actor: Actor, command: str, key: UUID, result: dict):
        self.conn.execute(
            text(
                "INSERT INTO command_results "
                "(organization_id,command_type,idempotency_key,payload_hash,result) "
                "VALUES (:org,:command,:key,:hash,CAST(:result AS jsonb))"
            ),
            {
                "org": actor.organization_id,
                "command": command,
                "key": key,
                "hash": self.digest,
                "result": json.dumps(result),
            },
        )

    def audit(self, actor: Actor, command: str, entity_id: UUID):
        self.conn.execute(
            text(
                "INSERT INTO audit_events "
                "(id,organization_id,actor_id,command_type,entity_id) "
                "VALUES (:id,:org,:actor,:command,:entity)"
            ),
            {
                "id": uuid7(),
                "org": actor.organization_id,
                "actor": actor.user_id,
                "command": command,
                "entity": entity_id,
            },
        )
