DDL = """
CREATE TABLE archive_settings (
 organization_id uuid NOT NULL REFERENCES organizations(id),
 version integer NOT NULL CHECK(version>0),
 rule text NOT NULL CHECK(rule IN ('date','customer','month_customer')),
 actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,version),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE FUNCTION guard_archive_settings() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable archive rule' USING ERRCODE='23000'; END; $$;
CREATE TRIGGER archive_settings_guard BEFORE UPDATE OR DELETE ON archive_settings
 FOR EACH ROW EXECUTE FUNCTION guard_archive_settings();
CREATE TABLE archive_batches (
 organization_id uuid NOT NULL REFERENCES organizations(id), id uuid NOT NULL,
 fingerprint text NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
 rule text NOT NULL CHECK(rule IN ('date','customer','month_customer')),
 input_hash text NOT NULL CHECK(input_hash ~ '^[0-9a-f]{64}$'),
 manifest jsonb NOT NULL, actor_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','failed','ready')),
 object_hash text, file_hash text, error_code text,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,fingerprint),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 CHECK ((status='ready' AND object_hash IS NOT NULL AND file_hash IS NOT NULL
 AND object_hash ~ '^[0-9a-f]{64}$' AND file_hash ~ '^[0-9a-f]{64}$' AND error_code IS NULL)
 OR (status<>'ready' AND object_hash IS NULL AND file_hash IS NULL))
);
CREATE FUNCTION guard_archive_batch() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain archive' USING ERRCODE='23000'; END IF;
 IF OLD.status='ready' OR (to_jsonb(NEW)-ARRAY['status','object_hash','file_hash','error_code'])
 IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','object_hash','file_hash','error_code']) THEN
 RAISE EXCEPTION 'immutable archive input' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER archive_batch_guard BEFORE UPDATE OR DELETE ON archive_batches
 FOR EACH ROW EXECUTE FUNCTION guard_archive_batch();
"""
