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
        return {
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
    ):
        row = (
            self.conn.execute(
                text("""INSERT INTO inventory_ledger
            (organization_id,id,material_id,kind,delta,business_date,reason,target_quantity,
             expected_version,delivery_id,order_line_id,reverses_id,shortage_confirmed,actor_id)
            VALUES(:org,:id,:material,:kind,:delta,:day,:reason,:target,:expected,
                   :delivery,:line,:reverses,:shortage,:actor) RETURNING *"""),
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
                },
            )
            .mappings()
            .one()
        )
        return self.entry_view(row)

    def entry(self, actor, identifier):
        row = (
            self.conn.execute(
                text("""SELECT e.*,r.id AS reversed_by FROM inventory_ledger e
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
                    """SELECT e.*,r.id AS reversed_by FROM inventory_ledger e
            LEFT JOIN inventory_ledger r
            ON r.organization_id=e.organization_id AND r.reverses_id=e.id
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

    def accounts(self, actor, cursor, limit):
        condition = ""
        params = {"org": actor.organization_id, "limit": limit + 1}
        if cursor:
            try:
                params["cursor"] = UUID(cursor)
            except TypeError, ValueError:
                raise BusinessError("INVALID_CURSOR") from None
            condition = " AND material_id>:cursor"
        rows = list(
            self.conn.execute(
                text(
                    "SELECT * FROM inventory_accounts WHERE organization_id=:org"
                    + condition
                    + " ORDER BY material_id LIMIT :limit"
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
