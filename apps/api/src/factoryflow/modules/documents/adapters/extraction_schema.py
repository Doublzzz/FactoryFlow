DDL = """
CREATE TABLE source_files (
 id uuid NOT NULL, organization_id uuid NOT NULL, actor_id uuid NOT NULL,
 filename text NOT NULL CHECK (length(filename) BETWEEN 1 AND 180),
 media_type text NOT NULL CHECK (media_type IN ('image/png','image/jpeg','application/pdf')),
 byte_size integer NOT NULL CHECK (byte_size BETWEEN 1 AND 10485760),
 original_sha256 char(64) NOT NULL CHECK (original_sha256 ~ '^[0-9a-f]{64}$'),
 blob_hash char(64) NOT NULL CHECK (blob_hash ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,original_sha256),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE TABLE extraction_runs (
 id uuid NOT NULL, organization_id uuid NOT NULL, source_id uuid NOT NULL, actor_id uuid NOT NULL,
 status text NOT NULL CHECK (status IN ('ready','failed')),
 trace_hash char(64) NOT NULL CHECK (trace_hash ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,source_id,id),
 FOREIGN KEY (organization_id,source_id) REFERENCES source_files(organization_id,id),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE TABLE source_imports (
 organization_id uuid NOT NULL, source_id uuid NOT NULL, extraction_id uuid NOT NULL,
 revision_id uuid NOT NULL, order_id uuid NOT NULL,
 PRIMARY KEY (organization_id,source_id),
 FOREIGN KEY (organization_id,source_id,extraction_id)
   REFERENCES extraction_runs(organization_id,source_id,id),
 FOREIGN KEY (organization_id,revision_id,order_id)
   REFERENCES confirmed_revisions(organization_id,id,order_id)
   DEFERRABLE INITIALLY DEFERRED
);
CREATE FUNCTION protect_document_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'Document evidence is immutable'; END $$;
CREATE TRIGGER source_files_immutable BEFORE UPDATE OR DELETE ON source_files
 FOR EACH ROW EXECUTE FUNCTION protect_document_source();
CREATE TRIGGER extraction_runs_immutable BEFORE UPDATE OR DELETE ON extraction_runs
 FOR EACH ROW EXECUTE FUNCTION protect_document_source();
CREATE TRIGGER source_imports_immutable BEFORE UPDATE OR DELETE ON source_imports
 FOR EACH ROW EXECUTE FUNCTION protect_document_source();
ALTER TABLE confirmed_revisions DROP CONSTRAINT confirmed_revisions_schema_version_check;
ALTER TABLE confirmed_revisions ADD CONSTRAINT confirmed_revisions_schema_version_check
 CHECK (schema_version IN (1,2));
"""
