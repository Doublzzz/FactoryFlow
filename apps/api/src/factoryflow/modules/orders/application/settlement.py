"""Read exact source revisions, never substitute the current order revision."""

from factoryflow.kernel.contracts import BusinessError


class SettlementOrderSources:
    def __init__(self, repository):
        self.repository = repository

    def read(self, actor, references):
        rows = self.repository.settlement_sources(actor, {r[2] for r in references})
        indexed = {(row["order_id"], row["revision_id"], row["id"]): row for row in rows}
        if not set(references) <= indexed.keys():
            raise BusinessError("STATEMENT_SOURCE_INVALID", 409)
        return {ref: indexed[ref] for ref in references}
