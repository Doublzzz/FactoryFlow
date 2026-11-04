"""Purchasing facts and deferred stock reconciliation for migration 0016."""

DDL = r"""
CREATE TABLE suppliers (
 organization_id uuid NOT NULL REFERENCES organizations(id), id uuid NOT NULL,
 full_name text NOT NULL CHECK(length(btrim(full_name)) BETWEEN 1 AND 200),
 contact text CHECK(length(contact)<=200), phone text CHECK(length(phone)<=100),
 address text CHECK(length(address)<=500), note text CHECK(length(note)<=1000),
 active boolean NOT NULL DEFAULT true, version bigint NOT NULL DEFAULT 1
CHECK(version>=1),
 created_by uuid NOT NULL, updated_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL
DEFAULT now(),
 PRIMARY KEY(organization_id,id),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,updated_by) REFERENCES users(organization_id,id)
);
CREATE TABLE purchase_orders (
 organization_id uuid NOT NULL, id uuid NOT NULL, supplier_id uuid NOT NULL,
 number text NOT NULL CHECK(length(btrim(number)) BETWEEN 1 AND 100),
 business_date date NOT NULL, supplier_name text NOT NULL, note text
CHECK(length(note)<=1000),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','closed')),
 version bigint NOT NULL DEFAULT 1 CHECK(version>=1), created_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), created_tx bigint
NOT NULL DEFAULT
txid_current(),
 closed_by uuid, closed_at timestamptz, close_reason text,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,number),
UNIQUE(organization_id,supplier_id,id),
 CHECK((status='closed' AND closed_by IS NOT NULL AND closed_at IS NOT NULL
  AND close_reason IS NOT NULL) OR (status='open' AND closed_by IS NULL
  AND closed_at IS NULL AND close_reason IS NULL)),
 CHECK(close_reason IS NULL OR length(btrim(close_reason)) BETWEEN 1 AND 500),
 FOREIGN KEY(organization_id,supplier_id) REFERENCES
suppliers(organization_id,id),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,closed_by) REFERENCES users(organization_id,id)
);
CREATE TABLE purchase_order_lines (
 organization_id uuid NOT NULL, id uuid NOT NULL, order_id uuid NOT NULL,
 line_number integer NOT NULL CHECK(line_number BETWEEN 1 AND 200), material_id
uuid NOT NULL,
 own_code text NOT NULL, material_name text NOT NULL, specification text,
canonical_unit text
NOT NULL,
 ordered_quantity numeric NOT NULL CHECK(ordered_quantity>0 AND
ordered_quantity<=9223372036854775.807 AND scale(ordered_quantity)<=3),
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,order_id,line_number),
 UNIQUE(organization_id,material_id,id),
 FOREIGN KEY(organization_id,order_id) REFERENCES
purchase_orders(organization_id,id),
 FOREIGN KEY(organization_id,material_id) REFERENCES
materials(organization_id,id)
);
CREATE TABLE purchase_receipts (
 organization_id uuid NOT NULL, id uuid NOT NULL, supplier_id uuid NOT NULL,
purchase_order_id uuid,
 number text NOT NULL CHECK(length(btrim(number)) BETWEEN 1 AND 100),
 business_date date NOT NULL, supplier_name text NOT NULL, note text
CHECK(length(note)<=1000),
 status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','void')),
 version bigint NOT NULL DEFAULT 1 CHECK(version>=1), created_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), created_tx bigint
NOT NULL DEFAULT
txid_current(),
 void_by uuid, void_at timestamptz, void_reason text,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,number),
 CHECK((status='void' AND void_by IS NOT NULL AND void_at IS NOT NULL
  AND void_reason IS NOT NULL) OR (status='active' AND void_by IS NULL
  AND void_at IS NULL AND void_reason IS NULL)),
 CHECK(void_reason IS NULL OR length(btrim(void_reason)) BETWEEN 1 AND 500),
 FOREIGN KEY(organization_id,supplier_id) REFERENCES
suppliers(organization_id,id),
 FOREIGN KEY(organization_id,supplier_id,purchase_order_id) REFERENCES
purchase_orders(organization_id,supplier_id,id),
 FOREIGN KEY(organization_id,created_by) REFERENCES users(organization_id,id),
 FOREIGN KEY(organization_id,void_by) REFERENCES users(organization_id,id)
);
CREATE TABLE purchase_receipt_lines (
 organization_id uuid NOT NULL, id uuid NOT NULL, receipt_id uuid NOT NULL,
 line_number integer NOT NULL CHECK(line_number BETWEEN 1 AND 200),
purchase_line_id uuid,
 material_id uuid NOT NULL, own_code text NOT NULL, material_name text NOT NULL,
 specification text, canonical_unit text NOT NULL,
 quantity numeric NOT NULL CHECK(quantity>0 AND quantity<=9223372036854775.807
AND
scale(quantity)<=3),
 PRIMARY KEY(organization_id,id),
UNIQUE(organization_id,receipt_id,line_number),
 UNIQUE(organization_id,material_id,id),
UNIQUE(organization_id,receipt_id,purchase_line_id),
 FOREIGN KEY(organization_id,receipt_id) REFERENCES
purchase_receipts(organization_id,id),
 FOREIGN KEY(organization_id,material_id) REFERENCES
materials(organization_id,id),
 FOREIGN KEY(organization_id,material_id,purchase_line_id) REFERENCES
purchase_order_lines(organization_id,material_id,id)
);
CREATE INDEX purchase_receipt_source ON
purchase_receipt_lines(organization_id,purchase_line_id);
CREATE FUNCTION purchasing_unit(source text) RETURNS text LANGUAGE sql IMMUTABLE
 SET search_path=pg_catalog,public,pg_temp AS $$
 SELECT CASE upper(btrim(source))
 WHEN 'PCS' THEN 'PCS' WHEN 'PCS.' THEN 'PCS' WHEN 'PC' THEN 'PCS' WHEN 'EA'
THEN 'PCS' WHEN '个'
THEN 'PCS' WHEN '件' THEN 'PCS'
 WHEN 'SET' THEN 'SET' WHEN '套' THEN 'SET' WHEN '台' THEN '台' WHEN '箱' THEN '箱'
WHEN '卷' THEN '卷'
 WHEN 'KG' THEN 'KG' WHEN 'KGS' THEN 'KG' WHEN '公斤' THEN 'KG' WHEN '千克' THEN
'KG'
 WHEN 'G' THEN 'G' WHEN '克' THEN 'G' WHEN 'LB' THEN 'LB' WHEN 'LBS' THEN 'LB'
WHEN '磅' THEN 'LB'
 WHEN 'OZ' THEN 'OZ' WHEN '盎司' THEN 'OZ' WHEN 'M' THEN 'M' WHEN '米' THEN 'M'
 WHEN 'MM' THEN 'MM' WHEN '毫米' THEN 'MM' WHEN 'CM' THEN 'CM' WHEN '厘米' THEN 'CM'
 WHEN 'KM' THEN 'KM' WHEN '千米' THEN 'KM' WHEN '公里' THEN 'KM' END
 $$;
CREATE FUNCTION protect_purchasing_header() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS
$$
DECLARE supplier suppliers%ROWTYPE;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'immutable purchasing evidence' USING
ERRCODE='23000';
END IF;
 PERFORM
pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 IF TG_TABLE_NAME='suppliers' THEN
  IF TG_OP='INSERT' AND (NEW.version<>1 OR NOT NEW.active) THEN RAISE EXCEPTION
'invalid
supplier'; END IF;
  IF TG_OP='UPDATE' AND (NEW.version<>OLD.version+1 OR
(to_jsonb(NEW)-ARRAY['full_name','contact','phone','address','note','active','version','updated_by','updated_at'])
IS DISTINCT FROM
(to_jsonb(OLD)-ARRAY['full_name','contact','phone','address','note','active','version','updated_by','updated_at']))
THEN
   RAISE EXCEPTION 'invalid supplier revision' USING ERRCODE='23000'; END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='INSERT' THEN
  SELECT * INTO STRICT supplier FROM suppliers WHERE
organization_id=NEW.organization_id AND
id=NEW.supplier_id;
  IF NOT supplier.active OR supplier.full_name<>NEW.supplier_name OR
NEW.version<>1 OR
NEW.created_tx<>txid_current()
   OR NEW.status<>(CASE TG_TABLE_NAME WHEN 'purchase_orders' THEN 'open' ELSE
'active' END) THEN
   RAISE EXCEPTION 'invalid purchasing creation' USING ERRCODE='23000'; END IF;
  IF TG_TABLE_NAME='purchase_receipts' AND
   (to_jsonb(NEW)->>'purchase_order_id') IS NOT NULL AND
NOT EXISTS
   (SELECT 1 FROM purchase_orders WHERE organization_id=NEW.organization_id AND
id=(to_jsonb(NEW)->>'purchase_order_id')::uuid AND status='open') THEN
   RAISE EXCEPTION 'purchase order closed' USING ERRCODE='23000'; END IF;
 ELSIF TG_TABLE_NAME='purchase_orders' THEN
  IF OLD.status<>'open' OR NEW.status<>'closed' OR NEW.version<>OLD.version+1 OR
(to_jsonb(NEW)-ARRAY['status','version','closed_by','closed_at','close_reason'])
IS DISTINCT FROM
(to_jsonb(OLD)-ARRAY['status','version','closed_by','closed_at','close_reason'])
THEN
   RAISE EXCEPTION 'immutable purchase order' USING ERRCODE='23000'; END IF;
 ELSE
  IF OLD.status<>'active' OR NEW.status<>'void' OR NEW.version<>OLD.version+1 OR
   (to_jsonb(NEW)-ARRAY['status','version','void_by','void_at','void_reason'])
IS DISTINCT FROM
   (to_jsonb(OLD)-ARRAY['status','version','void_by','void_at','void_reason'])
THEN
   RAISE EXCEPTION 'immutable purchase receipt' USING ERRCODE='23000'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER suppliers_guard BEFORE INSERT OR UPDATE OR DELETE ON suppliers
FOR EACH ROW
EXECUTE FUNCTION protect_purchasing_header();
CREATE TRIGGER purchase_orders_guard BEFORE INSERT OR UPDATE OR DELETE ON
purchase_orders FOR
EACH ROW EXECUTE FUNCTION protect_purchasing_header();
CREATE TRIGGER purchase_receipts_guard BEFORE INSERT OR UPDATE OR DELETE ON
purchase_receipts
FOR EACH ROW EXECUTE FUNCTION protect_purchasing_header();
CREATE FUNCTION protect_purchasing_line() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS
$$
DECLARE h record; m materials%ROWTYPE; p purchase_order_lines%ROWTYPE; qty
numeric; command text;
BEGIN
 IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'immutable purchase line' USING
ERRCODE='23000'; END IF;
 PERFORM
pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text||chr(58)||'materials',0));
 IF TG_TABLE_NAME='purchase_order_lines' THEN
  SELECT * INTO STRICT h FROM purchase_orders WHERE
organization_id=NEW.organization_id AND
id=NEW.order_id;
  qty:=NEW.ordered_quantity; command:='purchase_order.create';
 ELSE
  SELECT * INTO STRICT h FROM purchase_receipts WHERE
organization_id=NEW.organization_id AND
id=NEW.receipt_id;
  qty:=NEW.quantity; command:='purchase_receipt.create';
 END IF;
 IF h.created_tx<>txid_current() OR EXISTS(SELECT 1 FROM audit_events WHERE
organization_id=NEW.organization_id AND entity_id=h.id AND command_type=command)
THEN
  RAISE EXCEPTION 'sealed purchasing document' USING ERRCODE='23000'; END IF;
 SELECT * INTO STRICT m FROM materials WHERE organization_id=NEW.organization_id
AND
id=NEW.material_id;
 IF m.kind<>'raw' OR NOT m.active OR NEW.canonical_unit IS DISTINCT FROM
purchasing_unit(m.unit) OR
  (NEW.canonical_unit IN ('PCS','SET','台','箱','卷') AND qty<>trunc(qty)) THEN
  RAISE EXCEPTION 'invalid raw material unit' USING ERRCODE='23000'; END IF;
 IF TG_TABLE_NAME='purchase_receipt_lines' AND
  (to_jsonb(h)->>'purchase_order_id') IS NOT NULL
THEN
  SELECT * INTO STRICT p FROM purchase_order_lines WHERE
organization_id=NEW.organization_id AND
id=NEW.purchase_line_id;
  IF p.order_id<>(to_jsonb(h)->>'purchase_order_id')::uuid OR p.material_id<>NEW.material_id OR
   (p.own_code,p.material_name,p.specification,p.canonical_unit) IS DISTINCT
FROM
   (NEW.own_code,NEW.material_name,NEW.specification,NEW.canonical_unit) THEN
   RAISE EXCEPTION 'invalid purchase line source' USING ERRCODE='23000'; END IF;
 ELSIF TG_TABLE_NAME='purchase_receipt_lines' AND
 (to_jsonb(NEW)->>'purchase_line_id') IS NOT
NULL THEN
  RAISE EXCEPTION 'direct receipt has purchase source' USING ERRCODE='23000';
 ELSIF (m.own_code,m.name,m.specification) IS DISTINCT FROM
(NEW.own_code,NEW.material_name,NEW.specification) THEN
  RAISE EXCEPTION 'invalid material snapshot' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER purchase_order_lines_guard BEFORE INSERT OR UPDATE OR DELETE ON
purchase_order_lines FOR EACH ROW EXECUTE FUNCTION protect_purchasing_line();
CREATE TRIGGER purchase_receipt_lines_guard BEFORE INSERT OR UPDATE OR DELETE ON
purchase_receipt_lines FOR EACH ROW EXECUTE FUNCTION protect_purchasing_line();
CREATE FUNCTION check_purchasing_document() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS
$$
DECLARE header_id uuid; n bigint; command text;
BEGIN
 IF TG_TABLE_NAME IN ('purchase_orders','purchase_order_lines') THEN
  header_id:=COALESCE((to_jsonb(NEW)->>'order_id')::uuid,NEW.id);
  SELECT count(*) INTO n FROM purchase_order_lines WHERE
organization_id=NEW.organization_id AND
order_id=header_id;
  command:='purchase_order.create';
 ELSE
  header_id:=COALESCE((to_jsonb(NEW)->>'receipt_id')::uuid,NEW.id);
  SELECT count(*) INTO n FROM purchase_receipt_lines WHERE
organization_id=NEW.organization_id
AND receipt_id=header_id;
  command:='purchase_receipt.create';
  IF EXISTS(SELECT 1 FROM purchase_order_lines p WHERE
p.organization_id=NEW.organization_id AND
   (SELECT COALESCE(sum(l.quantity),0) FROM purchase_receipt_lines l JOIN
purchase_receipts r ON
    r.organization_id=l.organization_id AND r.id=l.receipt_id WHERE
l.organization_id=p.organization_id
    AND l.purchase_line_id=p.id AND r.status='active')>p.ordered_quantity) THEN
   RAISE EXCEPTION 'purchase over receipt' USING ERRCODE='23000'; END IF;
 END IF;
 IF n NOT BETWEEN 1 AND 200 OR NOT EXISTS(SELECT 1 FROM audit_events WHERE
organization_id=NEW.organization_id AND entity_id=header_id AND
command_type=command) THEN
  RAISE EXCEPTION 'incomplete purchasing document' USING ERRCODE='23000'; END
IF;
 IF TG_OP='UPDATE' AND NOT EXISTS(SELECT 1 FROM audit_events
  WHERE organization_id=NEW.organization_id AND entity_id=header_id AND
  command_type=CASE TG_TABLE_NAME WHEN 'purchase_orders'
   THEN 'purchase_order.close' ELSE 'purchase_receipt.void' END) THEN
  RAISE EXCEPTION 'missing purchasing transition audit' USING ERRCODE='23000';
 END IF;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER purchase_order_complete AFTER INSERT OR UPDATE ON
purchase_orders
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_document();
CREATE CONSTRAINT TRIGGER purchase_order_lines_complete AFTER INSERT ON
purchase_order_lines
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_document();
CREATE CONSTRAINT TRIGGER purchase_receipt_complete AFTER INSERT OR UPDATE ON
purchase_receipts
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_document();
CREATE CONSTRAINT TRIGGER purchase_receipt_lines_complete AFTER INSERT ON
purchase_receipt_lines
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_document();
REVOKE ALL ON FUNCTION
protect_purchasing_header(),protect_purchasing_line(),check_purchasing_document(),purchasing_unit(text)
FROM PUBLIC;
"""

