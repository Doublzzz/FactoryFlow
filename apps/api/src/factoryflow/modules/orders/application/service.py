"""Owns the single transaction for confirmation, revision and reversible soft deletion."""

from dataclasses import asdict, dataclass
from typing import Protocol
from uuid import UUID, uuid7

from factoryflow.kernel.contracts import Actor, BusinessError, CommandJournal
from factoryflow.modules.customers.public import CustomerAccess
from factoryflow.modules.documents.public import Documents
from factoryflow.modules.materials.public import MaterialCatalog, change_record
from factoryflow.modules.orders.domain.order import ConfirmedOrder, prepare_order, required_text


class OrderRepository(Protocol):
    def insert(
        self, actor: Actor, order_id: UUID, revision: dict, order: ConfirmedOrder
    ) -> None: ...
    def get(self, actor: Actor, order_id: UUID, lock: bool = False) -> dict: ...
    def lines(self, actor: Actor, revision_id: UUID) -> list[dict]: ...
    def replace_revision(
        self, actor: Actor, order_id: UUID, revision: dict, order: ConfirmedOrder
    ) -> None: ...
    def set_status(self, actor: Actor, order_id: UUID, status: str) -> None: ...
    def event(
        self,
        actor: Actor,
        order_id: UUID,
        action: str,
        version: int,
        revision_id: UUID,
        reason: str | None,
    ) -> None: ...
    def has_delivery(self, actor: Actor, revision_id: UUID) -> bool: ...
    def open_lines(
        self, actor: Actor, customer_id: UUID | None, cursor: str | None, limit: int, status: str
    ) -> dict: ...


@dataclass
class OrderWork:
    orders: OrderRepository
    customers: CustomerAccess
    documents: Documents
    journal: CommandJournal
    materials: MaterialCatalog | None = None


def evidence_content(order: ConfirmedOrder) -> dict:
    return {
        "order_number": order.order_number,
        "business_date": order.business_date.isoformat(),
        "currency": order.currency,
        "lines": [
            {
                "line_number": index,
                "description": line.description,
                "source_quantity_text": line.quantity.source_text,
                "canonical_quantity": line.quantity.canonical,
                "source_unit": line.quantity.source_unit,
                "quantity_policy": asdict(line.quantity.policy),
                "source_unit_price": line.source_unit_price,
                "source_amount": line.source_amount,
                **(
                    {
                        "item_code": line.item_code,
                        "item_name": line.item_name,
                        "specification": line.specification,
                    }
                    if any(
                        value is not None
                        for value in (line.item_code, line.item_name, line.specification)
                    )
                    else {}
                ),
            }
            for index, line in enumerate(order.lines, 1)
        ],
    }


