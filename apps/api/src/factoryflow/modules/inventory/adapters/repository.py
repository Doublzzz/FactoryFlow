"""Inventory persistence only; catalog and delivery facts enter through public contracts."""

from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.domain.stock import number
from sqlalchemy import text


class InventoryRepository:
    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def account_view(row):
        if row is None:
            return None
        return {
            "material_id": str(row["material_id"]),
            "canonical_unit": row["canonical_unit"],
            "balance": number(row["balance"]),
            "version": row["version"],
            "has_skipped": row["has_skipped"],
            "negative_balance": row["balance"] < 0,
            "needs_review": row["has_skipped"] or row["balance"] < 0,
        }

    def account(self, actor, material_id, *, lock=False):
        row = (
            self.conn.execute(
                text(
                    "SELECT * FROM inventory_accounts WHERE organization_id=:org "
                    "AND material_id=:material" + (" FOR UPDATE" if lock else "")
                ),
                {"org": actor.organization_id, "material": material_id},
            )
            .mappings()
            .first()
        )
        return self.account_view(row)

    def open_account(self, actor, material_id, unit):
        self.conn.execute(
            text("""INSERT INTO inventory_accounts
            (organization_id,material_id,canonical_unit,created_by)
            VALUES(:org,:material,:unit,:actor)
        """),
            {
                "org": actor.organization_id,
                "material": material_id,
                "unit": unit,
                "actor": actor.user_id,
            },
        )

    @staticmethod
    def entry_view(row):
        result = {
            "id": str(row["id"]),
            "material_id": str(row["material_id"]),
            "kind": row["kind"],
            "delta": number(row["delta"]),
            "balance_after": number(row["balance_after"]),
            "account_version": row["account_version"],
            "business_date": row["business_date"].isoformat(),
            "recorded_at": row["recorded_at"].isoformat(),
            "reason": row["reason"],
            "delivery_id": str(row["delivery_id"]) if row["delivery_id"] else None,
            "order_line_id": str(row["order_line_id"]) if row["order_line_id"] else None,
            "reverses_id": str(row["reverses_id"]) if row["reverses_id"] else None,
            "reversed_by": str(row["reversed_by"]) if row.get("reversed_by") else None,
            "shortage_confirmed": row["shortage_confirmed"],
            "target_quantity": number(row["target_quantity"])
            if row["target_quantity"] is not None
            else None,
        }
        if row["kind"] in {
            "purchase_receipt",
            "purchase_receipt_void",
            "material_issue",
            "material_return",
        }:
            result["purchase_receipt_line_id"] = (
                str(row["purchase_receipt_line_id"]) if row["purchase_receipt_line_id"] else None
            )
            result["returns_issue_id"] = (
                str(row["returns_issue_id"]) if row["returns_issue_id"] else None
            )
            result["returns_issue_version"] = row.get("returns_issue_version")
            result["purchase_receipt_id"] = (
                str(row["purchase_receipt_id"]) if row.get("purchase_receipt_id") else None
            )
            result["purchase_receipt_number"] = row.get("purchase_receipt_number")
            if row["kind"] == "material_issue":
                result["returned_quantity"] = number(row.get("returned_quantity") or Decimal(0))
        result["production_order_id"] = (
            str(row["production_order_id"]) if row.get("production_order_id") else None
        )
        result["production_completion_id"] = (
            str(row["production_completion_id"]) if row.get("production_completion_id") else None
        )
        return result

    def append(
        self,
        actor,
        material_id,
        kind,
        delta,
        business_date,
        *,
        reason=None,
        target=None,
        expected=None,
        delivery_id=None,
        order_line_id=None,
        reverses_id=None,
        shortage_confirmed=False,
        purchase_receipt_line_id=None,
        returns_issue_id=None,
        production_order_id=None,
        production_completion_id=None,
    ):
        row = (
            self.conn.execute(
                text("""INSERT INTO inventory_ledger
            (organization_id,id,material_id,kind,delta,business_date,reason,target_quantity,
             expected_version,delivery_id,order_line_id,reverses_id,shortage_confirmed,actor_id,
             purchase_receipt_line_id,returns_issue_id,production_order_id,production_completion_id)
            VALUES(:org,:id,:material,:kind,:delta,:day,:reason,:target,:expected,
                   :delivery,:line,:reverses,:shortage,:actor,:purchase_line,:issue,:production,:completion)
            RETURNING *"""),
                {
                    "org": actor.organization_id,
                    "id": uuid7(),
                    "material": material_id,
                    "kind": kind,
                    "delta": Decimal(delta),
                    "day": business_date,
                    "reason": reason,
                    "target": Decimal(target) if target is not None else None,
                    "expected": expected,
                    "delivery": delivery_id,
                    "line": order_line_id,
                    "reverses": reverses_id,
                    "shortage": shortage_confirmed,
                    "actor": actor.user_id,
                    "purchase_line": purchase_receipt_line_id,
                    "issue": returns_issue_id,
                    "production": production_order_id,
                    "completion": production_completion_id,
                },
            )
            .mappings()
            .one()
        )
        return self.entry_view(row)

    def entry(self, actor, identifier):
        row = (
            self.conn.execute(
                text("""SELECT e.*,r.id AS reversed_by,
            (SELECT COALESCE(sum(t.delta),0) FROM inventory_ledger t
             WHERE t.organization_id=e.organization_id AND t.returns_issue_id=e.id)
             AS returned_quantity
            FROM inventory_ledger e
            LEFT JOIN inventory_ledger r
            ON r.organization_id=e.organization_id AND r.reverses_id=e.id
            WHERE e.organization_id=:org AND e.id=:id"""),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("INVENTORY_ENTRY_NOT_FOUND", 404)
        return self.entry_view(row)

    def entries(self, actor, material_id, cursor, limit):
        condition = ""
        params = {"org": actor.organization_id, "material": material_id, "limit": limit + 1}
        if cursor is not None:
            try:
                params["cursor"] = int(cursor)
                if params["cursor"] < 1:
                    raise ValueError
            except TypeError, ValueError:
                raise BusinessError("INVALID_CURSOR") from None
            condition = " AND e.account_version<:cursor"
        rows = list(
            self.conn.execute(
                text(
                    """SELECT e.*,r.id AS reversed_by,
            p.receipt_id AS purchase_receipt_id, h.number AS purchase_receipt_number,
            issued.account_version AS returns_issue_version,
            (SELECT COALESCE(sum(t.delta),0) FROM inventory_ledger t
             WHERE t.organization_id=e.organization_id AND t.returns_issue_id=e.id)
             AS returned_quantity
            FROM inventory_ledger e
            LEFT JOIN inventory_ledger r
            ON r.organization_id=e.organization_id AND r.reverses_id=e.id
            LEFT JOIN purchase_receipt_lines p
            ON p.organization_id=e.organization_id AND p.id=e.purchase_receipt_line_id
            LEFT JOIN purchase_receipts h
            ON h.organization_id=p.organization_id AND h.id=p.receipt_id
            LEFT JOIN inventory_ledger issued
            ON issued.organization_id=e.organization_id AND issued.id=e.returns_issue_id
            WHERE e.organization_id=:org AND e.material_id=:material"""
                    + condition
                    + " ORDER BY e.account_version DESC LIMIT :limit"
                ),
                params,
            ).mappings()
        )
        more, rows = len(rows) > limit, rows[:limit]
        return {
            "entries": [self.entry_view(row) for row in rows],
            "next_cursor": str(rows[-1]["account_version"]) if more else None,
        }

    def accounts(self, actor, cursor, limit, kind="finished"):
        condition = ""
        params = {"org": actor.organization_id, "limit": limit + 1, "kind": kind}
        if cursor:
            try:
                params["cursor"] = UUID(cursor)
            except TypeError, ValueError:
                raise BusinessError("INVALID_CURSOR") from None
            condition = " AND a.material_id>:cursor"
        rows = list(
            self.conn.execute(
                text(
                    "SELECT a.* FROM inventory_accounts a JOIN materials m "
                    "ON m.organization_id=a.organization_id AND m.id=a.material_id "
                    "WHERE a.organization_id=:org AND m.kind=:kind"
                    + condition
                    + " ORDER BY a.material_id LIMIT :limit"
                ),
                params,
            ).mappings()
        )
        more, rows = len(rows) > limit, rows[:limit]
        return {
            "items": [self.account_view(row) for row in rows],
            "next_cursor": str(rows[-1]["material_id"]) if more else None,
        }

    def delivery_entries(self, actor, delivery_id):
        return [
            self.entry_view(row)
            for row in self.conn.execute(
                text(
                    "SELECT * FROM inventory_ledger WHERE organization_id=:org AND delivery_id=:id "
                    "AND kind='delivery' ORDER BY material_id,account_version"
                ),
                {"org": actor.organization_id, "id": delivery_id},
            ).mappings()
        ]

    def purchase_entries(self, actor, line_ids):
        return [
            self.entry_view(row)
            for row in self.conn.execute(
                text(
                    "SELECT * FROM inventory_ledger WHERE organization_id=:org "
                    "AND purchase_receipt_line_id=ANY(CAST(:ids AS uuid[])) "
                    "AND kind='purchase_receipt' ORDER BY material_id,account_version"
                ),
                {"org": actor.organization_id, "ids": list(map(str, line_ids))},
            ).mappings()
        ]

    def production_receipt(self, actor, completion_id):
        row = (
            self.conn.execute(
                text("""SELECT * FROM inventory_ledger
            WHERE organization_id=:org AND production_completion_id=:id
            AND kind='production_receipt'"""),
                {"org": actor.organization_id, "id": completion_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("PRODUCTION_INVENTORY_MISMATCH", 409)
        return self.entry_view(row)

    def production_issues(self, actor, production_id, offset, limit):
        params = {
            "org": actor.organization_id,
            "production": production_id,
            "offset": offset,
            "limit": limit,
        }
        count = self.conn.execute(
            text("""SELECT count(*) FROM inventory_ledger
            WHERE organization_id=:org AND production_order_id=:production
            AND kind='material_issue'"""),
            params,
        ).scalar_one()
        rows = self.conn.execute(
            text("""SELECT e.*,m.own_code,m.name,m.specification,a.canonical_unit,
            (SELECT COALESCE(sum(r.delta),0) FROM inventory_ledger r
             WHERE r.organization_id=e.organization_id AND r.returns_issue_id=e.id) AS returned
            FROM inventory_ledger e JOIN materials m
            ON m.organization_id=e.organization_id AND m.id=e.material_id
            JOIN inventory_accounts a ON a.organization_id=e.organization_id
            AND a.material_id=e.material_id
            WHERE e.organization_id=:org AND e.production_order_id=:production
            AND e.kind='material_issue'
            ORDER BY e.id DESC OFFSET :offset LIMIT :limit"""),
            params,
        ).mappings()
        return {
            "items": [
                {
                    "entry_id": str(r["id"]),
                    "production_order_id": str(production_id),
                    "material_id": str(r["material_id"]),
                    "own_code": r["own_code"],
                    "material_name": r["name"],
                    "specification": r["specification"],
                    "canonical_unit": r["canonical_unit"],
                    "quantity": number(-r["delta"]),
                    "returned_quantity": number(r["returned"]),
                    "outstanding_quantity": number(-r["delta"] - r["returned"]),
                    "business_date": r["business_date"].isoformat(),
                    "reason": r["reason"],
                }
                for r in rows
            ],
            "total": count,
            "offset": offset,
            "limit": limit,
        }
