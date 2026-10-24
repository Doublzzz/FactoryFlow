from dataclasses import dataclass

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.fulfillment.domain.print_layout import default_layout, normalize_layout
from factoryflow.modules.orders.public import SettlementOrderSources


@dataclass
class DeliveryLayoutWork:
    layouts: object
    deliveries: object
    sources: SettlementOrderSources
    journal: object


class DeliveryLayouts:
    def __init__(self, transaction, read_transaction):
        self.transaction = transaction
        self.read_transaction = read_transaction

    @staticmethod
    def current(work, actor):
        saved = work.layouts.current(actor)
        return {
            **(saved or {"version": 0, "config": default_layout(), "updated_at": None}),
            "defaults": default_layout(),
        }

    def get(self, actor):
        with self.read_transaction() as work:
            return self.current(work, actor)

    def save(self, actor, key, expected, payload):
        actor.require_write()
        if type(expected) is not int or expected < 0:
            raise BusinessError("INVALID_INPUT", 422, "expected_version")
        config = normalize_layout(payload)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "delivery.layout", key, {"expected_version": expected, "config": config}
            )
            if prior is not None:
                return prior
            if self.current(work, actor)["version"] != expected:
                raise BusinessError("VERSION_CONFLICT", 409)
            work.layouts.append(actor, expected, config)
            result = self.current(work, actor)
            work.journal.audit(actor, "delivery.layout", actor.organization_id)
            work.journal.finish(actor, "delivery.layout", key, result)
            return result

    def printable(self, actor, identifier, payload=None):
        config = normalize_layout(payload) if payload is not None else None
        with self.read_transaction() as work:
            delivery = work.deliveries.get(actor, identifier)
            saved = self.current(work, actor)
            references = {
                (delivery["order_id"], delivery["revision_id"], line["order_line_id"])
                for line in delivery["lines"]
            }
            sources = work.sources.read(actor, references)
            for line in delivery["lines"]:
                source = sources[
                    (delivery["order_id"], delivery["revision_id"], line["order_line_id"])
                ]
                for field in ("item_code", "item_name", "specification"):
                    line[field] = source.get(field)
            return delivery, config if config is not None else saved["config"], saved["version"]
