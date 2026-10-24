DDL = """
CREATE TABLE confirmed_revisions (
 id uuid NOT NULL, organization_id uuid NOT NULL, customer_id uuid NOT NULL, order_id uuid NOT NULL,
 parent_id uuid, revision_number integer NOT NULL CHECK (revision_number > 0),
 schema_version integer NOT NULL CHECK (schema_version = 1),
 blob_hash char(64) NOT NULL CHECK (blob_hash ~ '^[0-9a-f]{64}$'),
 actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,order_id,id),
 UNIQUE (organization_id,id,order_id,customer_id),
 UNIQUE (organization_id,order_id,revision_number),
 FOREIGN KEY (organization_id,customer_id) REFERENCES customers(organization_id,id),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id),
 FOREIGN KEY (organization_id,order_id,parent_id)
   REFERENCES confirmed_revisions(organization_id,order_id,id)
);
"""
