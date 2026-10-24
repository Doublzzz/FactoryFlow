"""Reject textual numeric scale above three, including trailing zeroes."""

from alembic import op

revision = "0002_quantity_scale"
down_revision = "0001_local_orders"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE order_lines ADD CONSTRAINT order_lines_quantity_scale "
        "CHECK (scale(quantity)<=3)"
    )
    op.execute(
        "ALTER TABLE order_lines ADD CONSTRAINT order_lines_delivered_scale "
        "CHECK (scale(delivered_quantity)<=3)"
    )
    op.execute("REVOKE UPDATE ON order_lines FROM ff_runtime")


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
