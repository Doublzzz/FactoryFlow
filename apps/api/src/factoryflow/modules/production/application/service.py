"""One transaction owns production evidence, stock effects, audit and replay."""

from dataclasses import dataclass
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.production.domain.production import (
    completion_request,
    create_request,
    identifier,
    material_request,
    page_arguments,
    quantity,
    transition_request,
)


@dataclass
class ProductionWork:
    production: object
    orders: object
    catalog: object
    inventory: object
    journal: object


class ProductionService:
    def __init__(self, transaction, read_transaction=None):
        self.transaction = transaction
        self.read_transaction = read_transaction or transaction

    def _command(self, actor, key, command, request, action):
        actor.require_write()
        with self.transaction() as work:
            prior = work.journal.claim(actor, command, key, request)
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            result = action(work)
            work.journal.audit(actor, command, result.get("id") or result["entry_id"])
            work.journal.finish(actor, command, key, result)
            return result

    @staticmethod
    def _view(work, actor, production):
        return {**production, "source_current": work.orders.current(actor, production)}

    @staticmethod
    def _lock(work, actor, production_id, *, require_current=False):
        previous = work.production.get(actor, production_id)
        current = work.orders.current(actor, previous, lock=True)
        production = work.production.get(actor, production_id, lock=True)
        if require_current:
            if production["status"] != "open":
                raise BusinessError("PRODUCTION_CLOSED", 409)
            if not current:
                raise BusinessError("PRODUCTION_SOURCE_CHANGED", 409)
            material = work.catalog.require(actor, production["material_id"], kind="finished")
            if (
                quantity("0", material["unit"]).policy.canonical_unit
                != production["canonical_unit"]
            ):
                raise BusinessError("PRODUCTION_UNIT_MISMATCH", 409)
        return production

    def create(self, actor, key, payload):
        request = create_request(payload)

        def create(work):
            order, line = work.orders.source(actor, request)
            material = work.catalog.require(actor, line["material_id"], kind="finished")
            confirmed = quantity(request["planned_quantity"], line["canonical_unit"], positive=True)
            material_unit = quantity("0", material["unit"]).policy.canonical_unit
            if confirmed.policy.canonical_unit is None or material_unit != line["canonical_unit"]:
                raise BusinessError("PRODUCTION_UNIT_MISMATCH", 409)
            return self._view(
                work, actor, work.production.insert(actor, request, order, line, material)
            )

        return self._command(actor, key, "production.create", request, create)

    def get(self, actor, production_id):
        with self.read_transaction() as work:
            return self._view(work, actor, work.production.get(actor, production_id))

    def list(self, actor, q="", order_id=None, offset=0, limit=50):
        page_arguments(offset, limit)
        with self.read_transaction() as work:
            page = work.production.list(actor, q, order_id, offset, limit)
            page["items"] = [self._view(work, actor, item) for item in page["items"]]
            return page

    def issues(self, actor, production_id, offset=0, limit=50):
        page_arguments(offset, limit)
        with self.read_transaction() as work:
            work.production.get(actor, production_id)
            return work.inventory.issues(actor, production_id, offset, limit)

    def completions(self, actor, production_id, offset=0, limit=50):
        page_arguments(offset, limit)
        with self.read_transaction() as work:
            work.production.get(actor, production_id)
            return work.production.completions(actor, production_id, offset, limit)

    def issue(self, actor, key, production_id, payload):
        request = {
            **material_request(payload),
            "material_id": identifier(payload.get("material_id")),
        }

        def issue(work):
            self._lock(work, actor, production_id, require_current=True)
            return work.inventory.issue(actor, str(production_id), request)

        return self._command(
            actor, key, "production.issue", {"id": str(production_id), **request}, issue
        )

    def return_issue(self, actor, key, production_id, issue_id, payload):
        request = material_request(payload)

        def return_issue(work):
            self._lock(work, actor, production_id)
            return work.inventory.return_issue(actor, str(production_id), issue_id, request)

        return self._command(
            actor,
            key,
            "production.return",
            {
                "id": str(production_id),
                "issue_id": str(issue_id),
                **request,
            },
            return_issue,
        )

    def complete(self, actor, key, production_id, payload):
        request = completion_request(payload)

        def complete(work):
            production = self._lock(work, actor, production_id, require_current=True)
            good = quantity(request["quantity"], production["canonical_unit"])
            quantity(request["scrap_quantity"], production["canonical_unit"])
            if good.value > Decimal(production["remaining_quantity"]):
                raise BusinessError("PRODUCTION_EXCEEDS_PLAN", 409)
            completion = work.production.complete(actor, production, request)
            work.inventory.on_complete(actor, production, completion)
            return completion

        return self._command(
            actor, key, "production.complete", {"id": str(production_id), **request}, complete
        )

    def void(self, actor, key, production_id, completion_id, payload):
        request = transition_request(payload)

        def void(work):
            production = self._lock(work, actor, production_id)
            completion = work.production.completion(actor, production_id, completion_id)
            if completion["version"] != request["expected_version"]:
                raise BusinessError("VERSION_CONFLICT", 409)
            if completion["status"] != "active":
                raise BusinessError("PRODUCTION_COMPLETION_VOID", 409)
            result = work.production.void(actor, completion, request["reason"])
            work.inventory.on_void(actor, production, result)
            return result

        return self._command(
            actor,
            key,
            "production.void",
            {
                "id": str(production_id),
                "completion_id": str(completion_id),
                **request,
            },
            void,
        )

    def close(self, actor, key, production_id, payload):
        request = transition_request(payload)

        def close(work):
            production = self._lock(work, actor, production_id)
            if production["version"] != request["expected_version"]:
                raise BusinessError("VERSION_CONFLICT", 409)
            if production["status"] != "open":
                raise BusinessError("PRODUCTION_CLOSED", 409)
            return self._view(
                work, actor, work.production.close(actor, production, request["reason"])
            )

        return self._command(
            actor, key, "production.close", {"id": str(production_id), **request}, close
        )
