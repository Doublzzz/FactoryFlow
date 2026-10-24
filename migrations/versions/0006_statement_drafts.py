"""Partial draft allocations with database-enforced source capacity."""

from alembic import op
from factoryflow.modules.statements.adapters.schema import DDL

revision = "0006_statement_drafts"
down_revision = "0005_order_item_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
