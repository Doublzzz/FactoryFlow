"""Raw issues and partial returns use the same immutable quantity ledger."""

from decimal import Decimal
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.application.service import InventoryService
from factoryflow.modules.inventory.domain.stock import (
    prepare,
    reason_text,
    validate_quantity,
    validate_range,
)


class RawInventoryService(InventoryService):
    def __init__(self, transaction, read_transaction=None):
        super().__init__(transaction, read_transaction, material_kind="raw")

    def issue(self, actor, key, material_id, payload):
        actor.require_write()
        request = prepare(payload)
        request["reason"] = reason_text(request["reason"], required=True)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "raw_inventory.issue", key, {"material_id": str(material_id), **request}
            )
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            work.catalog.require(actor, material_id, active=False, kind="raw")
            account = work.inventory.account(actor, material_id, lock=True)
            if account is None:
                raise BusinessError("INVENTORY_NOT_MANAGED", 409)
            quantity = validate_quantity(
                request["quantity"], account["canonical_unit"], positive=True
            ).value
            if quantity > Decimal(account["balance"]):
                raise BusinessError("RAW_INVENTORY_INSUFFICIENT", 409)
            entry = work.inventory.append(
                actor,
                material_id,
                "material_issue",
                -quantity,
                request["business_date"],
                reason=request["reason"],
            )
            result = {"account": work.inventory.account(actor, material_id), "entry": entry}
            work.journal.audit(actor, "raw_inventory.issue", UUID(entry["id"]))
            work.journal.finish(actor, "raw_inventory.issue", key, result)
            return result

    def return_issue(self, actor, key, issue_id, payload):
        actor.require_write()
        request = prepare(payload)
        request["reason"] = reason_text(request["reason"], required=True)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "raw_inventory.return", key, {"issue_id": str(issue_id), **request}
            )
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            original = work.inventory.entry(actor, issue_id)
            if original["kind"] != "material_issue":
                raise BusinessError("RAW_RETURN_REQUIRES_ISSUE", 409)
            material_id = original["material_id"]
            work.catalog.require(actor, material_id, active=False, kind="raw")
            account = work.inventory.account(actor, material_id, lock=True)
            quantity = validate_quantity(
                request["quantity"], account["canonical_unit"], positive=True
            ).value
            if quantity + Decimal(original["returned_quantity"]) > -Decimal(original["delta"]):
                raise BusinessError("RAW_RETURN_EXCEEDS_ISSUED", 409)
            validate_range(Decimal(account["balance"]) + quantity)
            entry = work.inventory.append(
                actor,
                material_id,
                "material_return",
                quantity,
                request["business_date"],
                reason=request["reason"],
                returns_issue_id=issue_id,
                production_order_id=original.get("production_order_id"),
            )
            result = {"account": work.inventory.account(actor, material_id), "entry": entry}
            work.journal.audit(actor, "raw_inventory.return", UUID(entry["id"]))
            work.journal.finish(actor, "raw_inventory.return", key, result)
            return result
