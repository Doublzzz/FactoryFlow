from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.statements.application.settings import StatementSettings
from factoryflow.modules.statements.domain.draft import (
    canonical,
    period,
    prepare_draft,
    price,
    reason,
    source_key,
)


@dataclass
class StatementWork:
    statements: object
    customers: object
    deliveries: object
    orders: object
    journal: object
    exports: object = None
    lifecycle: object = None
    templates: object = None


class StatementService:
    def __init__(self, transaction, read_transaction=None):
        self.transaction = transaction
        self.read_transaction = read_transaction or transaction
        self.settings = StatementSettings(transaction)

    @staticmethod
    def require_version(current, expected):
        if type(expected) is not int or expected != current["version"]:
            raise BusinessError("VERSION_CONFLICT", 409)

    @staticmethod
    def resolve(work, actor, body, identifier=None, current=None):
        keys = [source_key(line) for line in body["lines"]]
        sources = work.deliveries.lock_sources(actor, keys)
        refs = {
            (source["order_id"], source["revision_id"], source["order_line_id"])
            for source in sources.values()
        }
        orders = work.orders.read(actor, refs)
        allocated = work.statements.allocated(actor, keys, identifier)
        previous = {source_key(line): line for line in current["lines"]} if current else {}
        result = []
        for line in body["lines"]:
            key = source_key(line)
            src = sources[key]
            origin = orders[(src["order_id"], src["revision_id"], src["order_line_id"])]
            if (
                src["customer_id"] != body["customer_id"]
                or origin["customer_id"] != body["customer_id"]
                or src["delivery_date"] > body["period_end"]
            ):
                raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
            if origin["currency"] != body.get("currency", "CNY"):
                raise BusinessError("STATEMENT_CURRENCY_MISMATCH", 409)
            quantity = Decimal(line["quantity"])
            if (
                src["quantity_policy"]["mode"] == "INTEGER_ONLY"
                and quantity != quantity.to_integral_value()
            ):
                raise BusinessError("UNIT_REQUIRES_INTEGER_QUANTITY")
            if quantity > Decimal(src["quantity"]) - allocated.get(key, Decimal(0)):
                raise BusinessError("STATEMENT_QUANTITY_EXCEEDED", 409)
            try:
                source_price = price(origin["source_unit_price"])
            except BusinessError:
                source_price = None
            old_price = previous[key]["unit_price"] if key in previous else source_price
            chosen = line.get("unit_price", old_price)
            if quantity < Decimal(src["quantity"]) or chosen != old_price or chosen != source_price:
                reason(line["reason"], True)
            snapshot = (
                previous[key]["source"]
                if key in previous
                else {
                    **src,
                    "source_unit_price": origin["source_unit_price"],
                    "source_amount": origin["source_amount"],
                    "currency": origin["currency"],
                    "item_code": origin["item_code"],
                    "item_name": origin["item_name"],
                    "specification": origin["specification"],
                }
            )
            result.append(
                {
                    **line,
                    "unit_price": chosen,
                    "source": snapshot,
                    "status": "included" if quantity else "deferred",
                }
            )
        active = {source_key(line) for line in result if line["status"] == "included"}
        if current:
            active.update(source_key(line) for line in current.get("settlement_lines", []))
        for item in body["adjustments"]:
            if "delivery_id" in item and source_key(item) not in active:
                raise BusinessError("STATEMENT_ADJUSTMENT_SOURCE_REQUIRED")
        if current:
            removed = {
                source_key(line)
                for line in current["lines"]
                if line["status"] in {"included", "deferred"}
            } - set(keys)
            changed_adjustments = current["adjustments"] != body["adjustments"]
            if (
                removed
                or changed_adjustments
                or current["tax_mode"] != body["tax_mode"]
                or (current["tax_rate"] != body["tax_rate"])
            ):
                reason(body["reason"], True)
        return result

    def create(self, actor, key, payload):
        actor.require_write()
        body = prepare_draft(payload)
        with self.transaction() as work:
            prior = work.journal.claim(actor, "statement.create", key, body)
            if prior is not None:
                return prior
            customer = work.customers.lock(actor, UUID(body["customer_id"]))
            identifier = uuid7()
            work.statements.create(actor, identifier, body, customer)
            lines = self.resolve(work, actor, body)
            work.statements.write_lines(actor, identifier, body["customer_id"], lines)
            return self.finish(work, actor, key, identifier, "create", body["reason"])

    def save(self, actor, key, identifier, expected, payload, *, reopen=False):
        actor.require_write()
        body = prepare_draft(payload)
        command = "reopen" if reopen else "save"
        with self.transaction() as work:
            prior = work.journal.claim(
                actor,
                "statement." + command,
                key,
                {"id": str(identifier), "expected_version": expected, **body},
            )
            if prior is not None:
                return prior
            work.customers.lock(actor, UUID(body["customer_id"]))
            current = work.statements.get(actor, identifier, history=False)
            self.require_version(current, expected)
            if current["status"] not in ({"abandoned", "void"} if reopen else {"draft"}):
                raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
            if current.get("currency", "CNY") != body.get("currency", "CNY"):
                raise BusinessError("STATEMENT_CURRENCY_IMMUTABLE", 409)
            if any(
                current[field] != body[field]
                for field in ("customer_id", "period_start", "period_end")
            ):
                raise BusinessError("STATEMENT_PERIOD_IMMUTABLE", 409)
            if reopen:
                reason(body["reason"], True)
            lines = self.resolve(work, actor, body, identifier, current)
            work.lifecycle.reconcile_transfers(
                actor, identifier, lines, body["reason"] or "Draft changed"
            )
            work.statements.update(actor, identifier, body)
            work.statements.write_lines(actor, identifier, body["customer_id"], lines)
            return self.finish(work, actor, key, identifier, command, body["reason"])

    def abandon(self, actor, key, identifier, expected, why, *, exported=False):
        actor.require_write()
        why = reason(why, True)
        action = "void" if exported else "abandon"
        with self.transaction() as work:
            prior = work.journal.claim(
                actor,
                "statement." + action,
                key,
                {"id": str(identifier), "expected_version": expected, "reason": why},
            )
            if prior is not None:
                return prior
            initial = work.statements.get(actor, identifier, history=False)
            work.customers.lock(actor, UUID(initial["customer_id"]))
            current = work.statements.get(actor, identifier, history=False)
            self.require_version(current, expected)
            if current["status"] != "draft":
                raise BusinessError("STATEMENT_STATE_CONFLICT", 409)
            if not exported and work.exports.listing(actor, identifier, limit=1)["items"]:
                raise BusinessError("STATEMENT_EXPORTED_USE_VOID", 409)
            current["adjustments"] = [
                {**item, "status": "needs_review"} for item in current["adjustments"]
            ]
            for allocation in work.lifecycle.rows(actor, "allocations", statement=identifier):
                if allocation["status"] == "reserved":
                    work.lifecycle.change(
                        actor,
                        "allocations",
                        allocation["id"],
                        {"status": "released", "reason": why},
                    )
            work.lifecycle.reconcile_transfers(actor, identifier, [], why)
            work.statements.write_lines(actor, identifier, current["customer_id"], [])
            work.statements.update(actor, identifier, current, "void" if exported else "abandoned")
            return self.finish(work, actor, key, identifier, action, why)

    @staticmethod
    def finish(work, actor, key, identifier, action, why):
        work.statements.event(actor, identifier, action, why)
        result = work.statements.get(actor, identifier)
        work.journal.audit(actor, "statement." + action, identifier)
        work.journal.finish(actor, "statement." + action, key, result)
        return result

    def detail(self, actor, identifier):
        with self.read_transaction() as work:
            return work.statements.get(actor, identifier)

    def list(self, actor, customer_id, cursor=None, limit=50):
        with self.read_transaction() as work:
            work.customers.require(actor, customer_id)
            return work.statements.list(actor, customer_id, cursor, limit)

    def candidates(
        self,
        actor,
        customer_id,
        start,
        end,
        cursor=None,
        limit=50,
        statement_id=None,
        currency="CNY",
    ):
        start, end = period(start, end)
        if currency not in ("CNY", "USD"):
            raise BusinessError("CURRENCY_REQUIRED", field="currency")
        with self.read_transaction() as work:
            work.customers.require(actor, customer_id)
            if statement_id:
                existing = work.statements.get(actor, statement_id, history=False)
                if existing["customer_id"] != str(customer_id):
                    raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
                if existing.get("currency", "CNY") != currency:
                    raise BusinessError("STATEMENT_CURRENCY_MISMATCH", 409)
            page = work.deliveries.candidates(actor, customer_id, end, cursor, limit)
            refs = {(s["order_id"], s["revision_id"], s["order_line_id"]) for s in page["items"]}
            orders = work.orders.read(actor, refs)
            used = work.statements.allocated(
                actor, [source_key(s) for s in page["items"]], statement_id
            )
            for item in page["items"]:
                origin = orders[(item["order_id"], item["revision_id"], item["order_line_id"])]
                item.update(
                    {
                        field: origin[field]
                        for field in (
                            "item_code",
                            "item_name",
                            "specification",
                            "source_unit_price",
                            "source_amount",
                            "currency",
                        )
                    }
                )
                item["available_quantity"] = canonical(
                    Decimal(item["quantity"]) - used.get(source_key(item), 0)
                )
                item["cross_period"] = item["delivery_date"] < start
                item.pop("organization_id", None)
            page["items"] = [item for item in page["items"] if item["currency"] == currency]
            page["overlapping_statements"] = work.statements.overlaps(
                actor, customer_id, start, end, currency
            )
            return page
