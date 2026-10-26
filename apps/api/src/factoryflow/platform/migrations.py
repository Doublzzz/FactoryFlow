"""Explicit deployment operation, not used by application startup."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text


def upgrade_database(engine, repository_root: Path, runtime_role: str = "ff_runtime"):
    if runtime_role != "ff_runtime":
        raise ValueError("Only the explicitly provisioned runtime role is supported")
    config = Config(str(repository_root / "alembic.ini"))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")
        conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        conn.execute(text("GRANT USAGE ON SCHEMA public TO ff_runtime"))
        conn.execute(text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO ff_runtime"))
        conn.execute(
            text(
                "GRANT INSERT ON organizations,users,sessions,customers,orders,order_lines,"
                "confirmed_revisions,order_events,command_results,audit_events,"
                "deliveries,delivery_lines,fulfillment_actions,"
                "source_files,extraction_runs,source_imports TO ff_runtime"
            )
        )
        conn.execute(text("GRANT UPDATE ON users,orders TO ff_runtime"))
        conn.execute(text("GRANT UPDATE(delivered_quantity) ON order_lines TO ff_runtime"))
        conn.execute(text("GRANT UPDATE(material_id) ON order_lines TO ff_runtime"))
        conn.execute(text("GRANT INSERT ON materials,customer_material_codes TO ff_runtime"))
        conn.execute(
            text(
                "GRANT INSERT ON inventory_accounts,inventory_ledger,delivery_inventory_snapshots "
                "TO ff_runtime"
            )
        )
        # FOR UPDATE needs one UPDATE privilege. The trigger rejects identity and direct
        # projection writes; balances are changed only by the controlled ledger trigger.
        conn.execute(text("GRANT UPDATE(material_id) ON inventory_accounts TO ff_runtime"))
        conn.execute(text("REVOKE UPDATE ON materials,customer_material_codes FROM ff_runtime"))
        conn.execute(
            text(
                "GRANT UPDATE(own_code,name,specification,unit,active,version,"
                "updated_by,updated_at) ON materials TO ff_runtime"
            )
        )
        conn.execute(
            text(
                "GRANT UPDATE(material_id,item_name,specification,canonical_unit,version) "
                "ON customer_material_codes TO ff_runtime"
            )
        )
        conn.execute(text("GRANT USAGE,SELECT ON SEQUENCE material_code_seq TO ff_runtime"))
        conn.execute(
            text("GRANT UPDATE(status,version,void_reason,voided_at) ON deliveries TO ff_runtime")
        )
        conn.execute(text("GRANT DELETE ON sessions TO ff_runtime"))
        conn.execute(
            text(
                "GRANT INSERT,UPDATE ON statements,statement_lines,statement_balances,"
                "statement_customer_settings,statement_exports TO ff_runtime"
            )
        )
        conn.execute(text("GRANT INSERT ON statement_events TO ff_runtime"))
        conn.execute(text("GRANT INSERT ON statement_templates TO ff_runtime"))
        conn.execute(
            text("GRANT INSERT ON statement_evidence,statement_lifecycle_events TO ff_runtime")
        )
        conn.execute(
            text(
                "GRANT INSERT,UPDATE ON statement_approvals,statement_allocations,"
                "statement_reviews,statement_review_transfers TO ff_runtime"
            )
        )
        conn.execute(text("GRANT INSERT ON delivery_layout_versions TO ff_runtime"))
        conn.execute(text("GRANT INSERT ON archive_settings,archive_batches TO ff_runtime"))
        conn.execute(
            text(
                "GRANT UPDATE(status,object_hash,file_hash,error_code) "
                "ON archive_batches TO ff_runtime"
            )
        )
        conn.execute(text("GRANT UPDATE(id) ON customers TO ff_runtime"))
