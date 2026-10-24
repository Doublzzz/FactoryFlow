"""Statement-owned participation in delivery void; caller owns the transaction."""


class StatementDeliveryEffects:
    def __init__(self, repository, journal):
        self.repository, self.journal = repository, journal

    def on_void(self, actor, delivery_id, reason):
        self.repository.protect_delivery(actor, delivery_id)
        for identifier in self.repository.affected(actor, delivery_id):
            current = self.repository.get(actor, identifier, history=False)
            for item in current["adjustments"]:
                if item.get("delivery_id") == str(delivery_id):
                    item["status"] = "needs_review"
            self.repository.source_void(actor, identifier, delivery_id)
            self.repository.update(actor, identifier, current)
            self.repository.event(actor, identifier, "source_void", reason)
            self.journal.audit(actor, "statement.source_void", identifier)
