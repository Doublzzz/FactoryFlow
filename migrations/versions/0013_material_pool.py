"""Optional material identity; does not backfill orders or create inventory."""

from alembic import op

revision = "0013_material_pool"
down_revision = "0012_external_document_number"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE SEQUENCE material_code_seq;
    CREATE TABLE materials (
      organization_id uuid NOT NULL REFERENCES organizations(id), id uuid NOT NULL,
      own_code text NOT NULL CHECK(length(btrim(own_code)) BETWEEN 1 AND 100),
      name text NOT NULL CHECK(length(btrim(name)) BETWEEN 1 AND 500),
      specification text CHECK(length(specification)<=1000), unit text CHECK(length(unit)<=40),
      active boolean NOT NULL DEFAULT true, version integer NOT NULL DEFAULT 1 CHECK(version>0),
      created_by uuid NOT NULL, updated_by uuid NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY(organization_id,id),
      CONSTRAINT materials_code_unique UNIQUE(organization_id,own_code),
      FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
      FOREIGN KEY(organization_id,updated_by) REFERENCES users(organization_id,id)
    );
    CREATE TABLE customer_material_codes (
      organization_id uuid NOT NULL, customer_id uuid NOT NULL,
      customer_code text NOT NULL CHECK(length(btrim(customer_code)) BETWEEN 1 AND 100),
      material_id uuid NOT NULL, item_name text CHECK(length(item_name)<=500),
      specification text CHECK(length(specification)<=1000), canonical_unit text,
      version integer NOT NULL DEFAULT 1 CHECK(version>0),
      PRIMARY KEY(organization_id,customer_id,customer_code),
      FOREIGN KEY(organization_id,customer_id) REFERENCES customers(organization_id,id),
      FOREIGN KEY(organization_id,material_id) REFERENCES materials(organization_id,id)
    );
    CREATE INDEX material_codes_target ON customer_material_codes(organization_id,material_id);
    ALTER TABLE order_lines ADD COLUMN material_id uuid;
    ALTER TABLE order_lines ADD CONSTRAINT order_line_material_owner
      FOREIGN KEY(organization_id,material_id) REFERENCES materials(organization_id,id);
    """)


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a verified backup")
