from dataclasses import dataclass
from datetime import date
from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import confirm_quantity


@dataclass(frozen=True)
class DeliveryInput:
    order_id: UUID
    customer_id: UUID
    revision_id: UUID
    expected_version: int
    delivery_date: date
    quantities: dict[str, str]
    inventory_mode: str = "sync"
    confirm_inventory_shortage: bool = False

    def payload(self):
        result = {
            "order_id": str(self.order_id),
            "customer_id": str(self.customer_id),
            "revision_id": str(self.revision_id),
            "expected_version": self.expected_version,
            "delivery_date": self.delivery_date.isoformat(),
            "quantities": self.quantities,
        }
        # Default values preserve pre-inventory command fingerprints and successful replays.
        if self.inventory_mode != "sync":
            result["inventory_mode"] = self.inventory_mode
        if self.confirm_inventory_shortage:
            result["confirm_inventory_shortage"] = True
        return result


def prepare_delivery(payload):
    try:
        day = payload["delivery_date"]
        if not isinstance(day, str) or len(day) != 10:
            raise ValueError
        business_date = date.fromisoformat(day)
        if business_date.isoformat() != day:
            raise ValueError
        expected = payload["expected_version"]
        if type(expected) is not int or expected < 1:
            raise ValueError
        lines = payload["lines"]
        if not isinstance(lines, list) or not 1 <= len(lines) <= 200:
            raise ValueError
        quantities = {}
        mode = payload.get("inventory_mode", "sync")
        shortage = payload.get("confirm_inventory_shortage", False)
        if mode not in {"sync", "skip"} or type(shortage) is not bool:
            raise ValueError
        for line in lines:
            identifier = str(UUID(str(line["order_line_id"])))
            quantity = confirm_quantity(line["quantity"], None)
            if quantity.value <= 0 or identifier in quantities:
                raise BusinessError("DELIVERY_INVALID_LINES", field="lines")
            quantities[identifier] = quantity.canonical
        return DeliveryInput(
            UUID(str(payload["order_id"])),
            UUID(str(payload["customer_id"])),
            UUID(str(payload["revision_id"])),
            expected,
            business_date,
            dict(sorted(quantities.items())),
            mode,
            shortage,
        )
    except (KeyError, TypeError, ValueError) as error:
        # QuantityError keeps its stable code at the API boundary.
        if hasattr(error, "code"):
            raise
        raise BusinessError("INVALID_INPUT") from None


def void_reason(reason):
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 500:
        raise BusinessError("INVALID_INPUT", field="reason")
    return reason.strip()
