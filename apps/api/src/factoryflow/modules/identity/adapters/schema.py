DDL = """
CREATE TABLE organizations (
 id uuid PRIMARY KEY, name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 200),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE users (
 id uuid PRIMARY KEY, organization_id uuid NOT NULL REFERENCES organizations(id),
 username text NOT NULL UNIQUE CHECK (length(btrim(username)) BETWEEN 1 AND 100),
 password_hash text NOT NULL, role text NOT NULL CHECK (role IN ('admin','operator','viewer')),
 active boolean NOT NULL DEFAULT true, failed_attempts integer NOT NULL DEFAULT 0,
 locked_until timestamptz, UNIQUE (organization_id,id)
);
CREATE TABLE sessions (
 token_hash char(64) PRIMARY KEY, organization_id uuid NOT NULL, user_id uuid NOT NULL,
 csrf_token text NOT NULL, expires_at timestamptz NOT NULL,
 FOREIGN KEY (organization_id,user_id) REFERENCES users(organization_id,id)
);
CREATE INDEX sessions_expiry ON sessions(expires_at);
"""
