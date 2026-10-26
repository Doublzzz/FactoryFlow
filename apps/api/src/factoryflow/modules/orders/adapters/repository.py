"""Owned order persistence; open-lines has a read-only customer-name projection."""

import base64
import json
from dataclasses import asdict
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from sqlalchemy import text


def decimal_text(value):
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


class OrderRepository:
    def settlement_sources(self, actor, identifiers):
        if not identifiers:
            return []
        rows = self.conn.execute(
            text(
                "SELECT l.*,o.customer_id,o.currency FROM order_lines l JOIN orders o "
                "ON o.organization_id=l.organization_id AND o.id=l.order_id "
                "WHERE l.organization_id=:org AND l.id=ANY(:ids)"
            ),
            {"org": actor.organization_id, "ids": [UUID(str(value)) for value in identifiers]},
        ).mappings()
        return [
            {
                **self.line_view(row),
                "order_id": str(row["order_id"]),
                "revision_id": str(row["revision_id"]),
                "customer_id": str(row["customer_id"]),
                "currency": row["currency"],
            }
            for row in rows
        ]

    def __init__(self, conn):
        self.conn = conn

    def apply_delivery(self, actor, order_id, quantities, reverse):
        for identifier, quantity in quantities.items():
            self.conn.execute(
                text(
                    "UPDATE order_lines SET delivered_quantity=delivered_quantity+:delta "
                    "WHERE organization_id=:org AND order_id=:order AND id=:id"
                ),
                {
                    "delta": Decimal(quantity) * (-1 if reverse else 1),
                    "org": actor.organization_id,
                    "order": order_id,
                    "id": identifier,
                },
            )
        self.conn.execute(
            text("UPDATE orders SET version=version+1 WHERE organization_id=:org AND id=:id"),
            {"org": actor.organization_id, "id": order_id},
        )

    def insert_lines(self, actor, order_id, revision, order):
        for index, line in enumerate(order.lines, 1):
            structured = any(
                value is not None for value in (line.item_code, line.item_name, line.specification)
            )
            columns = ",item_code,item_name,specification" if structured else ""
            values = ",:item_code,:item_name,:specification" if structured else ""
            self.conn.execute(
                text(f"""INSERT INTO order_lines
              (id,organization_id,order_id,revision_id,line_number,description,quantity,
               source_quantity_text,source_unit,canonical_unit,quantity_policy,source_unit_price,source_amount{columns})
              VALUES (:id,:org,:order,:revision,:number,:description,
                      :quantity,:source,:unit,:canonical_unit,
                      CAST(:policy AS jsonb),:price,:amount{values})"""),
                {
                    "id": uuid7(),
                    "org": actor.organization_id,
                    "order": order_id,
                    "revision": revision["revision_id"],
                    "number": index,
                    "description": line.description,
                    "item_code": line.item_code,
                    "item_name": line.item_name,
                    "specification": line.specification,
                    "quantity": line.quantity.value,
                    "source": line.quantity.source_text,
                    "unit": line.quantity.source_unit,
                    "canonical_unit": line.quantity.policy.canonical_unit,
                    "policy": json.dumps(asdict(line.quantity.policy)),
                    "price": line.source_unit_price,
                    "amount": line.source_amount,
                },
            )

    def insert(self, actor, order_id, revision, order):
        self.conn.execute(
            text("""INSERT INTO orders
          (id,organization_id,customer_id,order_number,business_date,currency,current_revision_id,version,status)
          VALUES (:id,:org,:customer,:number,:date,:currency,:revision,1,'active')"""),
            {
                "id": order_id,
                "org": actor.organization_id,
                "customer": order.customer_id,
                "number": order.order_number,
                "date": order.business_date,
                "currency": order.currency,
                "revision": revision["revision_id"],
            },
        )
        self.insert_lines(actor, order_id, revision, order)

    def get(self, actor, order_id, lock=False):
        sql = "SELECT * FROM orders WHERE organization_id=:org AND id=:id"
        if lock:
            sql += " FOR UPDATE"
        row = (
            self.conn.execute(text(sql), {"org": actor.organization_id, "id": order_id})
            .mappings()
            .first()
        )
        if not row:
            raise BusinessError("ORDER_NOT_FOUND", 404)
        return {
            "id": str(row["id"]),
            "customer_id": str(row["customer_id"]),
            "order_number": row["order_number"],
            "business_date": row["business_date"].isoformat(),
            "currency": row["currency"],
            "revision_id": str(row["current_revision_id"]),
            "status": row["status"],
            "version": row["version"],
        }

    @staticmethod
    def line_view(row):
        return {
            "id": str(row["id"]),
            "line_number": row["line_number"],
            "description": row["description"],
            "item_code": row.get("item_code"),
            "item_name": row.get("item_name"),
            "specification": row.get("specification"),
            "quantity": decimal_text(row["quantity"]),
            "delivered_quantity": decimal_text(row["delivered_quantity"]),
            "remaining_quantity": decimal_text(row["quantity"] - row["delivered_quantity"]),
            "source_quantity_text": row["source_quantity_text"],
            "source_unit": row["source_unit"],
            "canonical_unit": row["canonical_unit"],
            "quantity_policy": row["quantity_policy"],
            "source_unit_price": row["source_unit_price"],
            "source_amount": row["source_amount"],
        }

    def lines(self, actor, revision_id):
        rows = self.conn.execute(
            text(
                "SELECT * FROM order_lines WHERE organization_id=:org "
                "AND revision_id=:revision ORDER BY line_number"
            ),
            {"org": actor.organization_id, "revision": revision_id},
        ).mappings()
        return [self.line_view(row) for row in rows]

    def material_lines(self, actor, revision_id):
        rows = self.conn.execute(
            text(
                "SELECT * FROM order_lines WHERE organization_id=:org "
                "AND revision_id=:revision ORDER BY line_number"
            ),
            {"org": actor.organization_id, "revision": revision_id},
        ).mappings()
        return [
            {
                **self.line_view(row),
                "material_id": str(row["material_id"]) if row.get("material_id") else None,
            }
            for row in rows
        ]

    def set_material_choices(self, actor, revision_id, selected):
        for choice in selected:
            self.conn.execute(
                text(
                    "UPDATE order_lines SET material_id=:material "
                    "WHERE organization_id=:org AND revision_id=:revision AND line_number=:number"
                ),
                {
                    "org": actor.organization_id,
                    "revision": revision_id,
                    "number": choice["line_number"],
                    "material": choice["material_id"],
                },
            )

    def set_material(self, actor, line_id, material_id):
        self.conn.execute(
            text(
                "UPDATE order_lines SET material_id=:material WHERE organization_id=:org AND id=:id"
            ),
            {"org": actor.organization_id, "id": line_id, "material": material_id},
        )

    def advance_version(self, actor, order_id):
        self.conn.execute(
            text("UPDATE orders SET version=version+1 WHERE organization_id=:org AND id=:id"),
            {"org": actor.organization_id, "id": order_id},
        )

    def replace_revision(self, actor, order_id, revision, order):
        self.conn.execute(
            text(
                "UPDATE orders SET current_revision_id=:revision, business_date=:date, "
                "version=version+1 WHERE organization_id=:org AND id=:id"
            ),
            {
                "revision": revision["revision_id"],
                "date": order.business_date,
                "org": actor.organization_id,
                "id": order_id,
            },
        )
        self.insert_lines(actor, order_id, revision, order)

    def set_status(self, actor, order_id, status):
        self.conn.execute(
            text(
                "UPDATE orders SET status=:status,version=version+1 "
                "WHERE organization_id=:org AND id=:id"
            ),
            {"status": status, "org": actor.organization_id, "id": order_id},
        )

    def event(self, actor, order_id, action, version, revision_id, reason):
        self.conn.execute(
            text("""INSERT INTO order_events
         (id,organization_id,order_id,action,version,revision_id,reason,actor_id)
         VALUES (:id,:org,:order,:action,:version,:revision,:reason,:actor)"""),
            {
                "id": uuid7(),
                "org": actor.organization_id,
                "order": order_id,
                "action": action,
                "version": version,
                "revision": revision_id,
                "reason": reason,
                "actor": actor.user_id,
            },
        )

    def has_delivery(self, actor, revision_id):
        return self.conn.execute(
            text(
                "SELECT EXISTS(SELECT 1 FROM order_lines "
                "WHERE organization_id=:org AND revision_id=:revision "
                "AND delivered_quantity>0)"
            ),
            {"org": actor.organization_id, "revision": revision_id},
        ).scalar_one()

    def open_lines(self, actor, customer_id, cursor, limit, status):
        params = {"org": actor.organization_id, "status": status, "limit": limit + 1}
        conditions = ""
        if customer_id:
            conditions += " AND o.customer_id=:customer"
            params["customer"] = customer_id
        if cursor:
            try:
                identifier, position = base64.urlsafe_b64decode(cursor.encode()).decode().split(":")
                params["cursor_id"], params["cursor_line"] = UUID(identifier), int(position)
                if params["cursor_line"] < 1:
                    raise ValueError
            except ValueError, UnicodeError:
                raise BusinessError("INVALID_CURSOR", field="cursor") from None
            conditions += (
                " AND (o.id<:cursor_id OR (o.id=:cursor_id AND l.line_number>:cursor_line))"
            )
        rows = list(
            self.conn.execute(
                text(
                    """SELECT l.*, o.order_number,o.business_date,o.version,
          o.customer_id,c.full_name AS customer_name FROM orders o
          JOIN order_lines l ON l.organization_id=o.organization_id
           AND l.revision_id=o.current_revision_id
          JOIN customers c ON c.organization_id=o.organization_id AND c.id=o.customer_id
          WHERE o.organization_id=:org AND o.status=:status AND l.quantity>l.delivered_quantity"""
                    + conditions
                    + " ORDER BY o.id DESC,l.line_number LIMIT :limit"
                ),
                params,
            ).mappings()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        next_cursor = None
        if more:
            last = rows[-1]
            next_cursor = base64.urlsafe_b64encode(
                f"{last['order_id']}:{last['line_number']}".encode()
            ).decode()
        return {
            "items": [
                {
                    **self.line_view(row),
                    "order_id": str(row["order_id"]),
                    "order_number": row["order_number"],
                    "business_date": row["business_date"].isoformat(),
                    "customer_id": str(row["customer_id"]),
                    "customer_name": row["customer_name"],
                    "version": row["version"],
                }
                for row in rows
            ],
            "next_cursor": next_cursor,
        }
