"""Statement evidence, approval, settlement and review lifecycle."""

from alembic import op
from factoryflow.modules.statements.adapters.lifecycle_schema import DDL

revision = "0010_statement_lifecycle"
down_revision = "0009_work_archives"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
