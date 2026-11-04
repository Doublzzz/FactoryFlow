"""Connect orders, raw movements and finished stock with immutable production facts."""

from alembic import op
from factoryflow.modules.inventory.adapters.production_schema import DDL as INVENTORY_DDL
from factoryflow.modules.production.adapters.schema import DDL, LINK_DDL

revision = "0017_production"
down_revision = "0016_purchasing_raw_inventory"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)
    op.execute(INVENTORY_DDL)
    op.execute(LINK_DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
