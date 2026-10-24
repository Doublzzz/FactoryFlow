DDL = """
CREATE TABLE statement_templates (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 version integer NOT NULL CHECK(version>0), name text NOT NULL CHECK(length(name) BETWEEN 1 AND 80),
 object_hash text NOT NULL CHECK(object_hash ~ '^[0-9a-f]{64}$'),
 file_hash text NOT NULL CHECK(file_hash ~ '^[0-9a-f]{64}$'), mapping jsonb NOT NULL,
 actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,customer_id,version),
 UNIQUE(organization_id,customer_id,id), UNIQUE(organization_id,customer_id,id,version),
 FOREIGN KEY(organization_id,customer_id) REFERENCES customers(organization_id,id),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE FUNCTION guard_statement_template() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'immutable customer template' USING ERRCODE='23000';
END; $$;
CREATE TRIGGER statement_template_guard BEFORE UPDATE OR DELETE ON statement_templates
 FOR EACH ROW EXECUTE FUNCTION guard_statement_template();
ALTER TABLE statement_customer_settings
 DROP CONSTRAINT statement_customer_settings_template_id_check;
ALTER TABLE statement_customer_settings ADD COLUMN customer_template_id uuid;
ALTER TABLE statement_customer_settings ADD CHECK (
 (template_id IN ('standard-v1','delivery-v1') AND customer_template_id IS NULL) OR
 (template_id='customer-v1' AND customer_template_id IS NOT NULL)
);
ALTER TABLE statement_customer_settings
 ADD FOREIGN KEY(organization_id,customer_id,customer_template_id)
 REFERENCES statement_templates(organization_id,customer_id,id);
ALTER TABLE statement_exports DROP CONSTRAINT statement_exports_template_version_check;
ALTER TABLE statement_exports ADD COLUMN customer_template_id uuid;
ALTER TABLE statement_exports ADD CHECK (
 (template_id IN ('standard-v1','delivery-v1') AND template_version=1
  AND customer_template_id IS NULL) OR
 (template_id='customer-v1' AND template_version>0 AND customer_template_id IS NOT NULL)
);
ALTER TABLE statement_exports
 ADD FOREIGN KEY(organization_id,customer_id,customer_template_id,template_version)
 REFERENCES statement_templates(organization_id,customer_id,id,version);
"""
