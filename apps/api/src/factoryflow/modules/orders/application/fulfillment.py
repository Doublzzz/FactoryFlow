"""Order-owned participation in a caller's transaction; never opens a transaction."""

from decimal import Decimal
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError


class FulfillmentOrders:
    def __init__(self, repository):
        self.repository = repository

    def lock(self, actor, order_id):
        return self.repository.get(actor, order_id, lock=True)

    def source(self, actor, current, customer_id, revision_id, expected, quantities):
        if current["version"] != expected:
            raise BusinessError("VERSION_CONFLICT", 409)
        if current["status"] != "active":
            raise BusinessError("ORDER_NOT_ACTIVE", 409)
        if current["customer_id"] != str(customer_id) or current["revision_id"] != str(revision_id):
            raise BusinessError("DELIVERY_SOURCE_CONFLICT", 409)
        lines = {line["id"]: line for line in self.repository.material_lines(actor, revision_id)}
        result = []
        for identifier, quantity in quantities.items():
            line = lines.get(identifier)
            if line is None:
                raise BusinessError("DELIVERY_SOURCE_CONFLICT", 409)
            value = Decimal(quantity)
            if (
                line["quantity_policy"]["mode"] == "INTEGER_ONLY"
                and value != value.to_integral_value()
            ):
                raise BusinessError("UNIT_REQUIRES_INTEGER_QUANTITY")
            if value > Decimal(line["remaining_quantity"]):
                raise BusinessError("DELIVERY_EXCEEDS_REMAINING", 409)
            result.append({**line, "quantity": quantity})
        return result

    def apply(self, actor, current, quantities, reverse=False, reason=None):
        self.repository.apply_delivery(actor, UUID(current["id"]), quantities, reverse)
        self.repository.event(
            actor,
            UUID(current["id"]),
            "delivery_void" if reverse else "delivery_create",
            current["version"] + 1,
            UUID(current["revision_id"]),
            reason,
        )
