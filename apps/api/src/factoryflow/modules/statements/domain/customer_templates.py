"""Business coverage required before a saved statement uses a customer layout."""

from factoryflow.kernel.contracts import BusinessError

CUSTOM_TEMPLATE = "customer-v1"
DETAIL_FIELDS = {
    "ordinal",
    "delivery_date",
    "item_code",
    "item_name",
    "item_name_specification",
    "order_number",
    "delivery_reference",
    "external_document_number",
    "specification",
    "unit",
    "quantity",
    "unit_price",
    "amount",
    "reason",
}
CELL_FIELDS = {
    "customer_name",
    "period",
    "status",
    "priced_subtotal",
    "tax_base",
    "tax_amount",
    "total",
    "total_label",
    "adjustments",
}
REQUIRED_COLUMNS = {"unit", "quantity", "unit_price", "amount"}
REQUIRED_CELLS = {"customer_name", "period", "total"}
MAX_DETAILS = 1000


def require_coverage(mapping, statement):
    cells = set(mapping["cells"])
    needed = set()
    if statement["tax_mode"] == "add_tax":
        needed.add("priced_subtotal")
    if statement["adjustments"]:
        needed |= {"adjustments", "priced_subtotal"}
    if not needed <= cells:
        raise BusinessError("STATEMENT_TEMPLATE_COVERAGE", 409, ",".join(sorted(needed - cells)))
    lines = statement["lines"] + statement.get("settlement_lines", [])
    for line in lines:
        if line["status"] != "included":
            continue
        if (
            "external_document_number" in mapping["columns"]
            and not line.get("external_document_number", "").strip()
        ):
            raise BusinessError("STATEMENT_TEMPLATE_COVERAGE", 409, "external_document_number")
        for field in {"order_number", "delivery_reference"} & mapping["columns"].keys():
            value = (
                line["source"].get("order_number")
                if field == "order_number"
                else line["source"].get("delivery_id") or line.get("delivery_id")
            )
            if not value:
                raise BusinessError("STATEMENT_TEMPLATE_COVERAGE", 409, field)
    if sum(line["status"] == "included" for line in lines) > MAX_DETAILS:
        raise BusinessError("STATEMENT_TEMPLATE_OUTPUT_LIMIT", 409)
    if len(statement["calculation"]["line_amounts"]) != len(lines):
        raise BusinessError("STATEMENT_EXPORT_REVIEW_REQUIRED", 409)
