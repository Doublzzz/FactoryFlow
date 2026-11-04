"""Inventory effects join the production command's transaction."""

from datetime import date
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.domain.stock import number, validate_quantity, validate_range


class InventoryProductionEffects:
    def __init__(self, inventory, catalog):
        self.inventory = inventory
        self.catalog = catalog

    @staticmethod
    def movement(entry):
        return {
            "entry_id": entry["id"],
            "production_order_id": entry["production_order_id"],
            "material_id": entry["material_id"],
            "quantity": number(abs(Decimal(entry["delta"]))),
            "business_date": entry["business_date"],
            "reason": entry["reason"],
        }

    def issues(self, actor, production_id, offset, limit):
        return self.inventory.production_issues(actor, production_id, offset, limit)

    def issue(self, actor, production_id, request):
        material_id = request["material_id"]
        self.catalog.require(actor, material_id, active=False, kind="raw")
        account = self.inventory.account(actor, material_id, lock=True)
        if account is None:
            raise BusinessError("INVENTORY_NOT_MANAGED", 409)
        quantity = validate_quantity(
            request["quantity"], account["canonical_unit"], positive=True
        ).value
        if quantity > Decimal(account["balance"]):
            raise BusinessError("RAW_INVENTORY_INSUFFICIENT", 409)
        return self.movement(
            self.inventory.append(
                actor,
                material_id,
                "material_issue",
                -quantity,
                request["business_date"],
                reason=request["reason"],
                production_order_id=production_id,
            )
        )

    def return_issue(self, actor, production_id, issue_id, request):
        original = self.inventory.entry(actor, issue_id)
        if (
            original["kind"] != "material_issue"
            or original.get("production_order_id") != production_id
        ):
            raise BusinessError("PRODUCTION_ISSUE_MISMATCH", 409)
        account = self.inventory.account(actor, original["material_id"], lock=True)
        quantity = validate_quantity(
            request["quantity"], account["canonical_unit"], positive=True
        ).value
        if quantity + Decimal(original["returned_quantity"]) > -Decimal(original["delta"]):
            raise BusinessError("RAW_RETURN_EXCEEDS_ISSUED", 409)
        validate_range(Decimal(account["balance"]) + quantity)
        return self.movement(
            self.inventory.append(
                actor,
                original["material_id"],
                "material_return",
                quantity,
                request["business_date"],
                reason=request["reason"],
                returns_issue_id=issue_id,
                production_order_id=production_id,
            )
        )

    def on_complete(self, actor, production, completion):
        quantity = Decimal(completion["quantity"])
        if quantity == 0:
            return
        account = self.inventory.account(actor, production["material_id"], lock=True)
        if account is None:
            raise BusinessError("INVENTORY_NOT_MANAGED", 409)
        if account["canonical_unit"] != production["canonical_unit"]:
            raise BusinessError("INVENTORY_UNIT_MISMATCH", 409)
        validate_range(Decimal(account["balance"]) + quantity)
        self.inventory.append(
            actor,
            production["material_id"],
            "production_receipt",
            quantity,
            completion["business_date"],
            production_order_id=production["id"],
            production_completion_id=completion["id"],
        )

    def on_void(self, actor, production, completion):
        quantity = Decimal(completion["quantity"])
        if quantity == 0:
            return
        original = self.inventory.production_receipt(actor, completion["id"])
        account = self.inventory.account(actor, production["material_id"], lock=True)
        if Decimal(account["balance"]) < quantity:
            raise BusinessError("PRODUCTION_RECEIPT_IN_USE", 409)
        self.inventory.append(
            actor,
            production["material_id"],
            "production_receipt_void",
            -quantity,
            date.today(),
            reason=completion["void_reason"],
            reverses_id=original["id"],
            production_order_id=production["id"],
            production_completion_id=completion["id"],
        )
