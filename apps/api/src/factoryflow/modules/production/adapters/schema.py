"""0017 production evidence; inventory owns the corresponding stock effects."""

DDL = """
ALTER TABLE order_lines ADD CONSTRAINT production_line_identity
 UNIQUE(organization_id,order_id,revision_id,id);
CREATE TABLE production_orders (
 organization_id uuid NOT NULL, id uuid NOT NULL, number text NOT NULL,
 order_id uuid NOT NULL, source_revision_id uuid NOT NULL, order_line_id uuid NOT NULL,
 order_number text NOT NULL, source_quantity numeric NOT NULL,
 material_id uuid NOT NULL, own_code text NOT NULL, material_name text NOT NULL, specification text,
 canonical_unit text NOT NULL CHECK(canonical_unit IN
  ('PCS','SET','台','箱','卷','KG','G','LB','OZ','M','MM','CM','KM')),
 planned_quantity numeric NOT NULL CHECK(planned_quantity>0 AND
  planned_quantity<=9223372036854775.807 AND scale(planned_quantity)<=3),
 business_date date NOT NULL, note text CHECK(note IS NULL OR length(btrim(note)) BETWEEN 1 AND
 500),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 closed_by uuid, closed_at timestamptz, close_reason text,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,number),
 UNIQUE(organization_id,id,material_id),
 CHECK((status='closed')=(closed_by IS NOT NULL)),
 CHECK((status='closed')=(closed_at IS NOT NULL)),
 CHECK((status='closed')=(close_reason IS NOT NULL)),
 CHECK(close_reason IS NULL OR length(btrim(close_reason)) BETWEEN 1 AND 500),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,closed_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,material_id) REFERENCES materials(organization_id,id),
 FOREIGN KEY(organization_id,order_id,source_revision_id,order_line_id)
  REFERENCES order_lines(organization_id,order_id,revision_id,id)
);
CREATE INDEX production_order_source ON production_orders(organization_id,order_id,id DESC);
CREATE TABLE production_completions (
 organization_id uuid NOT NULL, id uuid NOT NULL, production_order_id uuid NOT NULL,
 material_id uuid NOT NULL, quantity numeric NOT NULL, scrap_quantity numeric NOT NULL,
 business_date date NOT NULL, note text CHECK(note IS NULL OR length(btrim(note)) BETWEEN 1 AND
 500),
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','void')),
 version integer NOT NULL DEFAULT 1 CHECK(version>0),
 created_by uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 void_by uuid, void_at timestamptz, void_reason text,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,production_order_id,material_id,id),
 CHECK(quantity>=0 AND quantity<=9223372036854775.807 AND scale(quantity)<=3),
 CHECK(scrap_quantity>=0 AND scrap_quantity<=9223372036854775.807 AND scale(scrap_quantity)<=3),
 CHECK(quantity>0 OR scrap_quantity>0),
 CHECK((status='void')=(void_by IS NOT NULL)), CHECK((status='void')=(void_at IS NOT NULL)),
 CHECK((status='void')=(void_reason IS NOT NULL)),
 CHECK(void_reason IS NULL OR length(btrim(void_reason)) BETWEEN 1 AND 500),
 FOREIGN KEY(organization_id,production_order_id,material_id)
  REFERENCES production_orders(organization_id,id,material_id),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,void_by) REFERENCES users(organization_id,id)
);
CREATE INDEX production_completion_page ON
production_completions(organization_id,production_order_id,id DESC);

CREATE FUNCTION require_production_source(org uuid, source_order uuid, revision uuid,
 source_line uuid, material uuid, unit text) RETURNS void
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE h orders%ROWTYPE; l order_lines%ROWTYPE; m materials%ROWTYPE; source_unit text;
normalized text;
BEGIN
 PERFORM pg_advisory_xact_lock(hashtextextended(org::text||chr(58)||'materials',0));
 SELECT * INTO STRICT h FROM orders WHERE organization_id=org AND id=source_order FOR UPDATE;
 SELECT * INTO STRICT l FROM order_lines WHERE organization_id=org AND id=source_line FOR UPDATE;
 SELECT * INTO STRICT m FROM materials WHERE organization_id=org AND id=material FOR SHARE;
 source_unit:=upper(btrim(m.unit));
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
 IF h.status<>'active' OR h.current_revision_id<>revision OR
  (l.order_id,l.revision_id,l.material_id,l.canonical_unit) IS DISTINCT FROM
  (source_order,revision,material,unit) OR m.kind<>'finished' OR NOT m.active OR
  normalized IS DISTINCT FROM unit THEN
  RAISE EXCEPTION 'production source changed' USING ERRCODE='23000'; END IF;
END; $$;

CREATE FUNCTION protect_production_order() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE h orders%ROWTYPE; l order_lines%ROWTYPE; m materials%ROWTYPE;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable production' USING ERRCODE='23000'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'open' OR NEW.status<>'closed' OR NEW.version<>OLD.version+1 OR
   (to_jsonb(NEW)-ARRAY['status','version','closed_by','closed_at','close_reason']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['status','version','closed_by','closed_at','close_reason']) THEN
   RAISE EXCEPTION 'immutable production snapshot' USING ERRCODE='23000'; END IF;
  RETURN NEW;
 END IF;
 PERFORM require_production_source(NEW.organization_id,NEW.order_id,NEW.source_revision_id,
  NEW.order_line_id,NEW.material_id,NEW.canonical_unit);
 SELECT * INTO STRICT h FROM orders WHERE organization_id=NEW.organization_id AND id=NEW.order_id;
 SELECT * INTO STRICT l FROM order_lines WHERE organization_id=NEW.organization_id AND
 id=NEW.order_line_id;
 SELECT * INTO STRICT m FROM materials WHERE organization_id=NEW.organization_id AND
 id=NEW.material_id;
 IF NEW.status<>'open' OR NEW.version<>1 OR NEW.order_number<>h.order_number OR
  NEW.source_quantity<>l.quantity OR
  (NEW.own_code,NEW.material_name,NEW.specification) IS DISTINCT FROM
  (m.own_code,m.name,m.specification) OR
  (NEW.canonical_unit IN ('PCS','SET','台','箱','卷') AND
  NEW.planned_quantity<>trunc(NEW.planned_quantity)) THEN
  RAISE EXCEPTION 'invalid production snapshot' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER production_order_protect BEFORE INSERT OR UPDATE OR DELETE ON production_orders
 FOR EACH ROW EXECUTE FUNCTION protect_production_order();

CREATE FUNCTION protect_production_completion() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE h production_orders%ROWTYPE; completed numeric;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable completion' USING ERRCODE='23000'; END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 SELECT * INTO STRICT h FROM production_orders WHERE organization_id=NEW.organization_id
  AND id=NEW.production_order_id;
 IF TG_OP='INSERT' THEN
  PERFORM require_production_source(h.organization_id,h.order_id,h.source_revision_id,
   h.order_line_id,h.material_id,h.canonical_unit);
 END IF;
 SELECT * INTO STRICT h FROM production_orders WHERE organization_id=NEW.organization_id
  AND id=NEW.production_order_id FOR UPDATE;
 IF TG_OP='UPDATE' THEN
  IF OLD.status<>'active' OR NEW.status<>'void' OR NEW.version<>OLD.version+1 OR
   (to_jsonb(NEW)-ARRAY['status','version','void_by','void_at','void_reason']) IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['status','version','void_by','void_at','void_reason']) THEN
   RAISE EXCEPTION 'immutable completion snapshot' USING ERRCODE='23000'; END IF;
  RETURN NEW;
 END IF;
 SELECT COALESCE(sum(quantity),0) INTO completed FROM production_completions
  WHERE organization_id=h.organization_id AND production_order_id=h.id AND status='active';
 IF h.status<>'open' OR NEW.status<>'active' OR NEW.version<>1 OR NEW.material_id<>h.material_id OR
  completed+NEW.quantity>h.planned_quantity OR
  (h.canonical_unit IN ('PCS','SET','台','箱','卷') AND
   (NEW.quantity<>trunc(NEW.quantity) OR NEW.scrap_quantity<>trunc(NEW.scrap_quantity))) THEN
  RAISE EXCEPTION 'invalid production completion' USING ERRCODE='23000'; END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER production_completion_protect BEFORE INSERT OR UPDATE OR DELETE ON
production_completions
 FOR EACH ROW EXECUTE FUNCTION protect_production_completion();
REVOKE ALL ON FUNCTION require_production_source(uuid,uuid,uuid,uuid,uuid,text),
 protect_production_order(),protect_production_completion() FROM PUBLIC;
"""

