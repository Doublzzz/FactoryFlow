"""Immutable local file sources and extraction provenance."""

from alembic import op
from factoryflow.modules.documents.adapters.extraction_schema import DDL

revision = "0004_document_extraction"
down_revision = "0003_normal_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(DDL)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
