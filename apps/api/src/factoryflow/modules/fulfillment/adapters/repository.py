import json
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


class DeliveryRepository:
    def settlement_sources(self, actor, customer_id, end_date, cursor, limit):
        params = {
            "org": actor.organization_id,
            "customer": customer_id,
            "end": end_date,
            "limit": limit + 1,
        }
        condition = ""
        if cursor:
            try:
                delivery, line = cursor.split(":")
                params.update(delivery=UUID(delivery), line=UUID(line))
            except ValueError, AttributeError:
                raise BusinessError("INVALID_CURSOR") from None
            condition = " AND (d.id,dl.order_line_id)>(:delivery,:line)"
        rows = list(
            self.conn.execute(
                text(
                    "SELECT dl.*,d.customer_id,d.delivery_date "
                    "FROM deliveries d JOIN delivery_lines dl "
                    "ON d.organization_id=dl.organization_id AND d.id=dl.delivery_id "
                    "WHERE d.organization_id=:org AND d.customer_id=:customer "
                    "AND d.status='active' "
                    "AND d.delivery_date<=:end"
                    + condition
                    + " ORDER BY d.id,dl.order_line_id LIMIT :limit"
                ),
                params,
            ).mappings()
        )
        more, rows = len(rows) > limit, rows[:limit]
        items = [
            {
                key: (str(value) if isinstance(value, (UUID, Decimal)) else value)
                for key, value in row.items()
            }
            for row in rows
        ]
        for item in items:
            item["delivery_date"] = item["delivery_date"].isoformat()
        return {
            "items": items,
            "next_cursor": f"{rows[-1]['delivery_id']}:{rows[-1]['order_line_id']}"
            if more
            else None,
        }

    def __init__(self, conn):
        self.conn = conn

    def insert(self, actor, identifier, request, order, customer, lines):
        self.conn.execute(
            text("""INSERT INTO deliveries
          (id,organization_id,order_id,customer_id,revision_id,delivery_date,customer_name,order_number)
          VALUES (:id,:org,:order,:customer,:revision,:date,:name,:number)"""),
            {
                "id": identifier,
                "org": actor.organization_id,
                "order": request.order_id,
                "customer": request.customer_id,
                "revision": request.revision_id,
                "date": request.delivery_date,
                "name": customer["full_name"],
                "number": order["order_number"],
            },
        )
        for line in lines:
            self.conn.execute(
                text("""INSERT INTO delivery_lines
             (organization_id,delivery_id,order_id,revision_id,order_line_id,line_number,quantity,
              description,source_unit,canonical_unit,quantity_policy)
             VALUES (:org,:delivery,:order,:revision,:line,:number,:quantity,:description,
                     :unit,:canonical,CAST(:policy AS jsonb))"""),
                {
                    "org": actor.organization_id,
                    "delivery": identifier,
                    "order": request.order_id,
                    "revision": request.revision_id,
                    "line": line["id"],
                    "number": line["line_number"],
                    "quantity": Decimal(line["quantity"]),
                    "description": line["description"],
                    "unit": line["source_unit"],
                    "canonical": line["canonical_unit"],
                    "policy": json.dumps(line["quantity_policy"]),
                },
            )

    @staticmethod
    def header(row):
        return {
            "id": str(row["id"]),
            "order_id": str(row["order_id"]),
            "customer_id": str(row["customer_id"]),
            "revision_id": str(row["revision_id"]),
            "customer_name": row["customer_name"],
            "order_number": row["order_number"],
            "delivery_date": row["delivery_date"].isoformat(),
            "status": row["status"],
            "version": row["version"],
            "void_reason": row["void_reason"],
            "created_at": row["created_at"].isoformat(),
            "voided_at": row["voided_at"].isoformat() if row["voided_at"] else None,
        }

    def inventory_snapshots(self, actor, identifier, snapshots):
        for line_id, snapshot in snapshots.items():
            self.conn.execute(
                text("""INSERT INTO delivery_inventory_snapshots
                (organization_id,delivery_id,order_line_id,state,material_id,canonical_unit,
                 quantity,movement_id,reason,mode,shortage_confirmed)
                VALUES(:org,:delivery,:line,:state,:material_id,:canonical_unit,:quantity,
                       :movement_id,:reason,:mode,:shortage_confirmed)"""),
                {
                    "org": actor.organization_id,
                    "delivery": identifier,
                    "line": line_id,
                    **snapshot,
                },
            )

    @staticmethod
    def inventory_view(line):
        if line["inventory_state"] is None:
            return None
        return {
            "state": line["inventory_state"],
            "material_id": str(line["inventory_material_id"])
            if line["inventory_material_id"]
            else None,
            "canonical_unit": line["canonical_unit"],
            "quantity": format(line["quantity"], "f"),
            "movement_id": str(line["movement_id"]) if line["movement_id"] else None,
            "reason": line["inventory_reason"],
            "mode": line["inventory_mode"],
            "shortage_confirmed": line["shortage_confirmed"],
        }

    def get(self, actor, identifier, lock=False, *, inventory=False):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM deliveries WHERE organization_id=:org AND id=:id"
                    + (" FOR UPDATE" if lock else "")
                ),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("DELIVERY_NOT_FOUND", 404)
        # Inventory is a delivery-detail projection. Public settlement/archive sources
        # retain their original shape, including when constructing legacy migration fixtures.
        inventory_columns = (
            (
                ",s.state AS inventory_state,s.material_id AS inventory_material_id,"
                "s.movement_id,s.reason AS inventory_reason,s.mode AS inventory_mode,"
                "s.shortage_confirmed"
            )
            if inventory
            else ""
        )
        inventory_join = (
            (
                " LEFT JOIN delivery_inventory_snapshots s "
                "ON s.organization_id=l.organization_id AND s.delivery_id=l.delivery_id "
                "AND s.order_line_id=l.order_line_id"
            )
            if inventory
            else ""
        )
        lines = self.conn.execute(
            text(
                "SELECT l.*"
                + inventory_columns
                + " FROM delivery_lines l"
                + inventory_join
                + " WHERE l.organization_id=:org "
                "AND l.delivery_id=:id ORDER BY l.line_number"
            ),
            {"org": actor.organization_id, "id": identifier},
        ).mappings()
        return {
            **self.header(row),
            "lines": [
                {
                    "order_line_id": str(line["order_line_id"]),
                    "line_number": line["line_number"],
                    "quantity": format(line["quantity"], "f"),
                    "description": line["description"],
                    "source_unit": line["source_unit"],
                    "canonical_unit": line["canonical_unit"],
                    "quantity_policy": line["quantity_policy"],
                    **({"inventory": self.inventory_view(line)} if inventory else {}),
                }
                for line in lines
            ],
        }

    def action(self, actor, identifier, action, reverses_id, reason):
        self.conn.execute(
            text("""INSERT INTO fulfillment_actions
          (id,organization_id,delivery_id,action,reverses_id,reason,actor_id)
          VALUES (:id,:org,:delivery,:action,:reverses,:reason,:actor)"""),
            {
                "id": uuid7(),
                "org": actor.organization_id,
                "delivery": identifier,
                "action": action,
                "reverses": reverses_id,
                "reason": reason,
                "actor": actor.user_id,
            },
        )

    def create_action(self, actor, identifier):
        return self.conn.execute(
            text(
                "SELECT id FROM fulfillment_actions WHERE organization_id=:org "
                "AND delivery_id=:id AND action='create'"
            ),
            {"org": actor.organization_id, "id": identifier},
        ).scalar_one()

    def mark_void(self, actor, identifier, reason):
        self.conn.execute(
            text(
                "UPDATE deliveries SET status='void',version=2,void_reason=:reason,"
                "voided_at=now() WHERE organization_id=:org AND id=:id"
            ),
            {"org": actor.organization_id, "id": identifier, "reason": reason},
        )

    def list(self, actor, customer_id, cursor, limit, order_id):
        conditions = ""
        params = {"org": actor.organization_id, "limit": limit + 1}
        for key, value in (("customer_id", customer_id), ("order_id", order_id)):
            if value is not None:
                conditions += f" AND {key}=:{key}"
                params[key] = value
        if cursor:
            try:
                params["cursor"] = UUID(cursor)
            except ValueError:
                raise BusinessError("INVALID_CURSOR", field="cursor") from None
            conditions += " AND id<:cursor"
        rows = list(
            self.conn.execute(
                text(
                    "SELECT * FROM deliveries WHERE organization_id=:org"
                    + conditions
                    + " ORDER BY id DESC LIMIT :limit"
                ),
                params,
            ).mappings()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": [self.header(row) for row in rows],
            "next_cursor": str(rows[-1]["id"]) if more else None,
        }
