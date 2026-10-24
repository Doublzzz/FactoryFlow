DDL = """
CREATE TABLE customers (
 id uuid NOT NULL, organization_id uuid NOT NULL REFERENCES organizations(id),
 full_name text NOT NULL CHECK (length(btrim(full_name)) BETWEEN 1 AND 200),
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (organization_id,id),
 CONSTRAINT customers_name_unique UNIQUE (organization_id,full_name)
);
"""
