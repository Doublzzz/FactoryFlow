DDL = """
CREATE TABLE orders (
 id uuid NOT NULL, organization_id uuid NOT NULL, customer_id uuid NOT NULL,
 order_number text NOT NULL CHECK (length(btrim(order_number)) BETWEEN 1 AND 100),
 business_date date NOT NULL, currency text NOT NULL CHECK (currency='CNY'),
 current_revision_id uuid NOT NULL, version integer NOT NULL CHECK (version > 0),
 status text NOT NULL CHECK (status IN ('active','deleted')),
 created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (organization_id,id),
 UNIQUE (organization_id,id,customer_id),
 CONSTRAINT orders_number_unique UNIQUE (organization_id,customer_id,order_number),
 FOREIGN KEY (organization_id,customer_id) REFERENCES customers(organization_id,id),
 FOREIGN KEY (organization_id,current_revision_id,id,customer_id)
  REFERENCES confirmed_revisions(organization_id,id,order_id,customer_id)
);
ALTER TABLE confirmed_revisions ADD CONSTRAINT revisions_order_owner
 FOREIGN KEY (organization_id,order_id,customer_id)
 REFERENCES orders(organization_id,id,customer_id)
 DEFERRABLE INITIALLY DEFERRED;
CREATE TABLE order_lines (
 id uuid NOT NULL, organization_id uuid NOT NULL, order_id uuid NOT NULL, revision_id uuid NOT NULL,
 line_number integer NOT NULL CHECK (line_number > 0), description text NOT NULL,
 quantity numeric NOT NULL CHECK (quantity >= 0 AND quantity <= 9223372036854775.807
                                  AND quantity = trunc(quantity,3)),
 delivered_quantity numeric NOT NULL DEFAULT 0 CHECK
   (delivered_quantity >= 0 AND delivered_quantity <= quantity
    AND delivered_quantity = trunc(delivered_quantity,3)),
 source_quantity_text text NOT NULL, source_unit text, canonical_unit text,
 quantity_policy jsonb NOT NULL, source_unit_price text, source_amount text,
 PRIMARY KEY (organization_id,id), UNIQUE (organization_id,revision_id,line_number),
 FOREIGN KEY (organization_id,order_id) REFERENCES orders(organization_id,id),
 FOREIGN KEY (organization_id,order_id,revision_id)
  REFERENCES confirmed_revisions(organization_id,order_id,id)
);
CREATE INDEX orders_customer_page ON orders(organization_id,customer_id,id DESC);
CREATE INDEX lines_current_revision ON order_lines(organization_id,revision_id,line_number);
CREATE TABLE order_events (
 id uuid PRIMARY KEY, organization_id uuid NOT NULL, order_id uuid NOT NULL,
 action text NOT NULL, version integer NOT NULL, revision_id uuid NOT NULL,
 reason text, actor_id uuid NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (organization_id,order_id,version),
 FOREIGN KEY (organization_id,order_id) REFERENCES orders(organization_id,id),
 FOREIGN KEY (organization_id,actor_id) REFERENCES users(organization_id,id),
 FOREIGN KEY (organization_id,order_id,revision_id)
  REFERENCES confirmed_revisions(organization_id,order_id,id)
);
"""