LINK_DDL = r"""
CREATE UNIQUE INDEX inventory_purchase_receive_once ON
inventory_ledger(organization_id,purchase_receipt_line_id) WHERE
kind='purchase_receipt';
CREATE UNIQUE INDEX inventory_purchase_void_once ON
inventory_ledger(organization_id,purchase_receipt_line_id) WHERE
kind='purchase_receipt_void';
CREATE FUNCTION check_purchasing_stock() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS
$$
DECLARE receipt_id uuid; h purchase_receipts%ROWTYPE; l
purchase_receipt_lines%ROWTYPE;
 original inventory_ledger%ROWTYPE; reversal inventory_ledger%ROWTYPE;
BEGIN
 IF TG_TABLE_NAME='inventory_ledger' THEN
  IF NEW.kind NOT IN ('purchase_receipt','purchase_receipt_void') THEN RETURN
NULL; END IF;
  SELECT x.receipt_id INTO STRICT receipt_id FROM purchase_receipt_lines x WHERE
x.organization_id=NEW.organization_id AND x.id=NEW.purchase_receipt_line_id;
 ELSIF TG_TABLE_NAME='purchase_receipt_lines' THEN receipt_id:=NEW.receipt_id;
 ELSE receipt_id:=NEW.id; END IF;
 SELECT * INTO STRICT h FROM purchase_receipts WHERE
organization_id=NEW.organization_id AND
id=receipt_id;
 FOR l IN SELECT * FROM purchase_receipt_lines WHERE
organization_id=h.organization_id AND
purchase_receipt_lines.receipt_id=h.id LOOP
  SELECT * INTO original FROM inventory_ledger WHERE
organization_id=h.organization_id AND
purchase_receipt_line_id=l.id AND kind='purchase_receipt';
  IF NOT FOUND OR original.material_id<>l.material_id OR
original.delta<>l.quantity OR
original.business_date<>h.business_date
   OR NOT EXISTS(SELECT 1 FROM inventory_accounts a WHERE
a.organization_id=h.organization_id
AND a.material_id=l.material_id AND a.canonical_unit=l.canonical_unit) THEN
   RAISE EXCEPTION 'receipt missing exact inventory effect' USING
ERRCODE='23000'; END IF;
  SELECT * INTO reversal FROM inventory_ledger WHERE
organization_id=h.organization_id AND
purchase_receipt_line_id=l.id AND kind='purchase_receipt_void';
  IF h.status='active' AND FOUND THEN RAISE EXCEPTION 'active receipt reversed'
USING
ERRCODE='23000'; END IF;
  IF h.status='void' AND (NOT FOUND OR reversal.material_id<>l.material_id OR
reversal.delta<>-l.quantity OR reversal.reverses_id IS DISTINCT FROM
original.id) THEN
   RAISE EXCEPTION 'void receipt missing exact reversal' USING ERRCODE='23000';
END IF;
 END LOOP;
 RETURN NULL;
END; $$;
CREATE CONSTRAINT TRIGGER purchasing_stock_header AFTER INSERT OR UPDATE ON
purchase_receipts
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_stock();
CREATE CONSTRAINT TRIGGER purchasing_stock_line AFTER INSERT ON
purchase_receipt_lines
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION
check_purchasing_stock();
CREATE CONSTRAINT TRIGGER purchasing_stock_ledger AFTER INSERT ON
inventory_ledger DEFERRABLE
INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_purchasing_stock();
REVOKE ALL ON FUNCTION check_purchasing_stock() FROM PUBLIC;
"""
