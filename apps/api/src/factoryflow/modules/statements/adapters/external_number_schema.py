"""Add customer document metadata without changing frozen source snapshots."""

DDL = r"""
ALTER TABLE statement_lines ADD COLUMN external_document_number text NOT NULL DEFAULT ''
 CHECK (length(external_document_number)<=120
 AND external_document_number !~ '[[:cntrl:]]');
ALTER TABLE statement_approvals ADD COLUMN external_document_number text NOT NULL DEFAULT ''
 CHECK (length(external_document_number)<=120
 AND external_document_number !~ '[[:cntrl:]]');
ALTER TABLE statement_reviews ADD COLUMN external_document_number text NOT NULL DEFAULT ''
 CHECK (length(external_document_number)<=120
 AND external_document_number !~ '[[:cntrl:]]');
CREATE OR REPLACE FUNCTION guard_statement_claim() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_claim numeric:=0; new_claim numeric:=0; src record; head record;
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'retain statement source' USING ERRCODE='23000'; END IF;
 IF TG_OP='UPDATE' THEN
 IF (to_jsonb(NEW)-ARRAY['quantity','unit_price','status','reason','external_document_number'])
 IS DISTINCT FROM
 (to_jsonb(OLD)-ARRAY['quantity','unit_price','status','reason','external_document_number']) THEN
 RAISE EXCEPTION 'immutable statement source' USING ERRCODE='23000'; END IF;
 IF NEW.external_document_number IS DISTINCT FROM OLD.external_document_number
 AND NOT EXISTS (SELECT 1 FROM statements WHERE organization_id=OLD.organization_id
 AND id=OLD.statement_id AND status='draft') THEN
 RAISE EXCEPTION 'immutable external document number' USING ERRCODE='23000'; END IF;
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

"""
