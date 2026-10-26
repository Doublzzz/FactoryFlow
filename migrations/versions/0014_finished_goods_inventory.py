"""Optional finished goods; old deliveries retain no inventory decision or retroactive effects."""

from alembic import op
from factoryflow.modules.fulfillment.adapters.inventory_schema import DDL as DECISIONS
from factoryflow.modules.inventory.adapters.schema import DDL as INVENTORY

revision = "0014_finished_goods_inventory"
down_revision = "0013_material_pool"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(INVENTORY)
    op.execute(DECISIONS)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