class OrderService:
    def __init__(self, transaction):
        self.transaction = transaction

    def preview(self, actor: Actor, payload: dict) -> dict:
        actor.require_write()
        order = prepare_order(payload)
        with self.transaction() as work:
            customer = work.customers.require(actor, order.customer_id)
            return {
                "customer_id": str(order.customer_id),
                "customer_name": customer["full_name"],
                "order": evidence_content(order),
                "material_suggestions": work.materials.suggestions(
                    actor, order.customer_id, evidence_content(order)["lines"]
                )
                if work.materials
                else [],
            }

    def confirm(self, actor: Actor, key: UUID, payload: dict) -> dict:
        actor.require_write()
        order = prepare_order(payload)
        content = evidence_content(order)
        command_payload = {"customer_id": str(order.customer_id), **content}
        extraction_id = payload.get("extraction_id")
        if extraction_id:
            command_payload["extraction_id"] = str(extraction_id)
        if payload.get("material_choices"):
            command_payload["material_choices"] = payload["material_choices"]
        with self.transaction() as work:
            prior = work.journal.claim(actor, "order.confirm", key, command_payload)
            if prior is not None:
                return prior
            work.customers.require(actor, order.customer_id)
            selected = self.select_materials(work, actor, order.customer_id, content, payload)
            order_id = uuid7()
            revision = work.documents.confirm(
                actor,
                order_id,
                order.customer_id,
                content,
                extraction_id=UUID(str(extraction_id)) if extraction_id else None,
            )
            work.orders.insert(actor, order_id, revision, order)
            if selected:
                work.orders.set_material_choices(actor, UUID(revision["revision_id"]), selected)
            work.orders.event(actor, order_id, "confirm", 1, UUID(revision["revision_id"]), None)
            result = {"order_id": str(order_id), "version": 1, "status": "active", **revision}
            if selected:
                result["material_links"] = selected
            work.journal.audit(actor, "order.confirm", order_id)
            work.journal.finish(actor, "order.confirm", key, result)
            return result

    @staticmethod
    def require_version(current: dict, expected: int):
        if current["version"] != expected:
            raise BusinessError("VERSION_CONFLICT", 409)

    def revise(
        self, actor: Actor, key: UUID, order_id: UUID, expected: int, payload: dict, reason: str
    ) -> dict:
        actor.require_write()
        order = prepare_order(payload)
        reason = required_text(reason, "reason", 500)
        if payload.get("extraction_id"):
            raise BusinessError("REVISION_SOURCE_IMMUTABLE", 422)
        content = evidence_content(order)
        command_payload = {
            "order_id": str(order_id),
            "expected_version": expected,
            "customer_id": str(order.customer_id),
            "reason": reason,
            **content,
        }
        if payload.get("material_choices"):
            command_payload["material_choices"] = payload["material_choices"]
        with self.transaction() as work:
            prior = work.journal.claim(actor, "order.revise", key, command_payload)
            if prior is not None:
                return prior
            selected = self.select_materials(work, actor, order.customer_id, content, payload)
            current = work.orders.get(actor, order_id, lock=True)
            self.require_version(current, expected)
            if current["status"] != "active":
                raise BusinessError("ORDER_NOT_ACTIVE", 409)
            if order.currency != current["currency"]:
                raise BusinessError("ORDER_CURRENCY_IMMUTABLE", 409)
            if (
                str(order.customer_id) != current["customer_id"]
                or order.order_number != current["order_number"]
            ):
                raise BusinessError("ORDER_IDENTITY_IMMUTABLE", 409)
            if work.orders.has_delivery(actor, UUID(current["revision_id"])):
                raise BusinessError("ACTIVE_DELIVERY_BLOCKS_CHANGE", 409)
            previous = work.documents.read(actor, UUID(current["revision_id"]))
            revision = work.documents.confirm(
                actor,
                order_id,
                order.customer_id,
                content,
                UUID(current["revision_id"]),
                previous["content"]["revision_number"] + 1,
                inherited_source=previous["content"].get("source"),
            )
            work.orders.replace_revision(actor, order_id, revision, order)
            if selected:
                work.orders.set_material_choices(actor, UUID(revision["revision_id"]), selected)
            version = expected + 1
            work.orders.event(
                actor, order_id, "revise", version, UUID(revision["revision_id"]), reason
            )
            result = {"order_id": str(order_id), "version": version, "status": "active", **revision}
            if selected:
                result["material_links"] = selected
            work.journal.audit(actor, "order.revise", order_id)
            work.journal.finish(actor, "order.revise", key, result)
            return result

    def change_status(
        self, actor: Actor, key: UUID, order_id: UUID, expected: int, target: str, reason: str
    ) -> dict:
        actor.require_write()
        if target not in {"active", "deleted"}:
            raise BusinessError("INVALID_INPUT")
        reason = required_text(reason, "reason", 500)
        command = "order.restore" if target == "active" else "order.delete"
        payload = {"order_id": str(order_id), "expected_version": expected, "reason": reason}
        with self.transaction() as work:
            prior = work.journal.claim(actor, command, key, payload)
            if prior is not None:
                return prior
            current = work.orders.get(actor, order_id, lock=True)
            self.require_version(current, expected)
            if current["status"] == target:
                raise BusinessError("ORDER_STATE_CONFLICT", 409)
            if work.orders.has_delivery(actor, UUID(current["revision_id"])):
                raise BusinessError("ACTIVE_DELIVERY_BLOCKS_CHANGE", 409)
            work.orders.set_status(actor, order_id, target)
            work.orders.event(
                actor,
                order_id,
                command.split(".")[1],
                expected + 1,
                UUID(current["revision_id"]),
                reason,
            )
            result = {
                "order_id": str(order_id),
                "version": expected + 1,
                "status": target,
                "revision_id": current["revision_id"],
            }
            work.journal.audit(actor, command, order_id)
            work.journal.finish(actor, command, key, result)
            return result

    def detail(self, actor: Actor, order_id: UUID) -> dict:
        with self.transaction() as work:
            order = work.orders.get(actor, order_id)
            customer = work.customers.require(actor, UUID(order["customer_id"]))
            lines = (
                work.orders.material_lines(actor, UUID(order["revision_id"]))
                if work.materials
                else work.orders.lines(actor, UUID(order["revision_id"]))
            )
            if work.materials:
                materials = work.materials.summarize(
                    actor, [line["material_id"] for line in lines if line.get("material_id")]
                )
                lines = [
                    {**line, "material": materials.get(line.get("material_id"))} for line in lines
                ]
            return {
                **order,
                "customer_name": customer["full_name"],
                "lines": lines,
                "revisions": work.documents.history(actor, order_id),
            }

    @staticmethod
    def select_materials(work, actor, customer_id, content, payload):
        choices = payload.get("material_choices") or []
        if not choices:
            return []
        if len(choices) > len(content["lines"]) or len(
            {choice["line_number"] for choice in choices}
        ) != len(choices):
            raise BusinessError("INVALID_INPUT", field="material_choices")
        work.materials.lock(actor)
        selected = []
        for choice in choices:
            number = choice["line_number"]
            if not 1 <= number <= len(content["lines"]):
                raise BusinessError("INVALID_INPUT", field="material_choices")
            material = work.materials.choose(
                actor, customer_id, content["lines"][number - 1], choice
            )
            selected.append(
                {"line_number": number, "material_id": material["id"], "material": material}
            )
        return selected

    def material_links(self, actor, key, order_id, payload):
        actor.require_write()
        with self.transaction() as work:
            prior = work.journal.claim(
                actor, "order.material_links", key, {"order_id": str(order_id), **payload}
            )
            if prior is not None:
                return prior
            work.materials.lock(actor)
            current = work.orders.get(actor, order_id, lock=True)
            self.require_version(current, payload["expected_version"])
            if current["status"] != "active":
                raise BusinessError("ORDER_NOT_ACTIVE", 409)
            lines = {
                line["id"]: line
                for line in work.orders.material_lines(actor, UUID(current["revision_id"]))
            }
            choices = payload["lines"]
            if (
                not choices
                or len(choices) > 200
                or len({str(choice["line_id"]) for choice in choices}) != len(choices)
            ):
                raise BusinessError("INVALID_INPUT", field="lines")
            changes = []
            reason = payload.get("reason")
            for choice in choices:
                line = lines.get(str(choice["line_id"]))
                if line is None:
                    raise BusinessError("MATERIAL_LINE_NOT_CURRENT", 409)
                before = (
                    work.materials.require(actor, line["material_id"], active=False)
                    if line.get("material_id")
                    else None
                )
                identifier, data = choice.get("material_id"), choice.get("new_material")
                if identifier and data is not None:
                    raise BusinessError("INVALID_INPUT", field="material_id")
                if data is not None:
                    material = work.materials.create(actor, data)
                elif identifier:
                    if choice.get("expected_material_version") is None:
                        raise BusinessError("INVALID_INPUT", field="expected_material_version")
                    material = work.materials.require(
                        actor, identifier, choice["expected_material_version"]
                    )
                else:
                    material = None
                if before and (not material or before["id"] != material["id"]):
                    required_text(reason, "reason", 500)
                code_change = None
                if choice.get("remember_code"):
                    if material is None:
                        raise BusinessError("INVALID_INPUT", field="remember_code")
                    code_change = work.materials.remember(
                        actor,
                        current["customer_id"],
                        choice.get("customer_code"),
                        material,
                        line,
                        choice.get("expected_mapping_version", 0),
                        reason,
                    )
                work.orders.set_material(
                    actor, UUID(line["id"]), material["id"] if material else None
                )
                changes.append(
                    {
                        "line_id": line["id"],
                        **change_record(actor, before, material, reason),
                        "code_change": code_change,
                    }
                )
            version = current["version"] + 1
            work.orders.advance_version(actor, order_id)
            work.orders.event(
                actor, order_id, "material_links", version, UUID(current["revision_id"]), reason
            )
            result = {
                "order_id": str(order_id),
                "version": version,
                "status": current["status"],
                "revision_id": current["revision_id"],
                "changes": changes,
            }
            work.journal.audit(actor, "order.material_links", order_id)
            work.journal.finish(actor, "order.material_links", key, result)
            return result

    def open_lines(
        self,
        actor: Actor,
        customer_id: UUID | None = None,
        cursor: str | None = None,
        limit: int = 50,
        status: str = "active",
    ) -> dict:
        if not 1 <= limit <= 100 or status not in {"active", "deleted"}:
            raise BusinessError("INVALID_INPUT")
        with self.transaction() as work:
            if customer_id:
                work.customers.require(actor, customer_id)
            return work.orders.open_lines(actor, customer_id, cursor, limit, status)

    def evidence(self, actor: Actor, revision_id: UUID) -> dict:
        with self.transaction() as work:
            return work.documents.read(actor, revision_id)
