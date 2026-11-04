"""Commands own claims, facts, stock effects and audit in one transaction."""

from dataclasses import dataclass
from decimal import Decimal
from uuid import uuid7

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.purchasing.domain.rules import (
    document_input,
    order_input,
    quantity,
    request_fingerprint,
    source_money,
    supplier_input,
    text_value,
)


@dataclass
class PurchasingWork:
    purchasing: object
    catalog: object
    inventory: object
    journal: object
    documents: object = None


class PurchasingService:
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
            work.journal.audit(actor, command, result["id"])
            work.journal.finish(actor, command, key, result)
            return result

    def list_suppliers(self, actor, q="", offset=0, limit=50):
        with self.read_transaction() as work:
            return work.purchasing.list(actor, "suppliers", q, offset, limit)

    def create_supplier(self, actor, key, payload):
        return self._command(
            actor,
            key,
            "supplier.create",
            payload,
            lambda w: w.purchasing.insert_supplier(actor, supplier_input(payload)),
        )

    def update_supplier(self, actor, key, identifier, payload):
        def change(w):
            before = w.purchasing.supplier(actor, identifier)
            if before["version"] != payload["expected_version"]:
                raise BusinessError("VERSION_CONFLICT", 409)
            return w.purchasing.update_supplier(
                actor, identifier, {**supplier_input(payload), "active": payload["active"]}
            )

        return self._command(
            actor, key, "supplier.update", {"id": str(identifier), **payload}, change
        )

    @staticmethod
    def _supplier(work, actor, identifier):
        supplier = work.purchasing.supplier(actor, identifier)
        if not supplier["active"]:
            raise BusinessError("SUPPLIER_INACTIVE", 409)
        return supplier

    def list_orders(self, actor, q="", offset=0, limit=50):
        with self.read_transaction() as w:
            return w.purchasing.list(actor, "purchase_orders", q, offset, limit)

    def get_order(self, actor, identifier):
        with self.read_transaction() as w:
            return w.purchasing.document(actor, "purchase_orders", identifier)

    def get_order_by_source(self, actor, source_id):
        with self.read_transaction() as w:
            return w.purchasing.by_source(actor, source_id)

    def create_order(self, actor, key, payload):
        def create(w):
            header = order_input(payload)
            supplier = self._supplier(w, actor, payload["supplier_id"])
            if header["source_id"]:
                header.update(
                    w.documents.verify(actor, header["source_id"], header["extraction_id"])
                )
            lines = []
            for index, source in enumerate(payload["lines"]):
                material = w.catalog.require(actor, source["material_id"], kind="raw")
                if (
                    source.get("expected_material_version") is not None
                    and material["version"] != source["expected_material_version"]
                ):
                    raise BusinessError("MATERIAL_VERSION_CONFLICT", 409)
                confirmed = quantity(source["quantity"], material["unit"])
                prices = {
                    name: source_money(source.get(name), f"lines.{index}.{name}")
                    for name in ("source_unit_price", "source_amount")
                }
                if (
                    any(value is not None for value in prices.values())
                    and header["currency"] is None
                ):
                    raise BusinessError("CURRENCY_REQUIRED", field="currency")
                lines.append({**self._line(material, confirmed), **prices})
            return w.purchasing.insert_document(
                actor,
                "purchase_orders",
                {**header, "supplier_id": supplier["id"], "supplier_name": supplier["full_name"]},
                lines,
            )

        return self._command(
            actor, key, "purchase_order.create", request_fingerprint(payload), create
        )

    def close_order(self, actor, key, identifier, payload):
        def close(w):
            order = w.purchasing.document(actor, "purchase_orders", identifier)
            self._status(order, payload, "open", "PURCHASE_ORDER_CLOSED")
            reason = text_value(payload["reason"], "reason", required=True)
            return w.purchasing.transition(actor, "purchase_orders", identifier, reason)

        return self._command(
            actor, key, "purchase_order.close", {"id": str(identifier), **payload}, close
        )

    def list_receipts(self, actor, q="", offset=0, limit=50):
        with self.read_transaction() as w:
            return w.purchasing.list(actor, "purchase_receipts", q, offset, limit)

    def get_receipt(self, actor, identifier):
        with self.read_transaction() as w:
            return w.purchasing.document(actor, "purchase_receipts", identifier)

    @staticmethod
    def _line(material, confirmed):
        return {
            "id": str(uuid7()),
            "material_id": material["id"],
            "own_code": material["own_code"],
            "material_name": material["name"],
            "specification": material["specification"],
            "canonical_unit": confirmed.policy.canonical_unit,
            "quantity": confirmed.canonical,
        }

    @staticmethod
    def _status(document, payload, expected, code):
        if document["version"] != payload["expected_version"]:
            raise BusinessError("VERSION_CONFLICT", 409)
        if document["status"] != expected:
            raise BusinessError(code, 409)

    def create_receipt(self, actor, key, payload):
        def create(w):
            header = document_input(payload)
            supplier = self._supplier(w, actor, payload["supplier_id"])
            order_id = payload.get("purchase_order_id")
            order = w.purchasing.document(actor, "purchase_orders", order_id) if order_id else None
            if order and (order["status"] != "open" or order["supplier_id"] != supplier["id"]):
                raise BusinessError("PURCHASE_ORDER_UNAVAILABLE", 409)
            order_lines = {line["id"]: line for line in order["lines"]} if order else {}
            seen = set()
            lines = []
            for source in payload["lines"]:
                purchase_line_id = source.get("purchase_line_id")
                if order:
                    if not purchase_line_id or purchase_line_id not in order_lines:
                        raise BusinessError("PURCHASE_LINE_NOT_FOUND", 404)
                    if purchase_line_id in seen:
                        raise BusinessError("PURCHASE_LINE_DUPLICATE", field="lines")
                    seen.add(purchase_line_id)
                    original = order_lines[purchase_line_id]
                    if (
                        source.get("material_id")
                        and source["material_id"] != original["material_id"]
                    ):
                        raise BusinessError("PURCHASE_LINE_MATERIAL_MISMATCH", 409)
                    material = w.catalog.require(actor, original["material_id"], kind="raw")
                    confirmed = quantity(source["quantity"], original["canonical_unit"])
                    if confirmed.value > Decimal(original["remaining_quantity"]):
                        raise BusinessError("PURCHASE_OVER_RECEIPT", 409)
                    line = {
                        k: original[k]
                        for k in (
                            "material_id",
                            "own_code",
                            "material_name",
                            "specification",
                            "canonical_unit",
                        )
                    }
                    line.update(id=str(uuid7()), quantity=confirmed.canonical)
                else:
                    if purchase_line_id or not source.get("material_id"):
                        raise BusinessError("INVALID_INPUT", field="lines")
                    material = w.catalog.require(actor, source["material_id"], kind="raw")
                    line = self._line(material, quantity(source["quantity"], material["unit"]))
                line["purchase_line_id"] = purchase_line_id
                lines.append(line)
            receipt = w.purchasing.insert_document(
                actor,
                "purchase_receipts",
                {
                    **header,
                    "supplier_id": supplier["id"],
                    "supplier_name": supplier["full_name"],
                    "purchase_order_id": order_id,
                },
                lines,
            )
            w.inventory.on_receive(actor, receipt, receipt["lines"])
            return receipt

        return self._command(actor, key, "purchase_receipt.create", payload, create)

    def void_receipt(self, actor, key, identifier, payload):
        def void(w):
            receipt = w.purchasing.document(actor, "purchase_receipts", identifier)
            self._status(receipt, payload, "active", "PURCHASE_RECEIPT_NOT_ACTIVE")
            reason = text_value(payload["reason"], "reason", required=True)
            receipt = w.purchasing.transition(actor, "purchase_receipts", identifier, reason)
            w.inventory.on_void(actor, receipt, receipt["lines"])
            return receipt

        return self._command(
            actor, key, "purchase_receipt.void", {"id": str(identifier), **payload}, void
        )
