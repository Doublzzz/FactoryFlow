"""Additive lifecycle migration; old migration DDL remains frozen."""

DDL = """
ALTER TABLE statements DROP CONSTRAINT statements_status_check;
ALTER TABLE statements ADD CHECK(status IN ('draft','abandoned','void','confirmed'));
ALTER TABLE statements ADD COLUMN fees_confirmed boolean NOT NULL DEFAULT false;
ALTER TABLE statements ADD COLUMN reconfirmation text NOT NULL DEFAULT 'unknown'
 CHECK(reconfirmation IN ('unknown','not_required','received'));

CREATE TABLE statement_evidence (
 organization_id uuid NOT NULL, id uuid NOT NULL, statement_id uuid NOT NULL,
 customer_id uuid NOT NULL, kind text NOT NULL CHECK(kind IN ('sent','feedback')),
 export_id uuid, statement_version integer NOT NULL CHECK(statement_version>0),
 person text NOT NULL, occurred_on date NOT NULL, note text NOT NULL DEFAULT '',
 object_hash text CHECK(object_hash ~ '^[0-9a-f]{64}$'), media_type text, filename text,
 actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,id,statement_id,customer_id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,export_id) REFERENCES statement_exports(organization_id,id),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 CHECK(length(btrim(person)) BETWEEN 1 AND 500),
 CHECK((kind='sent' AND export_id IS NOT NULL) OR
 (kind='feedback' AND ((object_hash IS NOT NULL AND media_type IN
 ('image/png','image/jpeg','application/pdf') AND filename IS NOT NULL) OR
 (object_hash IS NULL AND media_type IS NULL AND filename IS NULL AND
 length(btrim(note)) BETWEEN 1 AND 500))))
);
CREATE TABLE statement_approvals (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 statement_id uuid NOT NULL, delivery_id uuid NOT NULL, order_line_id uuid NOT NULL,
 sent_id uuid NOT NULL, feedback_id uuid NOT NULL,
 quantity numeric NOT NULL CHECK(quantity>=0 AND quantity<=9223372036854775.807
 AND scale(quantity)<=3), unit_price numeric NOT NULL CHECK(unit_price>=0
 AND unit_price<=999999999999.9999 AND scale(unit_price)<=4),
 target_start date NOT NULL, target_end date NOT NULL CHECK(target_end>=target_start),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), reason text NOT NULL,
 source jsonb NOT NULL, correction jsonb,
 review_quantity numeric NOT NULL DEFAULT 0 CHECK(review_quantity>=0
 AND review_quantity<=9223372036854775.807 AND scale(review_quantity)<=3), actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,delivery_id,order_line_id)
 REFERENCES delivery_lines(organization_id,delivery_id,order_line_id),
 FOREIGN KEY(organization_id,sent_id,statement_id,customer_id)
 REFERENCES statement_evidence(organization_id,id,statement_id,customer_id),
 FOREIGN KEY(organization_id,feedback_id,statement_id,customer_id)
 REFERENCES statement_evidence(organization_id,id,statement_id,customer_id),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 CHECK(length(btrim(reason)) BETWEEN 1 AND 500)
);
CREATE TABLE statement_allocations (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 approval_id uuid NOT NULL, statement_id uuid NOT NULL,
 quantity numeric NOT NULL CHECK(quantity>0 AND quantity<=9223372036854775.807
 AND scale(quantity)<=3), unit_price numeric NOT NULL CHECK(unit_price>=0
 AND unit_price<=999999999999.9999 AND scale(unit_price)<=4),
 status text NOT NULL CHECK(status IN ('reserved','settled','released','superseded')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), settlement_version integer,
 superseded_version integer, reason text NOT NULL, actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(organization_id,id),
 FOREIGN KEY(organization_id,approval_id,customer_id)
 REFERENCES statement_approvals(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,statement_id,settlement_version)
 REFERENCES statement_events(organization_id,statement_id,version) DEFERRABLE INITIALLY DEFERRED,
 FOREIGN KEY(organization_id,statement_id,superseded_version)
 REFERENCES statement_events(organization_id,statement_id,version) DEFERRABLE INITIALLY DEFERRED,
 CHECK((status IN ('reserved','released') AND settlement_version IS NULL AND
 superseded_version IS NULL) OR (status='settled' AND settlement_version>0 AND
 settlement_version IS NOT NULL AND superseded_version IS NULL) OR
 (status='superseded' AND settlement_version>0 AND settlement_version IS NOT NULL AND
 superseded_version>settlement_version AND superseded_version IS NOT NULL)),
 CHECK(length(btrim(reason)) BETWEEN 1 AND 500)
);
CREATE TABLE statement_reviews (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 statement_id uuid NOT NULL, delivery_id uuid NOT NULL, order_line_id uuid NOT NULL,
 quantity numeric NOT NULL CHECK(quantity>0 AND quantity<=9223372036854775.807
 AND scale(quantity)<=3), reason text NOT NULL, source jsonb NOT NULL,
 actor_id uuid NOT NULL, version integer NOT NULL DEFAULT 1 CHECK(version>0),
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(organization_id,id),
 UNIQUE(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,delivery_id,order_line_id)
 REFERENCES delivery_lines(organization_id,delivery_id,order_line_id),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 CHECK(length(btrim(reason)) BETWEEN 1 AND 500)
);
CREATE TABLE statement_review_transfers (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 review_id uuid NOT NULL, statement_id uuid NOT NULL, approval_id uuid,
 quantity numeric NOT NULL CHECK(quantity>0 AND quantity<=9223372036854775.807
 AND scale(quantity)<=3), status text NOT NULL CHECK(status IN ('claimed','approved','released')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0), reason text NOT NULL,
 actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id),
 FOREIGN KEY(organization_id,review_id,customer_id)
 REFERENCES statement_reviews(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY(organization_id,approval_id,customer_id)
 REFERENCES statement_approvals(organization_id,id,customer_id),
 CHECK((status='approved' AND approval_id IS NOT NULL) OR
 (status IN ('claimed','released') AND approval_id IS NULL)),
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id),
 CHECK(length(btrim(reason)) BETWEEN 1 AND 500)
);
CREATE TABLE statement_lifecycle_events (
 organization_id uuid NOT NULL, id uuid NOT NULL DEFAULT gen_random_uuid(),
 kind text NOT NULL CHECK(kind IN ('statement_approvals','statement_allocations',
 'statement_reviews','statement_review_transfers')),
 entity_id uuid NOT NULL, version integer NOT NULL CHECK(version>0), snapshot jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(organization_id,id),
 UNIQUE(organization_id,kind,entity_id,version)
);
CREATE TRIGGER statement_evidence_immutable BEFORE UPDATE OR DELETE ON statement_evidence
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
CREATE TRIGGER statement_lifecycle_events_immutable BEFORE UPDATE OR DELETE
 ON statement_lifecycle_events FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();

CREATE FUNCTION validate_lifecycle_snapshot() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_entity jsonb;
BEGIN
 IF NEW.kind NOT IN ('statement_approvals','statement_allocations','statement_reviews',
 'statement_review_transfers') THEN
 RAISE EXCEPTION 'invalid lifecycle entity kind' USING ERRCODE='23000'; END IF;
 EXECUTE format('SELECT to_jsonb(e) FROM %I e WHERE organization_id=$1 AND id=$2',NEW.kind)
 INTO current_entity USING NEW.organization_id,NEW.entity_id;
 IF current_entity IS NULL OR NEW.snapshot IS DISTINCT FROM current_entity OR
 NEW.version<>(current_entity->>'version')::integer THEN
 RAISE EXCEPTION 'invalid lifecycle snapshot' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lifecycle_snapshot_validate BEFORE INSERT ON statement_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION validate_lifecycle_snapshot();

CREATE FUNCTION guard_lifecycle_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.kind='sent' AND NOT EXISTS(SELECT 1 FROM statement_exports e WHERE
 e.organization_id=NEW.organization_id AND e.id=NEW.export_id AND
 e.statement_id=NEW.statement_id AND e.customer_id=NEW.customer_id AND
 e.statement_version=NEW.statement_version AND e.status='ready') THEN
 RAISE EXCEPTION 'sent evidence requires ready matching export' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER lifecycle_evidence_guard BEFORE INSERT ON statement_evidence
 FOR EACH ROW EXECUTE FUNCTION guard_lifecycle_evidence();

CREATE FUNCTION guard_lifecycle_entity() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE delivery uuid; line uuid; customer uuid; policy jsonb; allowed text[];
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain lifecycle entity' USING ERRCODE='23000'; END IF;
 IF TG_TABLE_NAME IN ('statement_approvals','statement_reviews') THEN
 delivery:=NEW.delivery_id; line:=NEW.order_line_id;
 ELSIF TG_TABLE_NAME='statement_allocations' THEN
 SELECT delivery_id,order_line_id INTO delivery,line FROM statement_approvals
 WHERE organization_id=NEW.organization_id AND id=NEW.approval_id;
 ELSE
 SELECT delivery_id,order_line_id INTO delivery,line FROM statement_reviews
 WHERE organization_id=NEW.organization_id AND id=NEW.review_id;
 END IF;
 SELECT d.customer_id,dl.quantity_policy INTO customer,policy FROM deliveries d
 JOIN delivery_lines dl ON dl.organization_id=d.organization_id AND dl.delivery_id=d.id
 WHERE d.organization_id=NEW.organization_id AND d.id=delivery AND dl.order_line_id=line
 AND d.status='active' FOR UPDATE OF d;
 IF customer IS DISTINCT FROM NEW.customer_id OR
 (policy->>'mode'='INTEGER_ONLY' AND NEW.quantity<>trunc(NEW.quantity)) THEN
 RAISE EXCEPTION 'invalid lifecycle source' USING ERRCODE='23000'; END IF;
 PERFORM 1 FROM statements WHERE organization_id=NEW.organization_id
 AND id=NEW.statement_id FOR UPDATE;
 IF TG_OP='INSERT' AND NEW.version<>1 THEN
 RAISE EXCEPTION 'initial lifecycle version' USING ERRCODE='23000'; END IF;
 IF TG_OP='UPDATE' THEN
 allowed:=CASE TG_TABLE_NAME
 WHEN 'statement_approvals' THEN ARRAY['quantity','unit_price','target_start','target_end',
 'version','reason','actor_id','correction']
 WHEN 'statement_allocations' THEN ARRAY['status','version','settlement_version',
 'superseded_version','reason','actor_id']
 WHEN 'statement_review_transfers' THEN ARRAY['status','version','reason','actor_id','approval_id']
 ELSE ARRAY['version'] END;
 IF NEW.version<>OLD.version+1 OR (to_jsonb(NEW)-allowed) IS DISTINCT FROM
 (to_jsonb(OLD)-allowed) THEN
 RAISE EXCEPTION 'immutable lifecycle source or stale version' USING ERRCODE='23000'; END IF;
 IF TG_TABLE_NAME='statement_allocations' THEN
 IF ((OLD.status='settled' AND NEW.status<>'superseded') OR
 OLD.status IN ('released','superseded') OR
 (OLD.status='reserved' AND NEW.status NOT IN ('settled','released'))) THEN
 RAISE EXCEPTION 'invalid allocation transition' USING ERRCODE='23000'; END IF;
 IF OLD.status='settled' AND
 NEW.settlement_version IS DISTINCT FROM OLD.settlement_version THEN
 RAISE EXCEPTION 'immutable original settlement link' USING ERRCODE='23000'; END IF;
 END IF;
 IF TG_TABLE_NAME='statement_review_transfers' THEN
 IF (OLD.status<>'claimed' OR NEW.status NOT IN ('approved','released')) THEN
 RAISE EXCEPTION 'invalid review transfer transition' USING ERRCODE='23000'; END IF;
 END IF;
 END IF;
 IF TG_TABLE_NAME='statement_approvals' THEN
 IF TG_OP='INSERT' AND NEW.review_quantity>NEW.quantity THEN
 RAISE EXCEPTION 'review recognition exceeds original approval' USING ERRCODE='23000'; END IF;
 IF NEW.correction IS NOT NULL AND NOT EXISTS(SELECT 1 FROM statement_evidence e WHERE
 e.organization_id=NEW.organization_id AND e.customer_id=NEW.customer_id AND
 e.kind='feedback' AND e.id=(NEW.correction->>'evidence_id')::uuid) THEN
 RAISE EXCEPTION 'correction requires feedback evidence' USING ERRCODE='23000'; END IF;
 IF NOT EXISTS(SELECT 1 FROM statement_evidence WHERE organization_id=NEW.organization_id
 AND id=NEW.sent_id AND kind='sent') OR NOT EXISTS(SELECT 1 FROM statement_evidence
 WHERE organization_id=NEW.organization_id AND id=NEW.feedback_id AND kind='feedback') THEN
 RAISE EXCEPTION 'approval requires sent and feedback evidence' USING ERRCODE='23000'; END IF;
 END IF;
 RETURN NEW;
END; $$;

CREATE FUNCTION snapshot_lifecycle_entity() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO statement_lifecycle_events(organization_id,kind,entity_id,version,snapshot)
 VALUES(NEW.organization_id,TG_TABLE_NAME,NEW.id,NEW.version,to_jsonb(NEW));
 IF TG_TABLE_NAME='statement_review_transfers' THEN
 UPDATE statement_reviews SET version=version+1
 WHERE organization_id=NEW.organization_id AND id=NEW.review_id;
 END IF;
 RETURN NULL;
END; $$;

CREATE OR REPLACE FUNCTION guard_statement_header() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain statement history' USING ERRCODE='23000'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','version','tax_mode','tax_rate','adjustments',
 'fees_confirmed','reconfirmation']) IS DISTINCT FROM (to_jsonb(OLD)-ARRAY[
 'status','version','tax_mode','tax_rate','adjustments','fees_confirmed','reconfirmation'])
 OR NEW.version<>OLD.version+1 OR
 (OLD.status='confirmed' AND (NEW.status<>'confirmed' OR NEW.fees_confirmed IS DISTINCT FROM
 OLD.fees_confirmed OR NEW.reconfirmation IS DISTINCT FROM OLD.reconfirmation)) THEN
 RAISE EXCEPTION 'invalid statement transition' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION guard_statement_claim() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_claim numeric:=0; new_claim numeric:=0; src record; head record;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain statement source' USING ERRCODE='23000'; END IF;
 IF TG_OP='UPDATE' THEN
 IF (to_jsonb(NEW)-ARRAY['quantity','unit_price','status','reason']) IS DISTINCT FROM
 (to_jsonb(OLD)-ARRAY['quantity','unit_price','status','reason']) THEN
 RAISE EXCEPTION 'immutable statement source' USING ERRCODE='23000'; END IF;
 IF OLD.status='included' THEN old_claim:=OLD.quantity; END IF;
 END IF;
 SELECT d.customer_id,d.status,d.delivery_date,dl.quantity,dl.quantity_policy INTO src
 FROM deliveries d JOIN delivery_lines dl ON d.organization_id=dl.organization_id
 AND d.id=dl.delivery_id WHERE d.organization_id=NEW.organization_id
 AND d.id=NEW.delivery_id AND dl.order_line_id=NEW.order_line_id FOR UPDATE OF d;
 SELECT * INTO head FROM statements WHERE organization_id=NEW.organization_id
 AND id=NEW.statement_id FOR UPDATE;
 IF src.customer_id IS NULL OR src.customer_id IS DISTINCT FROM NEW.customer_id
 OR src.delivery_date>head.period_end THEN
 RAISE EXCEPTION 'invalid statement source' USING ERRCODE='23000'; END IF;
 IF NEW.status='included' THEN
 IF src.status<>'active' OR head.status<>'draft' OR
 (src.quantity_policy->>'mode'='INTEGER_ONLY' AND NEW.quantity<>trunc(NEW.quantity)) THEN
 RAISE EXCEPTION 'invalid statement claim' USING ERRCODE='23000'; END IF;
 new_claim:=NEW.quantity;
 END IF;
 INSERT INTO statement_balances(organization_id,delivery_id,order_line_id,capacity,claimed)
 VALUES(NEW.organization_id,NEW.delivery_id,NEW.order_line_id,src.quantity,0)
 ON CONFLICT DO NOTHING;
 UPDATE statement_balances SET claimed=claimed+new_claim-old_claim
 WHERE organization_id=NEW.organization_id AND delivery_id=NEW.delivery_id
 AND order_line_id=NEW.order_line_id;
 RETURN NEW;
END; $$;

CREATE OR REPLACE FUNCTION check_statement_balance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE org uuid; delivery uuid;
BEGIN
 org:=NEW.organization_id;
 IF TG_TABLE_NAME='deliveries' THEN delivery:=NEW.id; ELSE delivery:=NEW.delivery_id; END IF;
 PERFORM 1 FROM deliveries WHERE organization_id=org AND id=delivery FOR UPDATE;
 IF EXISTS(SELECT 1 FROM statement_balances b JOIN delivery_lines dl
 ON dl.organization_id=b.organization_id AND dl.delivery_id=b.delivery_id
 AND dl.order_line_id=b.order_line_id JOIN deliveries d
 ON d.organization_id=b.organization_id AND d.id=b.delivery_id
 WHERE b.organization_id=org AND b.delivery_id=delivery AND
 (b.capacity<>dl.quantity OR (d.status='void' AND b.claimed<>0) OR b.claimed<>(
 SELECT COALESCE(sum(l.quantity),0) FROM statement_lines l WHERE
 l.organization_id=b.organization_id AND l.delivery_id=b.delivery_id
 AND l.order_line_id=b.order_line_id AND l.status='included') + (
 SELECT COALESCE(sum(a.quantity),0) FROM statement_approvals a WHERE
 a.organization_id=b.organization_id AND a.delivery_id=b.delivery_id
 AND a.order_line_id=b.order_line_id))) THEN
 RAISE EXCEPTION 'statement balance mismatch' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;

CREATE FUNCTION update_approval_claim() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE previous numeric:=0; capacity numeric;
BEGIN
 IF TG_OP='UPDATE' THEN previous:=OLD.quantity; END IF;
 SELECT quantity INTO capacity FROM delivery_lines WHERE organization_id=NEW.organization_id
 AND delivery_id=NEW.delivery_id AND order_line_id=NEW.order_line_id;
 INSERT INTO statement_balances(organization_id,delivery_id,order_line_id,capacity,claimed)
 VALUES(NEW.organization_id,NEW.delivery_id,NEW.order_line_id,capacity,0) ON CONFLICT DO NOTHING;
 UPDATE statement_balances SET claimed=claimed+NEW.quantity-previous
 WHERE organization_id=NEW.organization_id AND delivery_id=NEW.delivery_id
 AND order_line_id=NEW.order_line_id;
 RETURN NEW;
END; $$;
CREATE TRIGGER lifecycle_approval_claim AFTER INSERT OR UPDATE ON statement_approvals
 FOR EACH ROW EXECUTE FUNCTION update_approval_claim();

CREATE FUNCTION check_lifecycle_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE org uuid:=NEW.organization_id;
BEGIN
 IF EXISTS(SELECT 1 FROM statement_approvals a WHERE a.organization_id=org AND
 ((SELECT COALESCE(sum(x.quantity),0) FROM statement_allocations x WHERE
 x.organization_id=a.organization_id AND x.approval_id=a.id AND
 x.status IN ('reserved','settled'))>a.quantity OR EXISTS(
 SELECT 1 FROM statement_allocations x JOIN statements s ON
 s.organization_id=x.organization_id AND s.id=x.statement_id WHERE
 x.organization_id=a.organization_id AND x.approval_id=a.id AND
 ((x.status IN ('reserved','settled') AND x.unit_price<>a.unit_price) OR
 (x.status='settled' AND s.status<>'confirmed') OR
 (x.status='reserved' AND (s.status<>'draft' OR s.period_start<>a.target_start
 OR s.period_end<>a.target_end)))))) THEN
 RAISE EXCEPTION 'approval allocation limit or period mismatch' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM statement_reviews r WHERE r.organization_id=org AND
 (SELECT COALESCE(sum(t.quantity),0) FROM statement_review_transfers t WHERE
 t.organization_id=r.organization_id AND t.review_id=r.id AND
 t.status IN ('claimed','approved'))>r.quantity) THEN
 RAISE EXCEPTION 'review transfer limit' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM statement_review_transfers t JOIN statement_reviews r ON
 r.organization_id=t.organization_id AND r.id=t.review_id JOIN statements s ON
 s.organization_id=t.organization_id AND s.id=t.statement_id
 WHERE t.organization_id=org AND t.status='claimed' GROUP BY
 t.statement_id,r.delivery_id,r.order_line_id,s.status HAVING s.status<>'draft' OR
 sum(t.quantity)>(SELECT COALESCE(sum(l.quantity),0) FROM statement_lines l WHERE
 l.organization_id=org AND l.statement_id=t.statement_id AND l.delivery_id=r.delivery_id
 AND l.order_line_id=r.order_line_id AND l.status='included')) THEN
 RAISE EXCEPTION 'review claim requires matching draft quantity' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM statement_review_transfers t JOIN statement_reviews r ON
 r.organization_id=t.organization_id AND r.id=t.review_id JOIN statement_approvals a ON
 a.organization_id=t.organization_id AND a.id=t.approval_id WHERE t.organization_id=org AND
 t.status='approved' AND (a.statement_id<>t.statement_id OR a.delivery_id<>r.delivery_id OR
 a.order_line_id<>r.order_line_id)) OR EXISTS(SELECT 1 FROM statement_approvals a WHERE
 a.organization_id=org AND a.review_quantity<>(SELECT COALESCE(sum(t.quantity),0)
 FROM statement_review_transfers t WHERE t.organization_id=org AND t.approval_id=a.id
 AND t.status='approved')) THEN
 RAISE EXCEPTION 'approved review requires exclusive recognition' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM delivery_lines dl JOIN deliveries d ON
 d.organization_id=dl.organization_id AND d.id=dl.delivery_id
 WHERE dl.organization_id=org AND (
 COALESCE((SELECT b.claimed FROM statement_balances b WHERE b.organization_id=org
 AND b.delivery_id=dl.delivery_id AND b.order_line_id=dl.order_line_id),0) +
 (SELECT COALESCE(sum(r.quantity-(SELECT COALESCE(sum(t.quantity),0)
 FROM statement_review_transfers t WHERE t.organization_id=org AND t.review_id=r.id
 AND t.status IN ('claimed','approved'))),0) FROM statement_reviews r WHERE
 r.organization_id=org AND r.delivery_id=dl.delivery_id AND r.order_line_id=dl.order_line_id)
 >dl.quantity)) THEN
 RAISE EXCEPTION 'unresolved review source capacity' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM statements s WHERE s.organization_id=org AND
 ((s.status='confirmed' AND (NOT s.fees_confirmed OR s.reconfirmation='unknown' OR
 EXISTS(SELECT 1 FROM statement_lines l WHERE l.organization_id=org AND
 l.statement_id=s.id AND l.status='included') OR NOT EXISTS(SELECT 1 FROM statement_events e
 WHERE e.organization_id=org AND e.statement_id=s.id AND e.version=s.version AND
 e.action IN ('settle','correct_settlement')))) OR
 (s.status IN ('abandoned','void') AND EXISTS(SELECT 1 FROM statement_allocations a
 WHERE a.organization_id=org AND a.statement_id=s.id AND a.status IN ('reserved','settled'))))) THEN
 RAISE EXCEPTION 'invalid formal statement state' USING ERRCODE='23000'; END IF;
 IF EXISTS(SELECT 1 FROM statement_allocations a WHERE a.organization_id=org AND
 a.status IN ('settled','superseded') AND (NOT EXISTS(SELECT 1 FROM statement_events e WHERE
 e.organization_id=org AND e.statement_id=a.statement_id AND e.version=a.settlement_version
 AND e.action IN ('settle','correct_settlement')) OR (a.status='superseded' AND NOT EXISTS(
 SELECT 1 FROM statement_events e WHERE e.organization_id=org AND e.statement_id=a.statement_id
 AND e.version=a.superseded_version AND e.action='correct_settlement')))) THEN
 RAISE EXCEPTION 'allocation requires formal event' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
"""

for _table in (
    "statement_approvals",
    "statement_allocations",
    "statement_reviews",
    "statement_review_transfers",
):
    DDL += f"""
CREATE TRIGGER lifecycle_entity_guard BEFORE INSERT OR UPDATE OR DELETE ON {_table}
 FOR EACH ROW EXECUTE FUNCTION guard_lifecycle_entity();
CREATE TRIGGER lifecycle_entity_snapshot AFTER INSERT OR UPDATE ON {_table}
 FOR EACH ROW EXECUTE FUNCTION snapshot_lifecycle_entity();
"""

for _table in (
    "statement_approvals",
    "statement_allocations",
    "statement_reviews",
    "statement_review_transfers",
    "statement_lines",
    "statements",
    "deliveries",
):
    DDL += f"""
CREATE CONSTRAINT TRIGGER lifecycle_state_check AFTER INSERT OR UPDATE ON {_table}
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_lifecycle_state();
"""
