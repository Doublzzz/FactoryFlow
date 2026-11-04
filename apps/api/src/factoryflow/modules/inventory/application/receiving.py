"""Inventory participant in purchasing's transaction; never commits or journals twice."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.domain.stock import validate_quantity, validate_range


class InventoryReceivingEffects:
    def __init__(self, inventory, catalog):
        self.inventory = inventory
        self.catalog = catalog

    def on_receive(self, actor, receipt, lines):
        totals = defaultdict(Decimal)
        accounts = {}
        for identifier in sorted({line["material_id"] for line in lines}):
            self.catalog.require(actor, identifier, kind="raw")
            account = self.inventory.account(actor, identifier, lock=True)
            if account is None:
                raise BusinessError("INVENTORY_NOT_MANAGED", 409)
            accounts[identifier] = account
        for line in lines:
            account = accounts[line["material_id"]]
            if account["canonical_unit"] != line["canonical_unit"]:
                raise BusinessError("INVENTORY_UNIT_MISMATCH", 409)
            totals[line["material_id"]] += validate_quantity(
                line["quantity"], account["canonical_unit"], positive=True
            ).value
        for identifier, quantity in totals.items():
            validate_range(Decimal(accounts[identifier]["balance"]) + quantity)
        for line in sorted(lines, key=lambda item: (item["material_id"], item["id"])):
            self.inventory.append(
                actor,
                line["material_id"],
                "purchase_receipt",
                Decimal(line["quantity"]),
                receipt["business_date"],
                purchase_receipt_line_id=line["id"],
            )

    def on_void(self, actor, receipt, lines):
        originals = self.inventory.purchase_entries(actor, [line["id"] for line in lines])
        if len(originals) != len(lines):
            raise BusinessError("PURCHASE_INVENTORY_MISMATCH", 409)
        totals = defaultdict(Decimal)
        for entry in originals:
            totals[entry["material_id"]] += Decimal(entry["delta"])
        for identifier, quantity in sorted(totals.items()):
            account = self.inventory.account(actor, identifier, lock=True)
            if Decimal(account["balance"]) < quantity:
                raise BusinessError("PURCHASE_RECEIPT_INSUFFICIENT_BALANCE", 409)
        for entry in originals:
            self.inventory.append(
                actor,
                entry["material_id"],
                "purchase_receipt_void",
                -Decimal(entry["delta"]),
                date.today(),
                reason=receipt["void_reason"],
                reverses_id=entry["id"],
                purchase_receipt_line_id=entry["purchase_receipt_line_id"],
            )
