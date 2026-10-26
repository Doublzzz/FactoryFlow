"""Expand currencies without rewriting confirmed evidence or old migrations."""

DDL = """
ALTER TABLE orders DROP CONSTRAINT orders_currency_check;
ALTER TABLE orders ADD CONSTRAINT orders_currency_check CHECK(currency IN ('CNY','USD'));
CREATE FUNCTION guard_order_currency() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.currency IS DISTINCT FROM OLD.currency THEN
  RAISE EXCEPTION 'immutable order currency' USING ERRCODE='23000';
 END IF;
 RETURN NEW;
END; $$;
CREATE TRIGGER order_currency_guard BEFORE UPDATE OF currency ON orders
 FOR EACH ROW EXECUTE FUNCTION guard_order_currency();
"""
