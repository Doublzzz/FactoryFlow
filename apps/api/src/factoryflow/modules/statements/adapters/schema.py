DDL = """
CREATE TABLE statements (
 organization_id uuid NOT NULL, id uuid NOT NULL, customer_id uuid NOT NULL,
 period_start date NOT NULL, period_end date NOT NULL CHECK (period_end>=period_start),
 status text NOT NULL CHECK (status IN ('draft','abandoned')),
 version integer NOT NULL CHECK (version>0), tax_mode text NOT NULL
 CHECK (tax_mode IN ('included','untaxed_final','add_tax')),
 tax_rate numeric NOT NULL CHECK (tax_rate>=0 AND tax_rate<=100 AND scale(tax_rate)<=4),
 adjustments jsonb NOT NULL DEFAULT '[]', customer_name text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,id,customer_id),
 CONSTRAINT statement_period_unique UNIQUE (organization_id,customer_id,period_start,period_end),
 FOREIGN KEY (organization_id,customer_id) REFERENCES customers(organization_id,id)
);
CREATE TABLE statement_lines (
 organization_id uuid NOT NULL, statement_id uuid NOT NULL, customer_id uuid NOT NULL,
 delivery_id uuid NOT NULL, order_line_id uuid NOT NULL,
 quantity numeric NOT NULL CHECK (quantity>=0 AND quantity<=9223372036854775.807
 AND scale(quantity)<=3),
 unit_price numeric CHECK (unit_price>=0 AND unit_price<=999999999999.9999
 AND scale(unit_price)<=4),
 status text NOT NULL CHECK (status IN ('included','deferred','source_void','released')),
 reason text NOT NULL DEFAULT '', source jsonb NOT NULL,
 CHECK (status<>'included' OR quantity>0),
 CHECK (status<>'deferred' OR (quantity=0 AND length(btrim(reason)) BETWEEN 1 AND 500)),
 PRIMARY KEY (organization_id,statement_id,delivery_id,order_line_id),
 FOREIGN KEY (organization_id,statement_id,customer_id)
 REFERENCES statements(organization_id,id,customer_id),
 FOREIGN KEY (organization_id,delivery_id,order_line_id)
 REFERENCES delivery_lines(organization_id,delivery_id,order_line_id)
);
CREATE TABLE statement_balances (
 organization_id uuid NOT NULL, delivery_id uuid NOT NULL, order_line_id uuid NOT NULL,
 capacity numeric NOT NULL, claimed numeric NOT NULL,
 CHECK (capacity>0 AND capacity<=9223372036854775.807 AND scale(capacity)<=3),
 CHECK (claimed>=0 AND claimed<=capacity AND scale(claimed)<=3),
 PRIMARY KEY (organization_id,delivery_id,order_line_id),
 FOREIGN KEY (organization_id,delivery_id,order_line_id)
 REFERENCES delivery_lines(organization_id,delivery_id,order_line_id)
);
CREATE TABLE statement_events (
 organization_id uuid NOT NULL, id uuid NOT NULL, statement_id uuid NOT NULL,
 version integer NOT NULL, action text NOT NULL, reason text NOT NULL,
 actor_id uuid NOT NULL, snapshot jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE(organization_id,statement_id,version),
 FOREIGN KEY (organization_id,statement_id) REFERENCES statements(organization_id,id),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE TRIGGER statement_events_immutable BEFORE UPDATE OR DELETE ON statement_events
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
CREATE TABLE statement_customer_settings (
 organization_id uuid NOT NULL, customer_id uuid NOT NULL, version integer NOT NULL,
 cycle_day integer CHECK (cycle_day BETWEEN 1 AND 31),
 tax_mode text NOT NULL CHECK (tax_mode IN ('included','untaxed_final','add_tax')),
 tax_rate numeric NOT NULL CHECK (tax_rate>=0 AND tax_rate<=100 AND scale(tax_rate)<=4),
 PRIMARY KEY (organization_id,customer_id),
 FOREIGN KEY (organization_id,customer_id) REFERENCES customers(organization_id,id)
);
CREATE INDEX statement_lines_source ON statement_lines(organization_id,delivery_id,order_line_id);

CREATE FUNCTION guard_statement_claim() RETURNS trigger LANGUAGE plpgsql AS $$
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
 AND id=NEW.statement_id;
 IF src.customer_id IS NULL OR src.customer_id IS DISTINCT FROM NEW.customer_id
 OR src.delivery_date>head.period_end THEN
  RAISE EXCEPTION 'invalid statement source' USING ERRCODE='23000'; END IF;
 IF NEW.status='included' THEN
  IF src.status<>'active' OR head.status<>'draft'
   OR (src.quantity_policy->>'mode'='INTEGER_ONLY' AND NEW.quantity<>trunc(NEW.quantity)) THEN
   RAISE EXCEPTION 'invalid statement claim' USING ERRCODE='23000'; END IF;
  new_claim:=NEW.quantity;
 END IF;
 INSERT INTO statement_balances(organization_id,delivery_id,order_line_id,capacity,claimed)
 VALUES(NEW.organization_id,NEW.delivery_id,NEW.order_line_id,src.quantity,0)
 ON CONFLICT(organization_id,delivery_id,order_line_id)
 DO NOTHING;
 UPDATE statement_balances SET claimed=claimed+new_claim-old_claim
 WHERE organization_id=NEW.organization_id AND delivery_id=NEW.delivery_id
 AND order_line_id=NEW.order_line_id;
 RETURN NEW;
END; $$;
CREATE TRIGGER statement_claim_guard BEFORE INSERT OR UPDATE OR DELETE ON statement_lines
 FOR EACH ROW EXECUTE FUNCTION guard_statement_claim();

CREATE FUNCTION check_statement_balance() RETURNS trigger LANGUAGE plpgsql AS $$
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
   AND l.order_line_id=b.order_line_id AND l.status='included')))
 THEN RAISE EXCEPTION 'statement balance mismatch' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER statement_balance_check AFTER INSERT OR UPDATE ON statement_balances
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_statement_balance();
CREATE CONSTRAINT TRIGGER statement_delivery_check AFTER UPDATE ON deliveries
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_statement_balance();

CREATE FUNCTION protect_statement_balance() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN
  RAISE EXCEPTION 'retain statement balance' USING ERRCODE='23000'; END IF;
 IF (to_jsonb(NEW)-'claimed') IS DISTINCT FROM (to_jsonb(OLD)-'claimed') THEN
  RAISE EXCEPTION 'immutable statement balance source' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER statement_balance_protect BEFORE UPDATE OR DELETE ON statement_balances
 FOR EACH ROW EXECUTE FUNCTION protect_statement_balance();

CREATE FUNCTION guard_statement_header() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain statement history' USING ERRCODE='23000'; END IF;
 IF (to_jsonb(NEW)-ARRAY['status','version','tax_mode','tax_rate','adjustments']) IS DISTINCT FROM
    (to_jsonb(OLD)-ARRAY['status','version','tax_mode','tax_rate','adjustments'])
 OR NEW.version<>OLD.version+1 THEN
  RAISE EXCEPTION 'invalid statement transition' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER statement_header_guard BEFORE UPDATE OR DELETE ON statements
 FOR EACH ROW EXECUTE FUNCTION guard_statement_header();
CREATE FUNCTION check_statement_state() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE current_state text;
BEGIN
 SELECT status INTO current_state FROM statements
 WHERE organization_id=NEW.organization_id AND id=NEW.id;
 IF current_state='abandoned' AND EXISTS(SELECT 1 FROM statement_lines WHERE
 organization_id=NEW.organization_id AND statement_id=NEW.id AND status='included') THEN
 RAISE EXCEPTION 'abandoned statement retains claims' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER statement_state_check AFTER UPDATE ON statements
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_statement_state();
"""
