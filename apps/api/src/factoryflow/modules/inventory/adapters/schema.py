"""Inventory-owned append-only quantities and database-maintained projections."""

DDL = """
CREATE TABLE inventory_accounts (
 organization_id uuid NOT NULL, material_id uuid NOT NULL, canonical_unit text NOT NULL,
 balance numeric NOT NULL DEFAULT 0, version bigint NOT NULL DEFAULT 0,
 has_skipped boolean NOT NULL DEFAULT false, created_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,material_id),
 CHECK(abs(balance)<=9223372036854775.807 AND scale(balance)<=3), CHECK(version>=0),
 CHECK(canonical_unit IN ('PCS','SET','台','箱','卷','KG','G','LB','OZ','M','MM','CM','KM')),
 FOREIGN KEY(organization_id,material_id) REFERENCES materials(organization_id,id),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id)
);
CREATE TABLE inventory_ledger (
 organization_id uuid NOT NULL, id uuid NOT NULL, material_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN
  ('opening','receipt','count','delivery','skip','delivery_void','receipt_void')),
 delta numeric NOT NULL, target_quantity numeric, expected_version bigint,
 balance_after numeric NOT NULL DEFAULT 0, account_version bigint NOT NULL DEFAULT 0,
 business_date date NOT NULL, recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 reason text CHECK(reason IS NULL OR length(btrim(reason)) BETWEEN 1 AND 500),
 actor_id uuid NOT NULL, delivery_id uuid, order_line_id uuid, reverses_id uuid,
 shortage_confirmed boolean NOT NULL DEFAULT false,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,material_id,id),
 UNIQUE(organization_id,material_id,account_version),
 UNIQUE(organization_id,reverses_id),
 CHECK(abs(delta)<=9223372036854775.807 AND scale(delta)<=3),
 CHECK(abs(balance_after)<=9223372036854775.807 AND scale(balance_after)<=3),
 CHECK(target_quantity IS NULL OR (target_quantity>=0 AND
  target_quantity<=9223372036854775.807 AND scale(target_quantity)<=3)),
 CHECK((kind IN ('delivery','skip','delivery_void'))=(delivery_id IS NOT NULL)),
 CHECK((delivery_id IS NULL)=(order_line_id IS NULL)),
 CHECK((kind IN ('delivery_void','receipt_void'))=(reverses_id IS NOT NULL)),
 CHECK((kind IN ('opening','count'))=(target_quantity IS NOT NULL)),
 CHECK((kind='count')=(expected_version IS NOT NULL)),
 CHECK(NOT shortage_confirmed OR kind='delivery'),
 CHECK(kind NOT IN ('count','receipt_void','delivery_void') OR reason IS NOT NULL),
 FOREIGN KEY(organization_id,material_id) REFERENCES inventory_accounts,
 FOREIGN KEY(organization_id,material_id,reverses_id)
  REFERENCES inventory_ledger(organization_id,material_id,id),
 FOREIGN KEY(organization_id,delivery_id,order_line_id) REFERENCES delivery_lines,
 FOREIGN KEY(organization_id,actor_id) REFERENCES users(organization_id,id)
);
CREATE UNIQUE INDEX inventory_open_once ON inventory_ledger(organization_id,material_id)
 WHERE kind='opening';
CREATE UNIQUE INDEX inventory_delivery_once
 ON inventory_ledger(organization_id,delivery_id,order_line_id) WHERE kind IN ('delivery','skip');
CREATE INDEX inventory_ledger_page
 ON inventory_ledger(organization_id,material_id,account_version DESC);
CREATE TRIGGER inventory_ledger_immutable BEFORE UPDATE OR DELETE ON inventory_ledger
 FOR EACH ROW EXECUTE FUNCTION reject_evidence_change();

CREATE FUNCTION protect_inventory_account() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE source_unit text; normalized text;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable inventory account' USING ERRCODE='23000'; END IF;
 IF TG_OP='UPDATE' THEN
  IF pg_trigger_depth()<2 OR
   (to_jsonb(NEW)-ARRAY['balance','version','has_skipped']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['balance','version','has_skipped']) THEN
   RAISE EXCEPTION 'inventory projection is ledger owned' USING ERRCODE='23000';
  END IF;
  RETURN NEW;
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 SELECT upper(btrim(unit)) INTO source_unit FROM materials
  WHERE organization_id=NEW.organization_id AND id=NEW.material_id AND active;
 normalized:=CASE
  WHEN source_unit IN ('PCS','PCS.','PC','EA','个','件') THEN 'PCS'
  WHEN source_unit IN ('SET','套') THEN 'SET'
  WHEN source_unit IN ('台','箱','卷') THEN source_unit
  WHEN source_unit IN ('KG','KGS','公斤','千克') THEN 'KG'
  WHEN source_unit IN ('G','克') THEN 'G'
  WHEN source_unit IN ('LB','LBS','磅') THEN 'LB'
  WHEN source_unit IN ('OZ','盎司') THEN 'OZ'
  WHEN source_unit IN ('M','米') THEN 'M'
  WHEN source_unit IN ('MM','毫米') THEN 'MM'
  WHEN source_unit IN ('CM','厘米') THEN 'CM'
  WHEN source_unit IN ('KM','千米','公里') THEN 'KM' END;
 IF normalized IS NULL OR normalized<>NEW.canonical_unit OR NEW.balance<>0
  OR NEW.version<>0 OR NEW.has_skipped THEN
  RAISE EXCEPTION 'invalid inventory opening account' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION protect_inventory_account() FROM PUBLIC;
CREATE TRIGGER inventory_account_protect BEFORE INSERT OR UPDATE OR DELETE ON inventory_accounts
 FOR EACH ROW EXECUTE FUNCTION protect_inventory_account();

CREATE FUNCTION apply_inventory_entry() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a inventory_accounts%ROWTYPE; original inventory_ledger%ROWTYPE;
 source delivery_lines%ROWTYPE; bound_material uuid; next_balance numeric;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 SELECT * INTO STRICT a FROM inventory_accounts WHERE organization_id=NEW.organization_id
  AND material_id=NEW.material_id FOR UPDATE;
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
 ELSIF NEW.kind IN ('delivery_void','receipt_void') THEN
  SELECT * INTO STRICT original FROM inventory_ledger WHERE organization_id=NEW.organization_id
   AND material_id=NEW.material_id AND id=NEW.reverses_id;
  IF original.kind<>(CASE NEW.kind WHEN 'delivery_void' THEN 'delivery' ELSE 'receipt' END)
   OR NEW.delta<>-original.delta OR NEW.delivery_id IS DISTINCT FROM original.delivery_id
   OR NEW.order_line_id IS DISTINCT FROM original.order_line_id THEN
   RAISE EXCEPTION 'invalid inventory reversal' USING ERRCODE='23000'; END IF;
 END IF;
 next_balance:=a.balance+NEW.delta;
 IF abs(next_balance)>9223372036854775.807 OR scale(NEW.delta)>3 OR
  (a.canonical_unit IN ('PCS','SET','台','箱','卷') AND NEW.delta<>trunc(NEW.delta)) OR
  (NEW.kind IN ('opening','count','receipt_void') AND next_balance<0) OR
  (NEW.kind='delivery' AND next_balance<0 AND NOT NEW.shortage_confirmed) THEN
  RAISE EXCEPTION 'invalid inventory balance' USING ERRCODE='23000'; END IF;
 NEW.balance_after:=next_balance;
 NEW.account_version:=a.version+1;
 UPDATE inventory_accounts SET balance=next_balance,version=NEW.account_version,
  has_skipped=CASE WHEN NEW.kind='skip' THEN true WHEN NEW.kind='count' THEN false
   ELSE has_skipped END WHERE organization_id=NEW.organization_id AND material_id=NEW.material_id;
 RETURN NEW;
END; $$;
REVOKE ALL ON FUNCTION apply_inventory_entry() FROM PUBLIC;
CREATE TRIGGER inventory_entry_apply BEFORE INSERT ON inventory_ledger
 FOR EACH ROW EXECUTE FUNCTION apply_inventory_entry();

CREATE FUNCTION check_inventory_projection() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE a inventory_accounts%ROWTYPE; total numeric; latest bigint; opening_count bigint;
 skipped bigint; counted bigint;
BEGIN
 SELECT * INTO STRICT a FROM inventory_accounts WHERE organization_id=NEW.organization_id
  AND material_id=NEW.material_id;
 SELECT COALESCE(sum(delta),0),COALESCE(max(account_version),0),
  count(*) FILTER(WHERE kind='opening'),
  COALESCE(max(account_version) FILTER(WHERE kind='skip'),0),
  COALESCE(max(account_version) FILTER(WHERE kind='count'),0)
 INTO total,latest,opening_count,skipped,counted FROM inventory_ledger
 WHERE organization_id=a.organization_id AND material_id=a.material_id;
 IF opening_count<>1 OR a.balance<>total OR a.version<>latest OR
  a.has_skipped<>(skipped>counted) THEN
  RAISE EXCEPTION 'inventory ledger projection mismatch' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER inventory_account_projection AFTER INSERT OR UPDATE ON inventory_accounts
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_projection();
CREATE CONSTRAINT TRIGGER inventory_entry_projection AFTER INSERT ON inventory_ledger
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_inventory_projection();
"""
