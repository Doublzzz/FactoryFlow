"""Production owns its plan and completion evidence; balances remain inventory-owned."""

from decimal import Decimal
from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.production.domain.production import number
from sqlalchemy import text


class ProductionRepository:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def view(row):
        result = dict(row)
        for key in ("organization_id", "created_tx"):
            result.pop(key, None)
        for key, value in result.items():
            if isinstance(value, Decimal):
                result[key] = number(value)
            elif value is not None and (key.endswith("_id") or key.endswith("_by") or key == "id"):
                result[key] = str(value)
            elif value is not None and (key.endswith("_at") or key == "business_date"):
                result[key] = value.isoformat()
        return result

    def get(self, actor, identifier, *, lock=False):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM production_orders WHERE organization_id=:org AND id=:id"
                    + (" FOR UPDATE" if lock else "")
                ),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("PRODUCTION_NOT_FOUND", 404)
        result = self.view(row)
        totals = (
            self.conn.execute(
                text("""SELECT
            COALESCE(sum(quantity) FILTER(WHERE status='active'),0) AS completed,
            COALESCE(sum(scrap_quantity) FILTER(WHERE status='active'),0) AS scrap
            FROM production_completions WHERE organization_id=:org AND production_order_id=:id
        """),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .one()
        )
        result.update(
            completed_quantity=number(totals["completed"]),
            scrap_quantity=number(totals["scrap"]),
            remaining_quantity=number(row["planned_quantity"] - totals["completed"]),
        )
        return result

    def insert(self, actor, request, order, line, material):
        identifier = uuid7()
        self.conn.execute(
            text("""INSERT INTO production_orders
            (organization_id,id,number,order_id,source_revision_id,order_line_id,order_number,
             source_quantity,material_id,own_code,material_name,specification,canonical_unit,
             planned_quantity,business_date,note,created_by)
            VALUES(:org,:id,:number,:order,:revision,:line,:order_number,:source_quantity,
             :material,:code,:name,:specification,:unit,:quantity,:day,:note,:actor)
        """),
            {
                "org": actor.organization_id,
                "id": identifier,
                "number": (
                    f"PD-{request['business_date'].replace('-', '')}-{identifier.hex[-12:].upper()}"
                ),
                "order": order["id"],
                "revision": order["revision_id"],
                "line": line["id"],
                "order_number": order["order_number"],
                "source_quantity": Decimal(line["quantity"]),
                "material": material["id"],
                "code": material["own_code"],
                "name": material["name"],
                "specification": material["specification"],
                "unit": line["canonical_unit"],
                "quantity": Decimal(request["planned_quantity"]),
                "day": request["business_date"],
                "note": request["note"],
                "actor": actor.user_id,
            },
        )
        return self.get(actor, identifier)

    def list(self, actor, query, order_id, offset, limit):
        params = {"org": actor.organization_id, "q": f"%{query}%", "offset": offset, "limit": limit}
        condition = (
            "organization_id=:org AND (number ILIKE :q OR order_number ILIKE :q "
            "OR material_name ILIKE :q)"
        )
        if order_id:
            condition += " AND order_id=:order"
            params["order"] = order_id
        count = self.conn.execute(
            text("SELECT count(*) FROM production_orders WHERE " + condition), params
        ).scalar_one()
        ids = self.conn.execute(
            text(
                "SELECT id FROM production_orders WHERE "
                + condition
                + " ORDER BY id DESC OFFSET :offset LIMIT :limit"
            ),
            params,
        ).scalars()
        return {
            "items": [self.get(actor, identifier) for identifier in ids],
            "total": count,
            "offset": offset,
            "limit": limit,
        }

    def close(self, actor, production, reason):
        self.conn.execute(
            text("""UPDATE production_orders SET status='closed',version=version+1,
            closed_by=:actor,closed_at=clock_timestamp(),close_reason=:reason
            WHERE organization_id=:org AND id=:id"""),
            {
                "org": actor.organization_id,
                "id": production["id"],
                "actor": actor.user_id,
                "reason": reason,
            },
        )
        return self.get(actor, production["id"])

    def completion(self, actor, production_id, identifier):
        row = (
            self.conn.execute(
                text("""SELECT * FROM production_completions
            WHERE organization_id=:org AND production_order_id=:production AND id=:id"""),
                {"org": actor.organization_id, "production": production_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("PRODUCTION_COMPLETION_NOT_FOUND", 404)
        return self.view(row)

    def complete(self, actor, production, request):
        identifier = uuid7()
        self.conn.execute(
            text("""INSERT INTO production_completions
            (organization_id,id,production_order_id,material_id,quantity,scrap_quantity,
             business_date,note,created_by) VALUES(:org,:id,:production,:material,:quantity,
             :scrap,:day,:note,:actor)"""),
            {
                "org": actor.organization_id,
                "id": identifier,
                "production": production["id"],
                "material": production["material_id"],
                "quantity": Decimal(request["quantity"]),
                "scrap": Decimal(request["scrap_quantity"]),
                "day": request["business_date"],
                "note": request["note"],
                "actor": actor.user_id,
            },
        )
        return self.completion(actor, production["id"], identifier)

    def void(self, actor, completion, reason):
        self.conn.execute(
            text("""UPDATE production_completions SET status='void',version=version+1,
            void_by=:actor,void_at=clock_timestamp(),void_reason=:reason
            WHERE organization_id=:org AND id=:id"""),
            {
                "org": actor.organization_id,
                "id": completion["id"],
                "actor": actor.user_id,
                "reason": reason,
            },
        )
        return self.completion(actor, completion["production_order_id"], completion["id"])

    def completions(self, actor, production_id, offset, limit):
        params = {
            "org": actor.organization_id,
            "production": production_id,
            "offset": offset,
            "limit": limit,
        }
        count = self.conn.execute(
            text(
                "SELECT count(*) FROM production_completions WHERE organization_id=:org "
                "AND production_order_id=:production"
            ),
            params,
        ).scalar_one()
        rows = self.conn.execute(
            text("""SELECT * FROM production_completions
            WHERE organization_id=:org AND production_order_id=:production
            ORDER BY id DESC OFFSET :offset LIMIT :limit"""),
            params,
        ).mappings()
        return {
            "items": [self.view(row) for row in rows],
            "total": count,
            "offset": offset,
            "limit": limit,
        }
