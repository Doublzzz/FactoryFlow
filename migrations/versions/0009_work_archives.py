"""Rebuildable work archives with immutable inputs."""

from alembic import op
from factoryflow.modules.archives.adapters.schema import DDL

revision = "0009_work_archives"
down_revision = "0008_delivery_layout"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
