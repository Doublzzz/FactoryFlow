"""Explicit CNY/USD orders and separate statement chains; retain historical bytes."""

from alembic import op
from factoryflow.modules.orders.adapters.currency_schema import DDL as ORDERS
from factoryflow.modules.statements.adapters.currency_schema import DDL as STATEMENTS

revision = "0015_order_currencies"
down_revision = "0014_finished_goods_inventory"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(ORDERS)
    op.execute(STATEMENTS)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
