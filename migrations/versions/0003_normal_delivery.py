"""Normal delivery snapshots, reversible ledger and exact order projection."""

from alembic import op
from factoryflow.modules.fulfillment.adapters.schema import DDL

revision = "0003_normal_delivery"
down_revision = "0002_quantity_scale"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
