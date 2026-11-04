"""0016 raw-stock extension; no change to the historical finished-stock DDL."""

DDL = """
ALTER TABLE inventory_ledger ADD COLUMN purchase_receipt_line_id uuid;
ALTER TABLE inventory_ledger ADD COLUMN returns_issue_id uuid;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_ledger_kind_check;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_ledger_check2;
ALTER TABLE inventory_ledger DROP CONSTRAINT inventory_ledger_check6;
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_ledger_kind_check CHECK(kind IN
 ('opening','receipt','count','delivery','skip','delivery_void','receipt_void',
  'purchase_receipt','purchase_receipt_void','material_issue','material_return'));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_reversal_source CHECK
 ((kind IN ('delivery_void','receipt_void','purchase_receipt_void'))=(reverses_id IS NOT NULL));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_reason_required CHECK
 (kind NOT IN ('count','receipt_void','delivery_void',
              'purchase_receipt_void','material_issue','material_return')
  OR reason IS NOT NULL);
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_purchase_source CHECK
 ((kind IN ('purchase_receipt','purchase_receipt_void'))=(purchase_receipt_line_id IS NOT NULL));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_return_source CHECK
 ((kind='material_return')=(returns_issue_id IS NOT NULL));
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_purchase_line_owner
 FOREIGN KEY(organization_id,material_id,purchase_receipt_line_id)
 REFERENCES purchase_receipt_lines(organization_id,material_id,id);
ALTER TABLE inventory_ledger ADD CONSTRAINT inventory_return_issue_owner
 FOREIGN KEY(organization_id,material_id,returns_issue_id)
 REFERENCES inventory_ledger(organization_id,material_id,id);
CREATE INDEX inventory_issue_returns ON inventory_ledger(organization_id,returns_issue_id)
 WHERE returns_issue_id IS NOT NULL;

CREATE OR REPLACE FUNCTION apply_inventory_entry() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a inventory_accounts%ROWTYPE; original inventory_ledger%ROWTYPE;
 source delivery_lines%ROWTYPE; bound_material uuid; next_balance numeric;
 material_kind text; received purchase_receipt_lines%ROWTYPE; receipt_status text; returned numeric;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 SELECT * INTO STRICT a FROM inventory_accounts WHERE organization_id=NEW.organization_id
  AND material_id=NEW.material_id FOR UPDATE;
 SELECT kind INTO STRICT material_kind FROM materials
  WHERE organization_id=NEW.organization_id AND id=NEW.material_id;
 IF (material_kind='raw' AND NEW.kind NOT IN ('opening','count','purchase_receipt',
     'purchase_receipt_void','material_issue','material_return')) OR
    (material_kind='finished' AND NEW.kind IN ('purchase_receipt','purchase_receipt_void',
     'material_issue','material_return')) THEN
  RAISE EXCEPTION 'inventory material kind mismatch' USING ERRCODE='23000';
 END IF;
 IF NEW.kind='opening' THEN
  IF a.version<>0 OR NEW.delta<>NEW.target_quantity THEN
   RAISE EXCEPTION 'inventory already opened' USING ERRCODE='23000'; END IF;
 ELSIF a.version=0 THEN
  RAISE EXCEPTION 'inventory has no opening' USING ERRCODE='23000';
 END IF;
 IF NEW.kind='receipt' AND NEW.delta<=0 THEN
  RAISE EXCEPTION 'receipt must be positive' USING ERRCODE='23000';
 ELSIF NEW.kind='count' THEN
  IF NEW.expected_version<>a.version OR NEW.delta<>NEW.target_quantity-a.balance THEN
   RAISE EXCEPTION 'stale inventory count' USING ERRCODE='23000'; END IF;
 ELSIF NEW.kind IN ('delivery','skip') THEN
  SELECT * INTO STRICT source FROM delivery_lines WHERE organization_id=NEW.organization_id
   AND delivery_id=NEW.delivery_id AND order_line_id=NEW.order_line_id;
  SELECT material_id INTO bound_material FROM order_lines WHERE
   organization_id=NEW.organization_id AND id=NEW.order_line_id;
  IF bound_material IS DISTINCT FROM NEW.material_id OR EXISTS (SELECT 1 FROM fulfillment_actions
   WHERE organization_id=NEW.organization_id AND delivery_id=NEW.delivery_id AND action='create')
   OR NOT EXISTS (SELECT 1 FROM deliveries WHERE organization_id=NEW.organization_id
    AND id=NEW.delivery_id AND status='active') THEN
   RAISE EXCEPTION 'invalid inventory delivery source' USING ERRCODE='23000'; END IF;
  IF (NEW.kind='skip' AND NEW.delta<>0) OR (NEW.kind='delivery' AND
   (NEW.delta<>-source.quantity OR source.canonical_unit IS DISTINCT FROM a.canonical_unit)) THEN
   RAISE EXCEPTION 'invalid inventory delivery quantity' USING ERRCODE='23000'; END IF;
 ELSIF NEW.kind IN ('delivery_void','receipt_void','purchase_receipt_void') THEN
  SELECT * INTO STRICT original FROM inventory_ledger WHERE organization_id=NEW.organization_id
   AND material_id=NEW.material_id AND id=NEW.reverses_id;
  IF original.kind<>(CASE NEW.kind WHEN 'delivery_void' THEN 'delivery'
    WHEN 'purchase_receipt_void' THEN 'purchase_receipt' ELSE 'receipt' END)
   OR NEW.delta<>-original.delta OR NEW.delivery_id IS DISTINCT FROM original.delivery_id
   OR NEW.order_line_id IS DISTINCT FROM original.order_line_id
   OR NEW.purchase_receipt_line_id IS DISTINCT FROM original.purchase_receipt_line_id THEN
   RAISE EXCEPTION 'invalid inventory reversal' USING ERRCODE='23000'; END IF;
 ELSIF NEW.kind='material_issue' THEN
  IF NEW.delta>=0 THEN RAISE EXCEPTION 'issue must be negative' USING ERRCODE='23000'; END IF;
 ELSIF NEW.kind='material_return' THEN
  SELECT * INTO STRICT original FROM inventory_ledger WHERE organization_id=NEW.organization_id
   AND material_id=NEW.material_id AND id=NEW.returns_issue_id;
  SELECT COALESCE(sum(delta),0) INTO returned FROM inventory_ledger
   WHERE organization_id=NEW.organization_id AND returns_issue_id=NEW.returns_issue_id;
  IF original.kind<>'material_issue' OR NEW.delta<=0 OR returned+NEW.delta>-original.delta THEN
   RAISE EXCEPTION 'return exceeds original issue' USING ERRCODE='23000'; END IF;
 END IF;
 IF NEW.kind IN ('purchase_receipt','purchase_receipt_void') THEN
  SELECT * INTO STRICT received FROM purchase_receipt_lines
   WHERE organization_id=NEW.organization_id
   AND material_id=NEW.material_id AND id=NEW.purchase_receipt_line_id;
  SELECT status INTO STRICT receipt_status FROM purchase_receipts
   WHERE organization_id=NEW.organization_id
   AND id=received.receipt_id;
  IF a.canonical_unit<>received.canonical_unit OR
    (NEW.kind='purchase_receipt' AND (NEW.delta<>received.quantity OR receipt_status<>'active')) OR
    (NEW.kind='purchase_receipt_void'
     AND (NEW.delta<>-received.quantity OR receipt_status<>'void')) THEN
   RAISE EXCEPTION 'invalid purchasing inventory source' USING ERRCODE='23000'; END IF;
 END IF;
 next_balance:=a.balance+NEW.delta;
 IF abs(next_balance)>9223372036854775.807 OR scale(NEW.delta)>3 OR
  (a.canonical_unit IN ('PCS','SET','台','箱','卷') AND NEW.delta<>trunc(NEW.delta)) OR
  (NEW.kind IN ('opening','count','receipt_void') AND next_balance<0) OR
  (NEW.kind='delivery' AND next_balance<0 AND NOT NEW.shortage_confirmed) OR
  (material_kind='raw' AND next_balance<0) THEN
  RAISE EXCEPTION 'invalid inventory balance' USING ERRCODE='23000'; END IF;
 NEW.balance_after:=next_balance;
 NEW.account_version:=a.version+1;
 UPDATE inventory_accounts SET balance=next_balance,version=NEW.account_version,
  has_skipped=CASE WHEN NEW.kind='skip' THEN true WHEN NEW.kind='count' THEN false
   ELSE has_skipped END WHERE organization_id=NEW.organization_id AND material_id=NEW.material_id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION apply_inventory_entry() FROM PUBLIC;
"""
