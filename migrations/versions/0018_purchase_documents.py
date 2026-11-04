"""Independent supplier purchase source review and optional prices for printing."""

from alembic import op
from factoryflow.modules.documents.adapters.purchase_source_schema import DDL as SOURCE_DDL
from factoryflow.modules.purchasing.adapters.document_schema import DDL as PURCHASE_DDL

revision = "0018_purchase_documents"
down_revision = "0017_production"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(SOURCE_DDL)
    op.execute(PURCHASE_DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
