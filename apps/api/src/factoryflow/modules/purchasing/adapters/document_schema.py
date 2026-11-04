"""0018: optional source/print facts on the existing immutable purchase documents."""

DDL = r"""
ALTER TABLE purchase_orders
 ADD COLUMN currency text CHECK(currency IN ('CNY','USD')),
 ADD COLUMN buyer_name text CHECK(buyer_name IS NULL OR
   length(btrim(buyer_name)) BETWEEN 1 AND 200),
 ADD COLUMN source_id uuid,
 ADD COLUMN extraction_id uuid,
 ADD CONSTRAINT purchase_order_source_unique UNIQUE(organization_id,source_id),
 ADD CONSTRAINT purchase_order_source_fk FOREIGN KEY(organization_id,source_id)
   REFERENCES source_files(organization_id,id),
 ADD CONSTRAINT purchase_order_extraction_fk FOREIGN KEY(organization_id,source_id,extraction_id)
   REFERENCES extraction_runs(organization_id,source_id,id),
 ADD CONSTRAINT purchase_order_extraction_source
   CHECK(extraction_id IS NULL OR source_id IS NOT NULL);
ALTER TABLE purchase_order_lines
 ADD COLUMN source_unit_price text CHECK(source_unit_price IS NULL OR
   source_unit_price ~ '^[0-9]{1,18}(\.[0-9]{1,6})?$'),
 ADD COLUMN source_amount text CHECK(source_amount IS NULL OR
   source_amount ~ '^[0-9]{1,18}(\.[0-9]{1,6})?$');

CREATE FUNCTION protect_purchase_source() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE source source_files%ROWTYPE;
BEGIN
 IF NEW.source_id IS NOT NULL THEN
  SELECT * INTO STRICT source FROM source_files
    WHERE organization_id=NEW.organization_id AND id=NEW.source_id;
  IF source.purpose<>'purchase_order' THEN
   RAISE EXCEPTION 'wrong source purpose' USING ERRCODE='23000'; END IF;
  IF source.media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    AND NEW.extraction_id IS NULL THEN
   RAISE EXCEPTION 'spreadsheet requires extraction' USING ERRCODE='23000'; END IF;
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER purchase_orders_source_guard BEFORE INSERT ON purchase_orders
 FOR EACH ROW EXECUTE FUNCTION protect_purchase_source();

CREATE FUNCTION protect_purchase_money() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF (NEW.source_unit_price IS NOT NULL OR NEW.source_amount IS NOT NULL)
 AND NOT EXISTS(SELECT 1 FROM purchase_orders WHERE organization_id=NEW.organization_id
   AND id=NEW.order_id AND currency IS NOT NULL) THEN
  RAISE EXCEPTION 'purchase currency required' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER purchase_order_lines_money BEFORE INSERT ON purchase_order_lines
 FOR EACH ROW EXECUTE FUNCTION protect_purchase_money();
"""
