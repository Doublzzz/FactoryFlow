"""Supplier receipts and raw inventory share the existing atomic stock ledger."""

from alembic import op
from factoryflow.modules.inventory.adapters.supply_schema import DDL as INVENTORY_DDL
from factoryflow.modules.materials.adapters.kind_schema import DDL as MATERIAL_DDL
from factoryflow.modules.purchasing.adapters.schema import DDL, LINK_DDL

revision = "0016_purchasing_raw_inventory"
down_revision = "0015_order_currencies"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(MATERIAL_DDL)
    op.execute(DDL)
    op.execute(INVENTORY_DDL)
    op.execute(LINK_DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
