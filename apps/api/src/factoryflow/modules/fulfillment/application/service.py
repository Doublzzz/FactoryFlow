from dataclasses import dataclass
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import BusinessError, CommandJournal
from factoryflow.modules.customers.public import CustomerAccess
from factoryflow.modules.fulfillment.domain.delivery import prepare_delivery, void_reason
from factoryflow.modules.inventory.public import InventoryDeliveryEffects
from factoryflow.modules.orders.public import FulfillmentOrders
from factoryflow.modules.statements.public import StatementDeliveryEffects


@dataclass
class DeliveryWork:
    deliveries: object
    orders: FulfillmentOrders
    customers: CustomerAccess
    journal: CommandJournal
    statements: StatementDeliveryEffects | None = None
    inventory: InventoryDeliveryEffects | None = None


class DeliveryService:
    def __init__(self, transaction):
        self.transaction = transaction

    def create(self, actor, key, payload):
        actor.require_write()
        request = prepare_delivery(payload)
        with self.transaction() as work:
            prior = work.journal.claim(actor, "delivery.create", key, request.payload())
            if prior is not None:
                return prior
            if work.inventory is not None:
                work.inventory.lock(actor)
            current = work.orders.lock(actor, request.order_id)
            lines = work.orders.source(
                actor,
                current,
                request.customer_id,
                request.revision_id,
                request.expected_version,
                request.quantities,
            )
            customer = work.customers.require(actor, request.customer_id)
            identifier = uuid7()
            work.deliveries.insert(actor, identifier, request, current, customer, lines)
            work.orders.apply(actor, current, request.quantities)
            if work.inventory is not None:
                snapshots = work.inventory.on_create(
                    actor,
                    {"id": identifier, "delivery_date": request.delivery_date},
                    lines,
                    {
                        "mode": request.inventory_mode,
                        "shortage_confirmed": request.confirm_inventory_shortage,
                    },
                )
                work.deliveries.inventory_snapshots(actor, identifier, snapshots)
            work.deliveries.action(actor, identifier, "create", None, None)
            result = work.deliveries.get(actor, identifier, inventory=True)
            work.journal.audit(actor, "delivery.create", identifier)
            work.journal.finish(actor, "delivery.create", key, result)
            return result

    def void(self, actor, key, identifier, expected, reason):
        actor.require_write()
        reason = void_reason(reason)
        if type(expected) is not int or expected < 1:
            raise BusinessError("INVALID_INPUT")
        with self.transaction() as work:
            prior = work.journal.claim(
                actor,
                "delivery.void",
                key,
                {"id": str(identifier), "expected_version": expected, "reason": reason},
            )
            if prior is not None:
                return prior
            if work.inventory is not None:
                work.inventory.lock(actor)
            initial = work.deliveries.get(actor, identifier)
            work.customers.lock(actor, UUID(initial["customer_id"]))
            # Lock the order before delivery. Re-read after locking to observe a competing void.
            current = work.orders.lock(actor, UUID(initial["order_id"]))
            delivery = work.deliveries.get(actor, identifier, lock=True)
            if delivery["status"] != "active":
                raise BusinessError("DELIVERY_NOT_ACTIVE", 409)
            if delivery["version"] != expected:
                raise BusinessError("VERSION_CONFLICT", 409)
            quantities = {line["order_line_id"]: line["quantity"] for line in delivery["lines"]}
            original = work.deliveries.create_action(actor, identifier)
            if work.statements is not None:
                work.statements.on_void(actor, identifier, reason)
            if work.inventory is not None:
                work.inventory.on_void(actor, identifier, reason)
            work.orders.apply(actor, current, quantities, reverse=True, reason=reason)
            work.deliveries.mark_void(actor, identifier, reason)
            work.deliveries.action(actor, identifier, "void", original, reason)
            result = work.deliveries.get(actor, identifier, inventory=True)
            work.journal.audit(actor, "delivery.void", identifier)
            work.journal.finish(actor, "delivery.void", key, result)
            return result

    def detail(self, actor, identifier):
        with self.transaction() as work:
            return work.deliveries.get(actor, identifier, inventory=True)

    def list(self, actor, customer_id=None, cursor=None, limit=50, order_id=None):
        if not 1 <= limit <= 100:
            raise BusinessError("INVALID_INPUT")
        with self.transaction() as work:
            return work.deliveries.list(actor, customer_id, cursor, limit, order_id)
