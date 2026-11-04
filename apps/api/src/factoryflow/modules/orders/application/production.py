"""Order-owned source access, without changing the existing order lifecycle."""

from factoryflow.kernel.contracts import BusinessError


class ProductionOrders:
    def __init__(self, repository):
        self.repository = repository

    def source(self, actor, request):
        order = self.repository.get(actor, request["order_id"], lock=True)
        if order["version"] != request["expected_order_version"]:
            raise BusinessError("VERSION_CONFLICT", 409)
        if order["status"] != "active":
            raise BusinessError("ORDER_NOT_ACTIVE", 409)
        if order["revision_id"] != request["revision_id"]:
            raise BusinessError("PRODUCTION_SOURCE_CHANGED", 409)
        line = next(
            (
                line
                for line in self.repository.material_lines(actor, order["revision_id"])
                if line["id"] == request["order_line_id"]
            ),
            None,
        )
        if line is None:
            raise BusinessError("PRODUCTION_SOURCE_CHANGED", 409)
        if line["material_id"] is None:
            raise BusinessError("PRODUCTION_MATERIAL_REQUIRED", 409)
        return order, line

    def current(self, actor, production, *, lock=False):
        order = self.repository.get(actor, production["order_id"], lock=lock)
        if order["status"] != "active" or order["revision_id"] != production["source_revision_id"]:
            return False
        return any(
            line["id"] == production["order_line_id"]
            and line["material_id"] == production["material_id"]
            and line["canonical_unit"] == production["canonical_unit"]
            for line in self.repository.material_lines(actor, order["revision_id"])
        )
