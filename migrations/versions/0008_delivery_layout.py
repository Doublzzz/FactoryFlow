"""Organization-scoped, append-only delivery layout versions."""

from alembic import op
from factoryflow.modules.fulfillment.adapters.layout_schema import DDL

revision = "0008_delivery_layout"
down_revision = "0007_statement_exports"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
