DDL = """
CREATE TABLE delivery_layout_versions (
 organization_id uuid NOT NULL REFERENCES organizations(id),
 version integer NOT NULL CHECK(version>0),
 schema_version integer NOT NULL DEFAULT 1 CHECK(schema_version=1),
 config jsonb NOT NULL CHECK(jsonb_typeof(config)='object'),
 actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,version),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE FUNCTION guard_delivery_layout_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'immutable delivery layout version' USING ERRCODE='23000';
END; $$;
CREATE TRIGGER delivery_layout_version_guard BEFORE UPDATE OR DELETE ON delivery_layout_versions
 FOR EACH ROW EXECUTE FUNCTION guard_delivery_layout_version();
"""
