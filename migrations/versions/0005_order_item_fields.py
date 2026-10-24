"""Add separate source item identity without rewriting any immutable evidence."""

from alembic import op

revision = "0005_order_item_fields"
down_revision = "0004_document_extraction"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      ALTER TABLE order_lines ADD COLUMN item_code text
        CHECK (item_code IS NULL OR length(item_code) <= 100);
      ALTER TABLE order_lines ADD COLUMN item_name text
        CHECK (item_name IS NULL OR length(item_name) <= 500);
      ALTER TABLE order_lines ADD COLUMN specification text
        CHECK (specification IS NULL OR length(specification) <= 1000);
      ALTER TABLE confirmed_revisions DROP CONSTRAINT confirmed_revisions_schema_version_check;
      ALTER TABLE confirmed_revisions ADD CONSTRAINT confirmed_revisions_schema_version_check
        CHECK (schema_version IN (1,2,3));
    """)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
