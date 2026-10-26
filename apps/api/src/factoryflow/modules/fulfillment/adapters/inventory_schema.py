"""Delivery-owned immutable inventory decisions, including lines not tracked."""

DDL = """
CREATE TABLE delivery_inventory_snapshots (
 organization_id uuid NOT NULL, delivery_id uuid NOT NULL, order_line_id uuid NOT NULL,
 state text NOT NULL CHECK(state IN ('tracked','skipped','unmanaged','unlinked')),
 material_id uuid, canonical_unit text, quantity numeric NOT NULL,
 movement_id uuid, reason text, mode text NOT NULL CHECK(mode IN ('sync','skip')),
 shortage_confirmed boolean NOT NULL,
 PRIMARY KEY(organization_id,delivery_id,order_line_id),
 CHECK((state IN ('tracked','skipped'))=(movement_id IS NOT NULL)),
 CHECK((state='unlinked')=(material_id IS NULL)),
 CHECK(state<>'tracked' OR mode='sync'), CHECK(state<>'skipped' OR mode='skip'),
 FOREIGN KEY(organization_id,delivery_id,order_line_id) REFERENCES delivery_lines,
 FOREIGN KEY(organization_id,material_id) REFERENCES materials(organization_id,id),
 FOREIGN KEY(organization_id,material_id,movement_id)
  REFERENCES inventory_ledger(organization_id,material_id,id)
);
CREATE TRIGGER delivery_inventory_immutable BEFORE UPDATE OR DELETE ON delivery_inventory_snapshots
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();
CREATE FUNCTION check_delivery_inventory_snapshot() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE source delivery_lines%ROWTYPE; bound_material uuid; managed boolean;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 PERFORM 1 FROM deliveries WHERE organization_id=NEW.organization_id AND id=NEW.delivery_id
  FOR UPDATE;
 SELECT * INTO STRICT source FROM delivery_lines WHERE organization_id=NEW.organization_id
  AND delivery_id=NEW.delivery_id AND order_line_id=NEW.order_line_id;
 SELECT material_id INTO bound_material FROM order_lines WHERE organization_id=NEW.organization_id
  AND id=NEW.order_line_id;
 managed:=EXISTS(SELECT 1 FROM inventory_accounts WHERE organization_id=NEW.organization_id
  AND material_id=NEW.material_id);
 IF EXISTS(SELECT 1 FROM fulfillment_actions WHERE organization_id=NEW.organization_id
  AND delivery_id=NEW.delivery_id AND action='create') OR
  NEW.quantity<>source.quantity OR NEW.canonical_unit IS DISTINCT FROM source.canonical_unit OR
  NEW.material_id IS DISTINCT FROM bound_material OR
  (NEW.state IN ('tracked','skipped'))<>managed THEN
  RAISE EXCEPTION 'invalid or sealed inventory decision' USING ERRCODE='23000'; END IF;
 IF NEW.movement_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM inventory_ledger e
  WHERE e.organization_id=NEW.organization_id AND e.id=NEW.movement_id
  AND e.material_id=NEW.material_id AND e.delivery_id=NEW.delivery_id
  AND e.order_line_id=NEW.order_line_id
  AND e.kind=CASE NEW.state WHEN 'tracked' THEN 'delivery' ELSE 'skip' END
  AND (NEW.state<>'tracked' OR e.shortage_confirmed=NEW.shortage_confirmed)) THEN
  RAISE EXCEPTION 'inventory decision movement mismatch' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER delivery_inventory_source BEFORE INSERT ON delivery_inventory_snapshots
 FOR EACH ROW EXECUTE FUNCTION check_delivery_inventory_snapshot();

CREATE FUNCTION check_inventory_delivery_effects() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE delivery uuid; org uuid;
BEGIN
 org:=NEW.organization_id;
 IF TG_TABLE_NAME='deliveries' THEN delivery:=NEW.id; ELSE delivery:=NEW.delivery_id; END IF;
 IF delivery IS NULL THEN RETURN NULL; END IF;
 IF TG_TABLE_NAME='fulfillment_actions' THEN
  IF NEW.action='create' AND EXISTS(
   SELECT 1 FROM delivery_lines l WHERE l.organization_id=org AND l.delivery_id=delivery
   AND NOT EXISTS(SELECT 1 FROM delivery_inventory_snapshots s WHERE s.organization_id=org
    AND s.delivery_id=delivery AND s.order_line_id=l.order_line_id)) THEN
   RAISE EXCEPTION 'delivery inventory decisions incomplete' USING ERRCODE='23000'; END IF;
 END IF;
 IF EXISTS(SELECT 1 FROM inventory_ledger e WHERE e.organization_id=org AND e.delivery_id=delivery
  AND e.kind IN ('delivery','skip') AND NOT EXISTS(SELECT 1 FROM delivery_inventory_snapshots s
   WHERE s.organization_id=org AND s.delivery_id=delivery AND s.order_line_id=e.order_line_id
   AND s.movement_id=e.id)) OR EXISTS(
  SELECT 1 FROM inventory_ledger e JOIN deliveries d ON d.organization_id=e.organization_id
   AND d.id=e.delivery_id WHERE e.organization_id=org AND e.delivery_id=delivery
   AND e.kind='delivery'
   AND (d.status='void')<>EXISTS(SELECT 1 FROM inventory_ledger r WHERE r.organization_id=org
    AND r.reverses_id=e.id AND r.kind='delivery_void')) THEN
  RAISE EXCEPTION 'delivery inventory effects incomplete' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER inventory_delivery_effects AFTER INSERT ON inventory_ledger
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_delivery_effects();
CREATE CONSTRAINT TRIGGER inventory_delivery_state AFTER UPDATE ON deliveries
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_delivery_effects();
CREATE CONSTRAINT TRIGGER inventory_delivery_sealed AFTER INSERT ON fulfillment_actions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_delivery_effects();
"""
