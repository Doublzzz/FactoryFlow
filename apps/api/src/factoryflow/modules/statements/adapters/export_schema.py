DDL = """
ALTER TABLE statements DROP CONSTRAINT statements_status_check;
ALTER TABLE statements ADD CHECK (status IN ('draft','abandoned','void'));
ALTER TABLE statement_customer_settings ADD COLUMN template_id text NOT NULL
 DEFAULT 'standard-v1' CHECK (template_id IN ('standard-v1','delivery-v1'));
CREATE TABLE statement_exports (
 organization_id uuid NOT NULL, id uuid NOT NULL, statement_id uuid NOT NULL,
 customer_id uuid NOT NULL, statement_version integer NOT NULL CHECK(statement_version>0),
 template_id text NOT NULL, template_version integer NOT NULL CHECK(template_version=1),
 snapshot jsonb NOT NULL, status text NOT NULL DEFAULT 'pending'
 CHECK(status IN ('pending','failed','ready')), object_hash text, file_hash text,
 error_code text, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 CHECK ((status='ready' AND object_hash ~ '^[0-9a-f]{64}$'
 AND file_hash ~ '^[0-9a-f]{64}$' AND object_hash IS NOT NULL AND file_hash IS NOT NULL)
 OR (status<>'ready' AND object_hash IS NULL AND file_hash IS NULL))
);
CREATE INDEX statement_exports_parent ON statement_exports(organization_id,statement_id,id);
CREATE FUNCTION guard_statement_export() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain export' USING ERRCODE='23000'; END IF;
 IF TG_OP='UPDATE' THEN
  IF OLD.status='ready' OR (to_jsonb(NEW)-ARRAY['status','object_hash','file_hash','error_code'])
  IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','object_hash','file_hash','error_code']) THEN
   RAISE EXCEPTION 'immutable export' USING ERRCODE='23000'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER statement_export_guard BEFORE UPDATE OR DELETE ON statement_exports
 FOR EACH ROW EXECUTE FUNCTION guard_statement_export();
"""
