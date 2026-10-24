"""Statement-owned lifecycle persistence; all writes use the caller's transaction."""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.domain.draft import canonical
from sqlalchemy import text


def serial(row):
    return {
        k: canonical(v)
        if isinstance(v, Decimal)
        else str(v)
        if isinstance(v, UUID)
        else v.isoformat()
        if isinstance(v, (date, datetime))
        else v
        for k, v in row.items()
        if k != "organization_id"
    }


class LifecycleRepository:
    TABLES = {"evidence", "approvals", "allocations", "reviews", "review_transfers"}

    def __init__(self, conn):
        self.conn = conn

    def available(self):
        return (
            self.conn.execute(text("SELECT to_regclass('statement_approvals')")).scalar_one()
            is not None
        )

    def get(self, actor, kind, identifier):
        assert kind in self.TABLES
        row = (
            self.conn.execute(
                text(f"SELECT * FROM statement_{kind} WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise BusinessError("STATEMENT_LIFECYCLE_NOT_FOUND", 404)
        result = serial(row)
        if kind == "approvals":
            amounts = self.conn.execute(
                text(
                    "SELECT status,COALESCE(sum(quantity),0) AS q "
                    "FROM statement_allocations WHERE organization_id=:org AND approval_id=:id "
                    "AND status IN ('reserved','settled') GROUP BY status"
                ),
                {"org": actor.organization_id, "id": identifier},
            ).all()
            used = dict(amounts)
            result.update(
                reserved_quantity=canonical(used.get("reserved", Decimal(0))),
                settled_quantity=canonical(used.get("settled", Decimal(0))),
                available_quantity=canonical(row["quantity"] - sum(used.values(), Decimal(0))),
            )
        if kind == "reviews":
            used = self.conn.execute(
                text(
                    "SELECT COALESCE(sum(quantity),0) "
                    "FROM statement_review_transfers WHERE organization_id=:org AND review_id=:id "
                    "AND status IN ('claimed','approved')"
                ),
                {"org": actor.organization_id, "id": identifier},
            ).scalar_one()
            result["remaining_quantity"] = canonical(row["quantity"] - used)
        return result

    def rows(self, actor, kind, *, statement=None, customer=None, approval=None, review=None):
        assert kind in self.TABLES
        clauses, params = ["organization_id=:org"], {"org": actor.organization_id}
        for column, value in (
            ("statement_id", statement),
            ("customer_id", customer),
            ("approval_id", approval),
            ("review_id", review),
        ):
            if value is not None:
                clauses.append(f"{column}=:{column}")
                params[column] = value
        ids = self.conn.execute(
            text(
                f"SELECT id FROM statement_{kind} WHERE "
                + " AND ".join(clauses)
                + " ORDER BY created_at,id"
            ),
            params,
        ).scalars()
        return [self.get(actor, kind, identifier) for identifier in ids]

    def page(self, actor, kind, customer, cursor=None, limit=50):
        assert kind in {"approvals", "reviews"}
        ids = list(
            self.conn.execute(
                text(
                    f"SELECT id FROM statement_{kind} WHERE "
                    "organization_id=:org AND customer_id=:customer "
                    "AND (CAST(:cursor AS uuid) IS NULL OR id<CAST(:cursor AS uuid)) "
                    "ORDER BY id DESC LIMIT :limit"
                ),
                {
                    "org": actor.organization_id,
                    "customer": customer,
                    "cursor": cursor,
                    "limit": limit + 1,
                },
            ).scalars()
        )
        return {
            "items": [self.get(actor, kind, i) for i in ids[:limit]],
            "next_cursor": str(ids[limit - 1]) if len(ids) > limit else None,
        }

    def add(self, actor, kind, body):
        assert kind in self.TABLES
        row = {
            **body,
            "organization_id": actor.organization_id,
            "actor_id": actor.user_id,
            "id": uuid7(),
        }
        columns = list(row)
        values = [f"CAST(:{c} AS jsonb)" if c == "source" else f":{c}" for c in columns]
        params = {c: json.dumps(v) if c == "source" else v for c, v in row.items()}
        self.conn.execute(
            text(
                f"INSERT INTO statement_{kind} ("
                + ",".join(columns)
                + ") VALUES ("
                + ",".join(values)
                + ")"
            ),
            params,
        )
        return self.get(actor, kind, row["id"])

    def change(self, actor, kind, identifier, changes):
        assert kind in {"approvals", "allocations", "review_transfers"}
        self.conn.execute(
            text(
                f"UPDATE statement_{kind} SET version=version+1,actor_id=:actor,"
                + ",".join(
                    f"{field}=CAST(:{field} AS jsonb)"
                    if field == "correction"
                    else f"{field}=:{field}"
                    for field in changes
                )
                + " WHERE organization_id=:org AND id=:id"
            ),
            {k: json.dumps(v) if k == "correction" else v for k, v in changes.items()}
            | {"org": actor.organization_id, "id": identifier, "actor": actor.user_id},
        )
        return self.get(actor, kind, identifier)

    def history(self, actor, identifier):
        return [
            serial(r) | {"snapshot": json.loads(r["snapshot"])}
            for r in self.conn.execute(
                text(
                    "SELECT kind,entity_id,version,(snapshot || "
                    "jsonb_build_object('quantity',snapshot->>'quantity') || "
                    "CASE WHEN snapshot ? 'unit_price' THEN "
                    "jsonb_build_object('unit_price',snapshot->>'unit_price') "
                    "ELSE '{}'::jsonb END || "
                    "CASE WHEN snapshot ? 'review_quantity' THEN "
                    "jsonb_build_object('review_quantity',snapshot->>'review_quantity') "
                    "ELSE '{}'::jsonb END)::text AS snapshot,created_at "
                    "FROM statement_lifecycle_events "
                    "WHERE organization_id=:org AND snapshot->>'statement_id'=:id "
                    "ORDER BY created_at,id"
                ),
                {"org": actor.organization_id, "id": str(identifier)},
            ).mappings()
        ]

    def lock_statement(self, actor, identifier):
        self.conn.execute(
            text("SELECT id FROM statements WHERE organization_id=:org AND id=:id FOR UPDATE"),
            {"org": actor.organization_id, "id": identifier},
        )

    def projection(self, actor, identifier):
        if not self.available():
            return []
        rows = self.conn.execute(
            text(
                "SELECT x.*,a.delivery_id,a.order_line_id,a.source,a.external_document_number,"
                "a.version AS approval_version FROM statement_allocations x "
                "JOIN statement_approvals a ON a.organization_id=x.organization_id "
                "AND a.id=x.approval_id WHERE x.organization_id=:org AND x.statement_id=:id "
                "AND x.status IN ('reserved','settled') "
                "ORDER BY x.id"
            ),
            {"org": actor.organization_id, "id": identifier},
        ).mappings()
        return [
            {
                "delivery_id": str(r["delivery_id"]),
                "order_line_id": str(r["order_line_id"]),
                "quantity": canonical(r["quantity"]),
                "unit_price": canonical(r["unit_price"]),
                "external_document_number": r.get("external_document_number", ""),
                "reason": r["reason"],
                "status": "included",
                "source": r["source"],
                "allocation_id": str(r["id"]),
                "approval_id": str(r["approval_id"]),
                "allocation_status": r["status"],
                "approval_version": r["approval_version"],
            }
            for r in rows
        ]

    def extra_claims(self, actor, keys):
        if not keys or not self.available():
            return {}
        rows = self.conn.execute(
            text(
                "SELECT delivery_id,order_line_id,sum(q) AS quantity FROM ("
                "SELECT delivery_id,order_line_id,quantity AS q FROM statement_approvals "
                "WHERE organization_id=:org AND delivery_id=ANY(:ids) UNION ALL "
                "SELECT r.delivery_id,r.order_line_id,r.quantity-"
                "(SELECT COALESCE(sum(t.quantity),0) "
                "FROM statement_review_transfers t WHERE t.organization_id=:org "
                "AND t.review_id=r.id "
                "AND t.status IN ('claimed','approved')) AS q FROM statement_reviews r "
                "WHERE r.organization_id=:org AND r.delivery_id=ANY(:ids)) q "
                "GROUP BY delivery_id,order_line_id"
            ),
            {"org": actor.organization_id, "ids": [UUID(key[0]) for key in keys]},
        ).mappings()
        return {(str(r["delivery_id"]), str(r["order_line_id"])): r["quantity"] for r in rows}

    def references(self, actor, statement):
        if not self.available():
            return []
        return [
            serial(r)
            for r in self.conn.execute(
                text(
                    "SELECT a.id AS approval_id,a.version,a.sent_id,a.feedback_id "
                    "FROM statement_approvals a "
                    "WHERE a.organization_id=:org AND (a.statement_id=:id OR EXISTS("
                    "SELECT 1 FROM statement_allocations x "
                    "WHERE x.organization_id=a.organization_id "
                    "AND x.approval_id=a.id AND x.statement_id=:id "
                    "AND x.status IN ('reserved','settled'))) "
                    "ORDER BY a.id"
                ),
                {"org": actor.organization_id, "id": statement},
            ).mappings()
        ]

    def review_claimed(self, actor, statement, source):
        return self.conn.execute(
            text(
                "SELECT COALESCE(sum(t.quantity),0) FROM statement_review_transfers t "
                "JOIN statement_reviews r ON r.organization_id=t.organization_id "
                "AND r.id=t.review_id "
                "WHERE t.organization_id=:org AND t.statement_id=:statement AND t.status='claimed' "
                "AND r.delivery_id=:delivery AND r.order_line_id=:line"
            ),
            {
                "org": actor.organization_id,
                "statement": statement,
                "delivery": source["delivery_id"],
                "line": source["order_line_id"],
            },
        ).scalar_one()

    def reconcile_transfers(self, actor, statement, lines, why):
        """Release only the excess claimed review quantity when a draft shrinks."""
        from factoryflow.modules.statements.domain.draft import source_key

        remaining = {
            source_key(x): Decimal(x["quantity"]) for x in lines if x["status"] == "included"
        }
        for item in self.rows(actor, "review_transfers", statement=statement):
            if item["status"] != "claimed":
                continue
            review = self.get(actor, "reviews", item["review_id"])
            key = source_key(review)
            matching = next(
                (x for x in lines if source_key(x) == key and x["status"] == "included"), None
            )
            if matching is not None and matching.get("external_document_number", "") != review.get(
                "external_document_number", ""
            ):
                raise BusinessError("STATEMENT_EXTERNAL_NUMBER_MISMATCH", 409)
            retained = min(remaining.get(key, Decimal(0)), Decimal(item["quantity"]))
            remaining[key] = remaining.get(key, Decimal(0)) - retained
            if retained < Decimal(item["quantity"]):
                self.change(
                    actor, "review_transfers", item["id"], {"status": "released", "reason": why}
                )
                if retained:
                    self.add(
                        actor,
                        "review_transfers",
                        {
                            "customer_id": item["customer_id"],
                            "review_id": item["review_id"],
                            "statement_id": statement,
                            "quantity": retained,
                            "status": "claimed",
                            "reason": why,
                        },
                    )

    def approve_transfers(self, actor, statement, source, amount, why, approval_id):
        for item in self.rows(actor, "review_transfers", statement=statement):
            review = self.get(actor, "reviews", item["review_id"])
            if (
                item["status"] != "claimed"
                or any(review[k] != source[k] for k in ("delivery_id", "order_line_id"))
                or not amount
            ):
                continue
            consumed = min(amount, Decimal(item["quantity"]))
            if consumed == Decimal(item["quantity"]):
                self.change(
                    actor,
                    "review_transfers",
                    item["id"],
                    {"status": "approved", "reason": why, "approval_id": approval_id},
                )
            else:
                self.change(
                    actor, "review_transfers", item["id"], {"status": "released", "reason": why}
                )
                for q, status in (
                    (consumed, "approved"),
                    (Decimal(item["quantity"]) - consumed, "claimed"),
                ):
                    self.add(
                        actor,
                        "review_transfers",
                        {
                            "customer_id": item["customer_id"],
                            "review_id": item["review_id"],
                            "statement_id": statement,
                            "quantity": q,
                            "status": status,
                            "approval_id": approval_id if status == "approved" else None,
                            "reason": why,
                        },
                    )
            amount -= consumed

    def confirmed_header(self, actor, statement, fees, reconfirmation):
        self.conn.execute(
            text(
                "UPDATE statements SET status='confirmed',version=version+1,"
                "fees_confirmed=:fees,reconfirmation=:reconfirmation "
                "WHERE organization_id=:org AND id=:id"
            ),
            {
                "org": actor.organization_id,
                "id": statement,
                "fees": fees,
                "reconfirmation": reconfirmation,
            },
        )

    def protect_delivery(self, actor, delivery):
        if self.conn.execute(
            text(
                "SELECT 1 FROM statement_approvals WHERE organization_id=:org "
                "AND delivery_id=:delivery AND quantity>0 LIMIT 1"
            ),
            {"org": actor.organization_id, "delivery": delivery},
        ).first():
            raise BusinessError("STATEMENT_APPROVED_SOURCE_PROTECTED", 409)

    def backup_hashes(self):
        if self.conn.execute(text("SELECT to_regclass('statement_evidence')")).scalar_one() is None:
            return []
        return list(
            self.conn.execute(
                text(
                    "SELECT DISTINCT object_hash FROM statement_evidence "
                    "WHERE object_hash IS NOT NULL"
                )
            ).scalars()
        )
