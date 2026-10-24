DDL = """
ALTER TABLE order_lines ADD CONSTRAINT lines_delivery_source_unique
 UNIQUE (organization_id,order_id,revision_id,id);
CREATE TABLE deliveries (
 id uuid NOT NULL, organization_id uuid NOT NULL, order_id uuid NOT NULL,
 customer_id uuid NOT NULL, revision_id uuid NOT NULL, delivery_date date NOT NULL,
 customer_name text NOT NULL, order_number text NOT NULL,
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','void')),
 version integer NOT NULL DEFAULT 1, void_reason text,
 created_at timestamptz NOT NULL DEFAULT now(), voided_at timestamptz,
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,id,order_id,revision_id),
 CHECK ((status='active' AND version=1 AND void_reason IS NULL AND voided_at IS NULL)
     OR (status='void' AND version=2 AND void_reason IS NOT NULL
  AND length(btrim(void_reason)) BETWEEN 1 AND 500 AND
  voided_at IS NOT NULL)),
 FOREIGN KEY (organization_id,revision_id,order_id,customer_id)
  REFERENCES confirmed_revisions(organization_id,id,order_id,customer_id)
);
CREATE INDEX deliveries_customer_page ON deliveries(organization_id,customer_id,id DESC);
CREATE INDEX deliveries_order_page ON deliveries(organization_id,order_id,id DESC);
CREATE TABLE delivery_lines (
 organization_id uuid NOT NULL, delivery_id uuid NOT NULL, order_id uuid NOT NULL,
 revision_id uuid NOT NULL, order_line_id uuid NOT NULL, line_number integer NOT NULL,
 quantity numeric NOT NULL CHECK (quantity>0 AND quantity<=9223372036854775.807 AND
  scale(quantity)<=3),
 description text NOT NULL, source_unit text, canonical_unit text, quantity_policy jsonb NOT NULL,
 PRIMARY KEY (organization_id,delivery_id,order_line_id),
 UNIQUE (organization_id,delivery_id,line_number),
 CHECK (quantity_policy->>'mode'<>'INTEGER_ONLY' OR quantity=trunc(quantity)),
 FOREIGN KEY (organization_id,delivery_id,order_id,revision_id)
  REFERENCES deliveries(organization_id,id,order_id,revision_id),
 FOREIGN KEY (organization_id,order_id,revision_id,order_line_id)
  REFERENCES order_lines(organization_id,order_id,revision_id,id)
);
CREATE TABLE fulfillment_actions (
 id uuid NOT NULL, organization_id uuid NOT NULL, delivery_id uuid NOT NULL,
 action text NOT NULL CHECK (action IN ('create','void')), reverses_id uuid,
 reason text, actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,delivery_id,action),
 UNIQUE (organization_id,delivery_id,id),
 CHECK ((action='create' AND reverses_id IS NULL AND reason IS NULL)
     OR (action='void' AND reverses_id IS NOT NULL AND reason IS NOT NULL
  AND length(btrim(reason)) BETWEEN 1 AND 500)),
 FOREIGN KEY (organization_id,delivery_id) REFERENCES deliveries(organization_id,id),
 FOREIGN KEY (organization_id,delivery_id,reverses_id)
  REFERENCES fulfillment_actions(organization_id,delivery_id,id),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE TRIGGER delivery_lines_immutable BEFORE UPDATE OR DELETE ON delivery_lines
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
CREATE TRIGGER fulfillment_actions_immutable BEFORE UPDATE OR DELETE ON fulfillment_actions
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
CREATE FUNCTION check_delivery_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 PERFORM 1 FROM deliveries WHERE organization_id=NEW.organization_id AND id=NEW.delivery_id
  FOR UPDATE;
 IF EXISTS (SELECT 1 FROM fulfillment_actions WHERE organization_id=NEW.organization_id
  AND delivery_id=NEW.delivery_id AND action='create') THEN
  RAISE EXCEPTION 'sealed delivery lines' USING ERRCODE='23000';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM order_lines l
  WHERE l.organization_id=NEW.organization_id AND l.id=NEW.order_line_id
  AND l.order_id=NEW.order_id AND l.revision_id=NEW.revision_id
  AND l.line_number=NEW.line_number AND l.description=NEW.description
  AND l.source_unit IS NOT DISTINCT FROM NEW.source_unit
  AND l.canonical_unit IS NOT DISTINCT FROM NEW.canonical_unit
  AND l.quantity_policy=NEW.quantity_policy) THEN
  RAISE EXCEPTION 'invalid delivery source snapshot' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER delivery_source BEFORE INSERT ON delivery_lines
 FOR EACH ROW EXECUTE FUNCTION check_delivery_source();
CREATE FUNCTION check_reverse_action() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.action='void' AND NOT EXISTS (SELECT 1 FROM fulfillment_actions
  WHERE organization_id=NEW.organization_id AND delivery_id=NEW.delivery_id
  AND id=NEW.reverses_id AND action='create') THEN
  RAISE EXCEPTION 'invalid reverse action' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER fulfillment_reverse BEFORE INSERT ON fulfillment_actions
 FOR EACH ROW EXECUTE FUNCTION check_reverse_action();
CREATE FUNCTION protect_delivery() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable delivery' USING ERRCODE='23000'; END IF;
 IF OLD.status<>'active' OR NEW.status<>'void'
 OR (to_jsonb(NEW)-ARRAY['status','version','void_reason','voided_at'])
    IS DISTINCT FROM (to_jsonb(OLD)-ARRAY['status','version','void_reason','voided_at']) THEN
  RAISE EXCEPTION 'invalid delivery transition' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER deliveries_protect BEFORE UPDATE OR DELETE ON deliveries
 FOR EACH ROW EXECUTE FUNCTION protect_delivery();

-- Check at commit after both owners have written their effects. All writes serialize
-- on the owning order; arithmetic on order_lines also takes PostgreSQL row locks.
CREATE FUNCTION check_delivery_projection() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE org uuid; source_order uuid;
BEGIN
 org:=NEW.organization_id;
 IF TG_TABLE_NAME='fulfillment_actions' THEN
  SELECT order_id INTO source_order FROM deliveries WHERE organization_id=org AND
  id=NEW.delivery_id;
 ELSIF TG_TABLE_NAME='orders' THEN source_order:=NEW.id;
 ELSE source_order:=NEW.order_id; END IF;
 IF EXISTS (
  SELECT 1 FROM order_lines l WHERE l.organization_id=org AND l.order_id=source_order
  AND l.delivered_quantity<>(SELECT COALESCE(sum(dl.quantity),0) FROM delivery_lines dl
   JOIN deliveries d ON d.organization_id=dl.organization_id AND d.id=dl.delivery_id
   WHERE dl.organization_id=l.organization_id AND dl.order_line_id=l.id AND d.status='active')
 ) OR EXISTS (
  SELECT 1 FROM deliveries d WHERE d.organization_id=org AND d.order_id=source_order
  AND ((d.status='active' AND NOT EXISTS (SELECT 1 FROM orders o WHERE o.organization_id=org
        AND o.id=source_order AND o.current_revision_id=d.revision_id AND o.status='active'))
   OR NOT EXISTS (SELECT 1 FROM delivery_lines dl WHERE dl.organization_id=org AND
  dl.delivery_id=d.id)
   OR NOT EXISTS (SELECT 1 FROM fulfillment_actions a WHERE a.organization_id=org AND
  a.delivery_id=d.id AND a.action='create')
   OR (d.status='void')<>EXISTS (SELECT 1 FROM fulfillment_actions a WHERE a.organization_id=org
  AND a.delivery_id=d.id AND a.action='void'))
 ) THEN RAISE EXCEPTION 'delivery ledger mismatch' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER order_delivery_projection AFTER INSERT OR UPDATE ON order_lines
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_delivery_projection();
CREATE CONSTRAINT TRIGGER order_delivery_state AFTER UPDATE ON orders
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_delivery_projection();
CREATE CONSTRAINT TRIGGER delivery_projection AFTER INSERT OR UPDATE ON deliveries
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_delivery_projection();
CREATE CONSTRAINT TRIGGER delivery_line_projection AFTER INSERT ON delivery_lines
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_delivery_projection();
CREATE CONSTRAINT TRIGGER fulfillment_action_projection AFTER INSERT ON fulfillment_actions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_delivery_projection();
"""
