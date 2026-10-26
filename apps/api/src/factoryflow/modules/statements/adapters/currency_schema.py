"""One immutable currency per statement, enforced at every source-claim entry."""

DDL = """
ALTER TABLE statements ADD COLUMN currency text NOT NULL DEFAULT 'CNY'
 CHECK(currency IN ('CNY','USD'));
ALTER TABLE statements DROP CONSTRAINT statement_period_unique;
ALTER TABLE statements ADD CONSTRAINT statement_period_unique
 UNIQUE(organization_id,customer_id,period_start,period_end,currency);

CREATE FUNCTION guard_statement_currency() RETURNS trigger LANGUAGE plpgsql
 SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE line uuid; snapshot jsonb; actual text; target text;
BEGIN
 IF TG_TABLE_NAME IN ('statement_lines','statement_approvals','statement_reviews') THEN
  line:=NEW.order_line_id; snapshot:=NEW.source;
 ELSIF TG_TABLE_NAME='statement_allocations' THEN
  SELECT order_line_id,source INTO line,snapshot FROM statement_approvals
   WHERE organization_id=NEW.organization_id AND id=NEW.approval_id;
 ELSE
  SELECT order_line_id,source INTO line,snapshot FROM statement_reviews
   WHERE organization_id=NEW.organization_id AND id=NEW.review_id;
 END IF;
 SELECT o.currency INTO actual FROM order_lines l JOIN orders o
  ON o.organization_id=l.organization_id AND o.id=l.order_id
  WHERE l.organization_id=NEW.organization_id AND l.id=line;
 SELECT currency INTO target FROM statements
  WHERE organization_id=NEW.organization_id AND id=NEW.statement_id;
 IF actual IS NULL OR target IS NULL OR actual IS DISTINCT FROM target
  OR COALESCE(snapshot->>'currency','CNY') IS DISTINCT FROM actual THEN
  RAISE EXCEPTION 'statement source currency mismatch' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER statement_line_currency_guard BEFORE INSERT OR UPDATE ON statement_lines
 FOR EACH ROW EXECUTE FUNCTION guard_statement_currency();
CREATE TRIGGER statement_approval_currency_guard BEFORE INSERT OR UPDATE ON statement_approvals
 FOR EACH ROW EXECUTE FUNCTION guard_statement_currency();
CREATE TRIGGER statement_review_currency_guard BEFORE INSERT OR UPDATE ON statement_reviews
 FOR EACH ROW EXECUTE FUNCTION guard_statement_currency();
CREATE TRIGGER statement_allocation_currency_guard BEFORE INSERT OR UPDATE ON statement_allocations
 FOR EACH ROW EXECUTE FUNCTION guard_statement_currency();
CREATE TRIGGER statement_transfer_currency_guard
 BEFORE INSERT OR UPDATE ON statement_review_transfers
 FOR EACH ROW EXECUTE FUNCTION guard_statement_currency();
"""
