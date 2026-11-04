"""0016 classification; historical 0013/0014 migrations remain reproducible."""

DDL = """
ALTER TABLE materials ADD COLUMN kind text NOT NULL DEFAULT 'finished'
 CHECK(kind IN ('finished','raw'));
CREATE FUNCTION protect_material_kind() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF NEW.kind<>OLD.kind THEN
  RAISE EXCEPTION 'immutable material kind' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER materials_kind_immutable BEFORE UPDATE OF kind ON materials
 FOR EACH ROW EXECUTE FUNCTION protect_material_kind();

CREATE FUNCTION require_finished_material_binding() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF NEW.material_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM materials
  WHERE organization_id=NEW.organization_id AND id=NEW.material_id AND kind='finished') THEN
  RAISE EXCEPTION 'customer orders require finished material' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER order_line_material_kind BEFORE INSERT OR UPDATE OF material_id ON order_lines
 FOR EACH ROW EXECUTE FUNCTION require_finished_material_binding();
CREATE TRIGGER customer_code_material_kind
 BEFORE INSERT OR UPDATE OF material_id ON customer_material_codes
 FOR EACH ROW EXECUTE FUNCTION require_finished_material_binding();
"""
