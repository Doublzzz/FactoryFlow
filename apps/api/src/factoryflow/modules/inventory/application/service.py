"""Inventory commands own one transaction; reads never create accounts."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.inventory.domain.stock import (
    prepare,
    reason_text,
    validate_quantity,
    validate_range,
)
from factoryflow.modules.materials.public import MaterialCatalog


@dataclass
class InventoryWork:
    inventory: object
    catalog: MaterialCatalog
    journal: object


class InventoryService:
    def __init__(self, transaction, read_transaction=None):
        self.transaction = transaction
        self.read_transaction = read_transaction or transaction

    def record(self, actor, key, material_id, kind, payload):
        actor.require_write()
        request = prepare(payload, count=kind == "count")
        if kind not in {"opening", "receipt", "count"}:
            raise BusinessError("INVALID_INPUT")
        command = f"inventory.{kind}"
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, command, key, {"material_id": str(material_id), **request}
            )
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            material = work.catalog.require(actor, material_id, active=kind == "opening")
            account = work.inventory.account(actor, material_id, lock=True)
            if kind == "opening":
                if account is not None:
                    raise BusinessError("INVENTORY_ALREADY_OPEN", 409)
                confirmed = validate_quantity(request["quantity"], material["unit"])
                work.inventory.open_account(actor, material_id, confirmed.policy.canonical_unit)
                balance, target = Decimal(0), confirmed.value
            else:
                if account is None:
                    raise BusinessError("INVENTORY_NOT_MANAGED", 409)
                confirmed = validate_quantity(
                    request["quantity"], account["canonical_unit"], positive=kind == "receipt"
                )
                balance = Decimal(account["balance"])
                target = confirmed.value if kind == "count" else None
                if kind == "count" and request["expected_version"] != account["version"]:
                    raise BusinessError("VERSION_CONFLICT", 409)
            delta = confirmed.value - balance if kind == "count" else confirmed.value
            validate_range(delta, balance + delta)
            entry = work.inventory.append(
                actor,
                material_id,
                kind,
                delta,
                request["business_date"],
                reason=request["reason"],
                target=target,
                expected=request.get("expected_version"),
            )
            result = {"account": work.inventory.account(actor, material_id), "entry": entry}
            work.journal.audit(actor, command, material_id)
            work.journal.finish(actor, command, key, result)
            return result

    def void_receipt(self, actor, key, entry_id, reason):
        actor.require_write()
        reason = reason_text(reason, required=True)
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "inventory.receipt_void", key, {"entry_id": str(entry_id), "reason": reason}
            )
            if prior is not None:
                return prior
            work.catalog.lock(actor)
            original = work.inventory.entry(actor, entry_id)
            if original["kind"] != "receipt" or original["reversed_by"]:
                raise BusinessError("INVENTORY_RECEIPT_NOT_ACTIVE", 409)
            account = work.inventory.account(actor, original["material_id"], lock=True)
            delta = -Decimal(original["delta"])
            if Decimal(account["balance"]) + delta < 0:
                raise BusinessError("INVENTORY_RECEIPT_IN_USE", 409)
            entry = work.inventory.append(
                actor,
                original["material_id"],
                "receipt_void",
                delta,
                date.today(),
                reason=reason,
                reverses_id=entry_id,
            )
            result = {
                "account": work.inventory.account(actor, original["material_id"]),
                "entry": entry,
            }
            work.journal.audit(actor, "inventory.receipt_void", entry_id)
            work.journal.finish(actor, "inventory.receipt_void", key, result)
            return result

    def detail(self, actor, material_id, cursor=None, limit=50):
        self._limit(limit)
        with self.read_transaction() as work:
            material = work.catalog.require(actor, material_id, active=False)
            return {
                "material": material,
                "account": work.inventory.account(actor, material_id),
                **work.inventory.entries(actor, material_id, cursor, limit),
            }

    def list(self, actor, cursor=None, limit=50):
        self._limit(limit)
        with self.read_transaction() as work:
            result = work.inventory.accounts(actor, cursor, limit)
            materials = work.catalog.summarize(
                actor, [item["material_id"] for item in result["items"]]
            )
            return {
                **result,
                "items": [
                    {"material": materials[item["material_id"]], "account": item}
                    for item in result["items"]
                ],
            }

    def preview(self, actor, material_ids):
        if not 1 <= len(material_ids) <= 200:
            raise BusinessError("INVALID_INPUT")
        with self.read_transaction() as work:
            identifiers = sorted(set(map(str, material_ids)))
            work.catalog.summarize(actor, identifiers)
            return {
                "items": [
                    {
                        "material_id": identifier,
                        "account": work.inventory.account(actor, identifier),
                    }
                    for identifier in identifiers
                ]
            }

    @staticmethod
    def _limit(limit):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise BusinessError("INVALID_INPUT")
