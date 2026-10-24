"""Customer external delivery or return reference metadata."""

from alembic import op
from factoryflow.modules.statements.adapters.external_number_schema import DDL

revision = "0012_external_document_number"
down_revision = "0011_customer_templates"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
