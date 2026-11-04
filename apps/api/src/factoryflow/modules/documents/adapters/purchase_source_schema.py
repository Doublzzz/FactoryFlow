"""0018 extends source purposes without rewriting existing immutable evidence."""

DDL = r"""
ALTER TABLE source_files ADD COLUMN purpose text NOT NULL DEFAULT 'sales_order'
 CHECK(purpose IN ('sales_order','purchase_order'));
ALTER TABLE source_files DROP CONSTRAINT source_files_organization_id_original_sha256_key;
ALTER TABLE source_files ADD CONSTRAINT source_files_purpose_sha256_key
 UNIQUE(organization_id,purpose,original_sha256);
ALTER TABLE source_files DROP CONSTRAINT source_files_media_type_check;
ALTER TABLE source_files ADD CONSTRAINT source_files_media_type_check CHECK(
 media_type IN ('image/png','image/jpeg','application/pdf') OR
 (purpose='purchase_order' AND
 media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'));

CREATE FUNCTION protect_sales_source_purpose() RETURNS trigger
 LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM source_files WHERE organization_id=NEW.organization_id
 AND id=NEW.source_id AND purpose='sales_order') THEN
  RAISE EXCEPTION 'wrong source purpose' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER source_imports_purpose BEFORE INSERT ON source_imports
 FOR EACH ROW EXECUTE FUNCTION protect_sales_source_purpose();
"""
