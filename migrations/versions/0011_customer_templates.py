"""Immutable customer Excel templates and pinned export references."""

from alembic import op
from factoryflow.modules.statements.adapters.template_schema import DDL

revision = "0011_customer_templates"
down_revision = "0010_statement_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
