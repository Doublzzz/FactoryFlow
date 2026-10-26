from sqlalchemy import text


class CustomerRepository:
    def lock(self, organization_id, customer_id):
        row = (
            self.conn.execute(
                text(
                    "SELECT id,full_name FROM customers WHERE organization_id=:org "
                    "AND id=:id FOR UPDATE"
                ),
                {"org": organization_id, "id": customer_id},
            )
            .mappings()
            .first()
        )
        return self.view(row) if row else None

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def view(row):
        return {"id": str(row["id"]), "full_name": row["full_name"]}

    def get(self, organization_id, customer_id):
        row = (
            self.conn.execute(
                text("SELECT id,full_name FROM customers WHERE organization_id=:org AND id=:id"),
                {"org": organization_id, "id": customer_id},
            )
            .mappings()
            .first()
        )
        return self.view(row) if row else None

    def insert(self, organization_id, customer_id, full_name):
        self.conn.execute(
            text("INSERT INTO customers (id,organization_id,full_name) VALUES (:id,:org,:name)"),
            {"id": customer_id, "org": organization_id, "name": full_name},
        )
        return {"id": str(customer_id), "full_name": full_name}

    def list(self, organization_id):
        rows = self.conn.execute(
            text(
                "SELECT id,full_name FROM customers "
                "WHERE organization_id=:org ORDER BY full_name,id LIMIT 1000"
            ),
            {"org": organization_id},
        ).mappings()
        return [self.view(row) for row in rows]
