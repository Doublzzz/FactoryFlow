"""0017 adds production guards without rewriting the historical ledger trigger."""

DDL = """
ALTER TABLE inventory_ledger ADD COLUMN production_order_id uuid;
ALTER TABLE inventory_ledger ADD COLUMN production_completion_id uuid;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_ledger_kind_check;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_reversal_source;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_reason_required;
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_ledger_kind_check CHECK(kind IN
 ('opening','receipt','count','delivery','skip','delivery_void','receipt_void',
  'purchase_receipt','purchase_receipt_void','material_issue','material_return',
  'production_receipt','production_receipt_void'));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_reversal_source CHECK
 ((kind IN ('delivery_void','receipt_void','purchase_receipt_void',
 'production_receipt_void'))=(reverses_id IS NOT NULL));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_reason_required CHECK
 (kind NOT IN ('count','receipt_void','delivery_void','purchase_receipt_void',
              'material_issue','material_return','production_receipt_void') OR reason IS NOT NULL);
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_production_completion_source CHECK
 ((kind IN ('production_receipt','production_receipt_void'))=
 (production_completion_id IS NOT NULL));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_production_order_source CHECK
 ((production_completion_id IS NULL OR production_order_id IS NOT NULL) AND
  (production_order_id IS NULL OR kind IN
   ('material_issue','material_return','production_receipt','production_receipt_void')));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_production_owner
 FOREIGN KEY(organization_id,production_order_id) REFERENCES production_orders(organization_id,id);
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_production_completion_owner
 FOREIGN KEY(organization_id,production_order_id,material_id,production_completion_id)
 REFERENCES production_completions(organization_id,production_order_id,material_id,id);
CREATE INDEX inventory_production_issues ON
 inventory_ledger(organization_id,production_order_id,id DESC)
 WHERE production_order_id IS NOT NULL;

CREATE FUNCTION check_inventory_production_source() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE h production_orders%ROWTYPE; c production_completions%ROWTYPE;
 original inventory_ledger%ROWTYPE; a inventory_accounts%ROWTYPE;
BEGIN
 IF NEW.production_order_id IS NULL AND NEW.kind<>'material_return' THEN RETURN NEW; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 IF NEW.kind='material_return' THEN
  SELECT * INTO STRICT original FROM inventory_ledger WHERE organization_id=NEW.organization_id
   AND id=NEW.returns_issue_id;
  IF NEW.production_order_id IS DISTINCT FROM original.production_order_id THEN
   RAISE EXCEPTION 'return must retain production source' USING ERRCODE='23000'; END IF;
  RETURN NEW;
 END IF;
 SELECT * INTO STRICT h FROM production_orders WHERE organization_id=NEW.organization_id
  AND id=NEW.production_order_id;
 IF NEW.kind='material_issue' THEN
  PERFORM require_production_source(h.organization_id,h.order_id,h.source_revision_id,
   h.order_line_id,h.material_id,h.canonical_unit);
  SELECT * INTO STRICT h FROM production_orders WHERE organization_id=NEW.organization_id
   AND id=NEW.production_order_id FOR UPDATE;
  IF h.status<>'open' THEN
   RAISE EXCEPTION 'production closed' USING ERRCODE='23000'; END IF;
 ELSIF NEW.kind IN ('production_receipt','production_receipt_void') THEN
  SELECT * INTO STRICT c FROM production_completions WHERE organization_id=NEW.organization_id
   AND id=NEW.production_completion_id;
  SELECT * INTO STRICT a FROM inventory_accounts WHERE organization_id=NEW.organization_id
   AND material_id=NEW.material_id FOR UPDATE;
  IF c.quantity<=0 OR c.production_order_id<>h.id OR NEW.material_id<>c.material_id OR
   a.canonical_unit<>h.canonical_unit THEN
   RAISE EXCEPTION 'invalid production stock source' USING ERRCODE='23000'; END IF;
  IF NEW.kind='production_receipt' THEN
   IF NEW.delta<>c.quantity OR NEW.business_date<>c.business_date OR c.status<>'active' THEN
    RAISE EXCEPTION 'invalid production stock quantity' USING ERRCODE='23000'; END IF;
  ELSE
   SELECT * INTO STRICT original FROM inventory_ledger WHERE organization_id=NEW.organization_id
    AND id=NEW.reverses_id;
   IF c.status<>'void' OR NEW.delta<>-c.quantity OR original.kind<>'production_receipt' OR
    original.material_id<>NEW.material_id OR
    original.production_order_id IS DISTINCT FROM NEW.production_order_id OR
    original.production_completion_id IS DISTINCT FROM NEW.production_completion_id OR
    NEW.delta<>-original.delta OR a.balance+NEW.delta<0 THEN
    RAISE EXCEPTION 'invalid production stock reversal' USING ERRCODE='23000'; END IF;
  END IF;
 END IF;
 RETURN NEW;
END; $$;
-- Alphabetical trigger order takes source locks before the existing stock trigger.
CREATE TRIGGER a_production_inventory_source BEFORE INSERT ON inventory_ledger
 FOR EACH ROW EXECUTE FUNCTION check_inventory_production_source();
REVOKE ALL ON FUNCTION check_inventory_production_source() FROM PUBLIC;
"""
