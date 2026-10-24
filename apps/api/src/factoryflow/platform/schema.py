DDL = """
CREATE TABLE command_results (
 organization_id uuid NOT NULL REFERENCES organizations(id), command_type text NOT NULL,
 idempotency_key uuid NOT NULL, payload_hash char(64) NOT NULL, result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,command_type,idempotency_key)
);
CREATE TABLE audit_events (
 id uuid PRIMARY KEY, organization_id uuid NOT NULL, actor_id uuid NOT NULL,
 command_type text NOT NULL, entity_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE FUNCTION reject_evidence_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'immutable evidence' USING ERRCODE='23000'; END; $$;
"""
