"""Read current confirmed classification without delivery-driven order versions."""

from uuid import UUID

from factoryflow.kernel.contracts import BusinessError
from factoryflow.modules.customers.public import CustomerAccess


class ArchiveOrders:
    def __init__(self, repository, customers: CustomerAccess):
        self.repository, self.customers = repository, customers

    def describe(self, actor, key: str) -> dict:
        try:
            identifier = UUID(str(key))
        except ValueError:
            raise BusinessError("INVALID_INPUT", field="key") from None
        row = self.repository.get(actor, identifier)
        customer = self.customers.require(actor, UUID(row["customer_id"]))
        return {
            "source_id": str(row["id"]),
            "customer_id": row["customer_id"],
            "customer_name": customer["full_name"],
            "business_date": row["business_date"],
            "revision_id": row["revision_id"],
            "version_label": f"确认版本 {row['revision_id']}",
            "state_label": "有效" if row["status"] == "active" else "已删除",
            "status": row["status"],
            "order_number": row["order_number"],
        }
