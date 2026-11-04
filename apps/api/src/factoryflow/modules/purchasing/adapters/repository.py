"""Purchasing-owned SQL; inventory effects use its public transaction facade."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.purchasing.domain.rules import total_amount
from sqlalchemy import text


class PurchasingRepository:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def view(row):
        return {
            k: str(v)
            if isinstance(v, (UUID, Decimal))
            else v.isoformat()
            if isinstance(v, (datetime, date))
            else v
            for k, v in row.items()
            if k not in {"organization_id", "created_tx"}
        }

    def supplier(self, actor, identifier):
        row = (
            self.conn.execute(
                text("SELECT * FROM suppliers WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("SUPPLIER_NOT_FOUND", 404)
        return self.view(row)

    def insert_supplier(self, actor, values):
        identifier = uuid7()
        self.conn.execute(
            text("""INSERT INTO suppliers
            (organization_id,id,full_name,contact,phone,address,note,created_by,updated_by)
            VALUES (:org,:id,:full_name,:contact,:phone,:address,:note,:user,:user)"""),
            {"org": actor.organization_id, "id": identifier, "user": actor.user_id, **values},
        )
        return self.supplier(actor, identifier)

    def update_supplier(self, actor, identifier, values):
        self.conn.execute(
            text("""UPDATE suppliers SET full_name=:full_name,contact=:contact,
            phone=:phone,address=:address,note=:note,active=:active,version=version+1,
            updated_by=:user,updated_at=clock_timestamp() WHERE organization_id=:org AND id=:id"""),
            {"org": actor.organization_id, "id": identifier, "user": actor.user_id, **values},
        )
        return self.supplier(actor, identifier)

    def list(self, actor, table, q, offset, limit):
        if table not in {"suppliers", "purchase_orders", "purchase_receipts"}:
            raise ValueError(table)
        if offset < 0 or not 1 <= limit <= 100:
            raise BusinessError("INVALID_INPUT", field="limit")
        name = "full_name" if table == "suppliers" else "number || ' ' || supplier_name"
        where = f"organization_id=:org AND strpos(lower({name}),lower(:q))>0"
        params = {"org": actor.organization_id, "q": q.strip(), "offset": offset, "limit": limit}
        total = self.conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE {where}"), params
        ).scalar_one()
        rows = self.conn.execute(
            text(
                f"SELECT * FROM {table} WHERE {where} "
                "ORDER BY created_at DESC,id DESC OFFSET :offset LIMIT :limit"
            ),
            params,
        ).mappings()
        return {
            "items": [self.view(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    def document(self, actor, table, identifier):
        is_order = table == "purchase_orders"
        if table not in {"purchase_orders", "purchase_receipts"}:
            raise ValueError(table)
        row = (
            self.conn.execute(
                text(f"SELECT * FROM {table} WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError(
                "PURCHASE_ORDER_NOT_FOUND" if is_order else "PURCHASE_RECEIPT_NOT_FOUND", 404
            )
        result = self.view(row)
        if is_order:
            query = """SELECT l.*, COALESCE((SELECT sum(rl.quantity) FROM purchase_receipt_lines rl
                JOIN purchase_receipts r ON r.organization_id=rl.organization_id
                AND r.id=rl.receipt_id
                WHERE rl.organization_id=l.organization_id AND rl.purchase_line_id=l.id
                AND r.status='active'),0)
                AS received_quantity FROM purchase_order_lines l WHERE organization_id=:org
                AND order_id=:id ORDER BY line_number"""
        else:
            query = (
                "SELECT * FROM purchase_receipt_lines WHERE organization_id=:org "
                "AND receipt_id=:id ORDER BY line_number"
            )
        result["lines"] = [
            self.view(r)
            for r in self.conn.execute(
                text(query), {"org": actor.organization_id, "id": identifier}
            ).mappings()
        ]
        if is_order:
            for line in result["lines"]:
                line["remaining_quantity"] = str(
                    Decimal(line["ordered_quantity"]) - Decimal(line["received_quantity"])
                )
            result["total_amount"] = total_amount(result["lines"])
        return result

    def by_source(self, actor, source_id):
        identifier = self.conn.execute(
            text("SELECT id FROM purchase_orders WHERE organization_id=:org AND source_id=:source"),
            {"org": actor.organization_id, "source": source_id},
        ).scalar()
        if identifier is None:
            raise BusinessError("PURCHASE_ORDER_NOT_FOUND", 404)
        return self.document(actor, "purchase_orders", identifier)

    def insert_document(self, actor, table, header, lines):
        is_order = table == "purchase_orders"
        identifier = uuid7()
        number = header["number"] or ("CG" if is_order else "SL") + identifier.hex.upper()
        values = {
            "org": actor.organization_id,
            "id": identifier,
            "user": actor.user_id,
            **header,
            "number": number,
        }
        extra = ",currency,buyer_name,source_id,extraction_id" if is_order else ",purchase_order_id"
        extra_value = (
            ",:currency,:buyer_name,:source_id,:extraction_id"
            if is_order
            else ",:purchase_order_id"
        )
        self.conn.execute(
            text(f"""INSERT INTO {table}
            (organization_id,id,supplier_id,number,business_date,supplier_name,note,created_by{extra})
            VALUES (:org,:id,:supplier_id,:number,:business_date,
            :supplier_name,:note,:user{extra_value})"""),
            values,
        )
        line_table = "purchase_order_lines" if is_order else "purchase_receipt_lines"
        parent = "order_id" if is_order else "receipt_id"
        amount = "ordered_quantity" if is_order else "quantity"
        for index, line in enumerate(lines, 1):
            extra = ",source_unit_price,source_amount" if is_order else ",purchase_line_id"
            extra_value = ",:source_unit_price,:source_amount" if is_order else ",:purchase_line_id"
            self.conn.execute(
                text(f"""INSERT INTO {line_table}
                (organization_id,id,{parent},line_number,material_id,own_code,material_name,
                specification,canonical_unit,{amount}{extra})
                VALUES (:org,:id,:parent,:line_number,:material_id,:own_code,:material_name,
                :specification,:canonical_unit,:quantity{extra_value})"""),
                {"org": actor.organization_id, "parent": identifier, "line_number": index, **line},
            )
        return self.document(actor, table, identifier)

    def transition(self, actor, table, identifier, reason):
        prefix, status = ("close", "closed") if table == "purchase_orders" else ("void", "void")
        by = "closed" if prefix == "close" else "void"
        self.conn.execute(
            text(f"""UPDATE {table} SET status=:status,version=version+1,
            {prefix}_reason=:reason,{by}_by=:user,{by}_at=clock_timestamp()
            WHERE organization_id=:org AND id=:id"""),
            {
                "org": actor.organization_id,
                "id": identifier,
                "status": status,
                "reason": reason,
                "user": actor.user_id,
            },
        )
        return self.document(actor, table, identifier)
