import json
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.adapters.lifecycle_repository import LifecycleRepository
from factoryflow.modules.statements.domain.draft import calculate, canonical
from sqlalchemy import text


class StatementRepository:
    def __init__(self, conn):
        self.conn = conn

    def settings(self, actor, customer_id):
        row = (
            self.conn.execute(
                text(
                    "SELECT version,cycle_day,tax_mode,tax_rate,template_id,"
                    "to_jsonb(s)->>'customer_template_id' AS customer_template_id FROM "
                    "statement_customer_settings s WHERE organization_id=:org "
                    "AND customer_id=:customer"
                ),
                {"org": actor.organization_id, "customer": customer_id},
            )
            .mappings()
            .first()
        )
        return (
            {
                **row,
                "tax_rate": canonical(row["tax_rate"]),
                "customer_template_id": str(row["customer_template_id"])
                if row["customer_template_id"]
                else None,
            }
            if row
            else None
        )

    def save_settings(self, actor, customer_id, body, version):
        self.conn.execute(
            text(
                "INSERT INTO statement_customer_settings(organization_id,customer_id,"
                "version,cycle_day,tax_mode,tax_rate,template_id,customer_template_id) "
                "VALUES(:org,:customer,:version,:day,:mode,:rate,:template,:custom) "
                "ON CONFLICT(organization_id,customer_id) DO UPDATE "
                "SET version=excluded.version,cycle_day=excluded.cycle_day,"
                "tax_mode=excluded.tax_mode,tax_rate=excluded.tax_rate,template_id=excluded.template_id,"
                "customer_template_id=excluded.customer_template_id"
            ),
            {
                "org": actor.organization_id,
                "customer": customer_id,
                "version": version,
                "day": body["cycle_day"],
                "template": body["template_id"],
                "custom": body.get("customer_template_id"),
                "mode": body["tax_mode"],
                "rate": Decimal(body["tax_rate"]),
            },
        )

    def get(self, actor, identifier, *, history=True):
        row = (
            self.conn.execute(
                text("SELECT * FROM statements WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("STATEMENT_NOT_FOUND", 404)
        fixed = None
        if row["status"] == "confirmed":
            fixed = self.conn.execute(
                text(
                    "SELECT snapshot FROM statement_events "
                    "WHERE organization_id=:org AND statement_id=:id AND version=:version"
                ),
                {"org": actor.organization_id, "id": identifier, "version": row["version"]},
            ).scalar()
        lines = self.conn.execute(
            text(
                "SELECT * FROM statement_lines WHERE organization_id=:org "
                "AND statement_id=:id ORDER BY delivery_id,order_line_id"
            ),
            {"org": actor.organization_id, "id": identifier},
        ).mappings()
        result = {
            "id": str(row["id"]),
            "currency": row.get("currency", "CNY"),
            "customer_id": str(row["customer_id"]),
            "customer_name": row["customer_name"],
            "status": row["status"],
            "version": row["version"],
            "period_start": row["period_start"].isoformat(),
            "period_end": row["period_end"].isoformat(),
            "tax_mode": row["tax_mode"],
            "tax_rate": canonical(row["tax_rate"]),
            "adjustments": row["adjustments"],
            "fees_confirmed": row.get("fees_confirmed", False),
            "reconfirmation": row.get("reconfirmation", "unknown"),
            "correction": None,
            "approval_refs": LifecycleRepository(self.conn).references(actor, identifier),
            "confirmation_evidence_ids": [],
            "settlement_lines": LifecycleRepository(self.conn).projection(actor, identifier),
            "lines": [
                {
                    "delivery_id": str(line["delivery_id"]),
                    "order_line_id": str(line["order_line_id"]),
                    "quantity": canonical(line["quantity"]),
                    "unit_price": canonical(line["unit_price"])
                    if line["unit_price"] is not None
                    else None,
                    "external_document_number": line.get("external_document_number", ""),
                    "reason": line["reason"],
                    "status": line["status"],
                    "source": line["source"],
                }
                for line in lines
            ],
        }
        result["calculation"] = calculate(
            result["lines"] + result["settlement_lines"],
            result["tax_mode"],
            result["tax_rate"],
            result["adjustments"],
        )
        if fixed is not None:
            result = {**fixed, "currency": fixed.get("currency", "CNY")}
        result["history"] = []
        if history:
            result["history"] = [
                dict(row)
                for row in self.conn.execute(
                    text(
                        "SELECT version,action,reason,snapshot FROM statement_events "
                        "WHERE organization_id=:org AND statement_id=:id ORDER BY version"
                    ),
                    {"org": actor.organization_id, "id": identifier},
                ).mappings()
            ]
        return result

    def create(self, actor, identifier, body, customer):
        currency_column = ",currency" if body.get("currency", "CNY") != "CNY" else ""
        currency_value = ",:currency" if currency_column else ""
        self.conn.execute(
            text(
                "INSERT INTO statements(organization_id,id,customer_id,customer_name,"
                "period_start,period_end,status,version,tax_mode,tax_rate,"
                f"adjustments{currency_column}) "
                "VALUES(:org,:id,:customer,:name,:start,:end,'draft',1,:mode,:rate,"
                f"CAST(:adjustments AS jsonb){currency_value})"
            ),
            self.parameters(actor, identifier, body) | {"name": customer["full_name"]},
        )

    @staticmethod
    def parameters(actor, identifier, body):
        return {
            "org": actor.organization_id,
            "id": identifier,
            "customer": body["customer_id"],
            "currency": body.get("currency", "CNY"),
            "start": body["period_start"],
            "end": body["period_end"],
            "mode": body["tax_mode"],
            "rate": Decimal(body["tax_rate"]),
            "adjustments": json.dumps(body["adjustments"]),
        }

    def update(self, actor, identifier, body, status="draft"):
        self.conn.execute(
            text(
                "UPDATE statements SET version=version+1,status=:status,"
                "tax_mode=:mode,tax_rate=:rate,adjustments=CAST(:adjustments AS jsonb) "
                "WHERE organization_id=:org AND id=:id"
            ),
            self.parameters(actor, identifier, body) | {"status": status},
        )

    def write_lines(self, actor, identifier, customer_id, lines):
        # Current projection changes; every command also records a complete immutable snapshot.
        self.conn.execute(
            text(
                "UPDATE statement_lines SET status='released' "
                "WHERE organization_id=:org AND statement_id=:id "
                "AND status IN ('included','deferred')"
            ),
            {"org": actor.organization_id, "id": identifier},
        )
        for line in lines:
            params = {
                "org": actor.organization_id,
                "id": identifier,
                "customer": customer_id,
                "delivery": line["delivery_id"],
                "line": line["order_line_id"],
                "quantity": Decimal(line["quantity"]),
                "price": Decimal(line["unit_price"]) if line["unit_price"] is not None else None,
                "status": line["status"],
                "external_document_number": line.get("external_document_number", ""),
                "reason": line["reason"],
                "source": json.dumps(line["source"]),
            }
            updated = self.conn.execute(
                text(
                    "UPDATE statement_lines SET quantity=:quantity,unit_price=:price,"
                    "status=:status,external_document_number=:external_document_number,"
                    "reason=:reason WHERE organization_id=:org AND statement_id=:id "
                    "AND delivery_id=:delivery AND order_line_id=:line"
                ),
                params,
            )
            if updated.rowcount:
                continue
            self.conn.execute(
                text(
                    "INSERT INTO statement_lines(organization_id,statement_id,"
                    "customer_id,delivery_id,order_line_id,quantity,unit_price,"
                    "status,reason,source,external_document_number) "
                    "VALUES(:org,:id,:customer,:delivery,:line,"
                    ":quantity,:price,:status,:reason,CAST(:source AS jsonb),"
                    ":external_document_number)"
                ),
                params,
            )

    def allocated(self, actor, keys, exclude=None):
        if not keys:
            return {}
        rows = self.conn.execute(
            text(
                "SELECT delivery_id,order_line_id,sum(quantity) AS quantity "
                "FROM statement_lines WHERE organization_id=:org "
                "AND delivery_id=ANY(:ids) AND status='included' "
                "AND statement_id<>:exclude GROUP BY delivery_id,order_line_id"
            ),
            {
                "org": actor.organization_id,
                "ids": [UUID(key[0]) for key in keys],
                "exclude": exclude or UUID(int=0),
            },
        ).mappings()
        result = {
            (str(row["delivery_id"]), str(row["order_line_id"])): row["quantity"] for row in rows
        }
        for key, quantity in LifecycleRepository(self.conn).extra_claims(actor, keys).items():
            result[key] = result.get(key, Decimal(0)) + quantity
        return result

    def event(self, actor, identifier, action, reason, *, correction=None):
        snapshot = self.get(actor, identifier, history=False)
        if action in {"settle", "correct_settlement"}:
            snapshot["confirmation_evidence_ids"] = [
                str(value)
                for value in self.conn.execute(
                    text(
                        "SELECT id FROM statement_evidence WHERE organization_id=:org "
                        "AND statement_id=:id ORDER BY created_at,id"
                    ),
                    {"org": actor.organization_id, "id": identifier},
                ).scalars()
            ]
        if correction is not None:
            snapshot["correction"] = correction
        self.conn.execute(
            text(
                "INSERT INTO statement_events(organization_id,id,statement_id,"
                "version,action,reason,actor_id,snapshot) "
                "VALUES(:org,:event,:id,:version,:action,:reason,:actor,CAST(:snapshot AS jsonb))"
            ),
            {
                "org": actor.organization_id,
                "event": uuid7(),
                "id": identifier,
                "version": snapshot["version"],
                "action": action,
                "reason": reason,
                "actor": actor.user_id,
                "snapshot": json.dumps(snapshot),
            },
        )

    def affected(self, actor, delivery_id):
        return (
            self.conn.execute(
                text(
                    "SELECT DISTINCT s.id FROM statements s JOIN statement_lines l "
                    "ON s.organization_id=l.organization_id AND s.id=l.statement_id "
                    "WHERE s.organization_id=:org AND l.delivery_id=:delivery "
                    "AND s.status='draft' AND l.status IN ('included','deferred') "
                    "ORDER BY s.id"
                ),
                {"org": actor.organization_id, "delivery": delivery_id},
            )
            .scalars()
            .all()
        )

    def protect_delivery(self, actor, delivery_id):
        LifecycleRepository(self.conn).protect_delivery(actor, delivery_id)

    def source_void(self, actor, identifier, delivery_id):
        remaining = [
            line
            for line in self.get(actor, identifier, history=False)["lines"]
            if line["delivery_id"] != str(delivery_id)
        ]
        LifecycleRepository(self.conn).reconcile_transfers(
            actor, identifier, remaining, "Source delivery void"
        )
        self.conn.execute(
            text(
                "UPDATE statement_lines SET status='source_void' "
                "WHERE organization_id=:org AND statement_id=:id AND delivery_id=:delivery "
                "AND status IN ('included','deferred')"
            ),
            {"org": actor.organization_id, "id": identifier, "delivery": delivery_id},
        )

    def list(self, actor, customer_id, cursor=None, limit=50):
        rows = (
            self.conn.execute(
                text(
                    "SELECT id FROM statements WHERE organization_id=:org "
                    "AND customer_id=:customer AND (CAST(:cursor AS uuid) IS NULL "
                    "OR id<CAST(:cursor AS uuid)) "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {
                    "org": actor.organization_id,
                    "customer": customer_id,
                    "cursor": cursor,
                    "limit": limit + 1,
                },
            )
            .scalars()
            .all()
        )
        more, rows = len(rows) > limit, rows[:limit]
        return {
            "items": [self.get(actor, identifier, history=False) for identifier in rows],
            "next_cursor": str(rows[-1]) if more else None,
        }

    def overlaps(self, actor, customer_id, start, end, currency="CNY"):
        return [
            str(identifier)
            for identifier in self.conn.execute(
                text(
                    "SELECT id FROM statements WHERE organization_id=:org "
                    "AND customer_id=:customer AND status='draft' "
                    "AND currency=:currency "
                    "AND period_start<=:end AND period_end>=:start ORDER BY id LIMIT 100"
                ),
                {
                    "org": actor.organization_id,
                    "customer": customer_id,
                    "start": start,
                    "end": end,
                    "currency": currency,
                },
            ).scalars()
        ]
