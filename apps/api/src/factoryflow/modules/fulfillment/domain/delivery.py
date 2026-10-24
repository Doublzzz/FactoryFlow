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

    def payload(self):
        return {
            "order_id": str(self.order_id),
            "customer_id": str(self.customer_id),
            "revision_id": str(self.revision_id),
            "expected_version": self.expected_version,
            "delivery_date": self.delivery_date.isoformat(),
            "quantities": self.quantities,
        }


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
