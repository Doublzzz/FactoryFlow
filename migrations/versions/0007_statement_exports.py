"""Immutable reconciliation exports and customer layout preference."""

from alembic import op
from factoryflow.modules.statements.adapters.export_schema import DDL

revision = "0007_statement_exports"
down_revision = "0006_statement_drafts"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
