"""Delivery-owned sources participating in the caller's transaction."""

from factoryflow.kernel.contracts import BusinessError


class SettlementDeliveries:
    def __init__(self, repository):
        self.repository = repository

    def candidates(self, actor, customer_id, end_date, cursor=None, limit=50):
        return self.repository.settlement_sources(actor, customer_id, end_date, cursor, limit)

    def lock_sources(self, actor, keys):
        sources = {}
        for identifier in sorted({key[0] for key in keys}):
            delivery = self.repository.get(actor, identifier, lock=True)
            if delivery["status"] != "active":
                raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
            for line in delivery["lines"]:
                key = (str(identifier), line["order_line_id"])
                sources[key] = {
                    **line,
                    "delivery_id": str(identifier),
                    "order_id": delivery["order_id"],
                    "revision_id": delivery["revision_id"],
                    "customer_id": delivery["customer_id"],
                    "delivery_date": delivery["delivery_date"],
                    "order_number": delivery["order_number"],
                }
        if not set(keys) <= sources.keys():
            raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
        return {key: sources[key] for key in keys}
