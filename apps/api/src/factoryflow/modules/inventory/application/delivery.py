"""Participates in fulfillment's connection and transaction; never commits."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.domain.stock import validate_range


class InventoryDeliveryEffects:
    def __init__(self, inventory, catalog):
        self.inventory = inventory
        self.catalog = catalog

    def lock(self, actor):
        self.catalog.lock(actor)

    def on_create(self, actor, delivery, lines, decision):
        identifiers = sorted({line["material_id"] for line in lines if line.get("material_id")})
        accounts = {
            identifier: self.inventory.account(actor, identifier, lock=True)
            for identifier in identifiers
        }
        totals = defaultdict(Decimal)
        for line in lines:
            account = accounts.get(line.get("material_id"))
            if account and decision["mode"] == "sync":
                if (
                    line["canonical_unit"] is None
                    or line["canonical_unit"] != account["canonical_unit"]
                ):
                    raise BusinessError("INVENTORY_UNIT_MISMATCH", 409)
                totals[line["material_id"]] += Decimal(line["quantity"])
        for identifier, total in totals.items():
            result = Decimal(accounts[identifier]["balance"]) - total
            validate_range(total, result)
            if result < 0 and not decision["shortage_confirmed"]:
                raise BusinessError("INVENTORY_SHORTAGE", 409)
        snapshots = {}
        for line in sorted(lines, key=lambda item: (item.get("material_id") or "", item["id"])):
            material_id = line.get("material_id")
            account = accounts.get(material_id)
            state = "unlinked" if material_id is None else "unmanaged"
            movement, reason = None, None
            if account:
                skipped = decision["mode"] == "skip"
                state = "skipped" if skipped else "tracked"
                reason = "USER_SKIPPED" if skipped else None
                movement = self.inventory.append(
                    actor,
                    material_id,
                    "skip" if skipped else "delivery",
                    Decimal(0) if skipped else -Decimal(line["quantity"]),
                    delivery["delivery_date"],
                    reason=reason,
                    delivery_id=delivery["id"],
                    order_line_id=line["id"],
                    shortage_confirmed=decision["shortage_confirmed"] and not skipped,
                )
                if not skipped and Decimal(movement["balance_after"]) < 0:
                    reason = "MISSING_RECEIPT"
            snapshots[line["id"]] = {
                "state": state,
                "material_id": material_id,
                "canonical_unit": line["canonical_unit"],
                "quantity": line["quantity"],
                "movement_id": movement["id"] if movement else None,
                "reason": reason,
                "mode": decision["mode"],
                "shortage_confirmed": decision["shortage_confirmed"],
            }
        return snapshots

    def on_void(self, actor, delivery_id, reason):
        originals = self.inventory.delivery_entries(actor, delivery_id)
        for identifier in sorted({entry["material_id"] for entry in originals}):
            self.inventory.account(actor, identifier, lock=True)
        for original in originals:
            self.inventory.append(
                actor,
                original["material_id"],
                "delivery_void",
                -Decimal(original["delta"]),
                date.today(),
                reason=reason,
                delivery_id=delivery_id,
                order_line_id=original["order_line_id"],
                reverses_id=original["id"],
            )
