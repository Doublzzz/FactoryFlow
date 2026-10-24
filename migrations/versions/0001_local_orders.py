"""Local identity, confirmation evidence and first order lifecycle."""

from alembic import op
from factoryflow.modules.customers.adapters.schema import DDL as CUSTOMERS
from factoryflow.modules.documents.adapters.schema import DDL as DOCUMENTS
from factoryflow.modules.identity.adapters.schema import DDL as IDENTITY
from factoryflow.modules.orders.adapters.schema import DDL as ORDERS
from factoryflow.platform.schema import DDL as PLATFORM

revision = "0001_local_orders"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for ddl in (IDENTITY, CUSTOMERS, DOCUMENTS, ORDERS, PLATFORM):
        op.execute(ddl)
    for table in ("confirmed_revisions", "order_events", "audit_events", "command_results"):
        op.execute(
            f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_evidence_change()"
        )


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