LINK_DDL = """
CREATE UNIQUE INDEX inventory_production_receive_once ON
inventory_ledger(organization_id,production_completion_id)
 WHERE kind='production_receipt';
CREATE UNIQUE INDEX inventory_production_void_once ON
inventory_ledger(organization_id,production_completion_id)
 WHERE kind='production_receipt_void';
CREATE FUNCTION check_production_stock() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE completed_id uuid; c production_completions%ROWTYPE; h production_orders%ROWTYPE;
 original inventory_ledger%ROWTYPE; reversal inventory_ledger%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='inventory_ledger' THEN
  IF NEW.kind NOT IN ('production_receipt','production_receipt_void') THEN RETURN NULL; END IF;
  completed_id:=NEW.production_completion_id;
 ELSE completed_id:=NEW.id; END IF;
 SELECT * INTO STRICT c FROM production_completions WHERE organization_id=NEW.organization_id
 AND id=completed_id;
 SELECT * INTO STRICT h FROM production_orders WHERE organization_id=c.organization_id AND
 id=c.production_order_id;
 SELECT * INTO original FROM inventory_ledger WHERE organization_id=c.organization_id
  AND production_completion_id=c.id AND kind='production_receipt';
 IF c.quantity=0 THEN
  IF EXISTS(SELECT 1 FROM inventory_ledger WHERE organization_id=c.organization_id AND
  production_completion_id=c.id) THEN
   RAISE EXCEPTION 'scrap is not stock' USING ERRCODE='23000'; END IF;
  RETURN NULL;
 END IF;
 IF NOT FOUND OR original.material_id<>c.material_id OR original.delta<>c.quantity OR
  original.production_order_id<>c.production_order_id OR original.business_date<>c.business_date OR
  NOT EXISTS(SELECT 1 FROM inventory_accounts WHERE organization_id=c.organization_id
   AND material_id=c.material_id AND canonical_unit=h.canonical_unit) THEN
  RAISE EXCEPTION 'completion missing exact stock effect' USING ERRCODE='23000'; END IF;
 SELECT * INTO reversal FROM inventory_ledger WHERE organization_id=c.organization_id
  AND production_completion_id=c.id AND kind='production_receipt_void';
 IF c.status='active' AND FOUND THEN
  RAISE EXCEPTION 'active completion reversed' USING ERRCODE='23000'; END IF;
 IF c.status='void' AND (NOT FOUND OR reversal.material_id<>c.material_id OR
  reversal.delta<>-c.quantity OR reversal.reverses_id IS DISTINCT FROM original.id OR
  reversal.production_order_id<>c.production_order_id) THEN
  RAISE EXCEPTION 'void completion missing exact reversal' USING ERRCODE='23000'; END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER production_stock_completion AFTER INSERT OR UPDATE ON
production_completions
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_production_stock();
CREATE CONSTRAINT TRIGGER production_stock_ledger AFTER INSERT ON inventory_ledger
 DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_production_stock();
REVOKE ALL ON FUNCTION check_production_stock() FROM PUBLIC;
"""
