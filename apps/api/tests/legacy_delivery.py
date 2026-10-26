"""Frozen pre-inventory delivery fixture, used only inside disposable migration databases."""

from uuid import uuid4, uuid7

from factoryflow.modules.fulfillment.domain.delivery import prepare_delivery
from sqlalchemy import text


def create_legacy_delivery(runtime, actor, payload, key=None):
    request = prepare_delivery(payload)
    key = key or uuid4()
    with runtime.deliveries.transaction() as work:
        conn = work.deliveries.conn
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert int(revision[:4]) < 14, "Legacy fixture must never write the current schema"
        assert work.journal.claim(actor, "delivery.create", key, request.payload()) is None
        order = work.orders.lock(actor, request.order_id)
        assert order["version"] == request.expected_version
        sources = work.orders.repository.lines(actor, request.revision_id)
        lines = [
            {**line, "quantity": request.quantities[line["id"]]}
            for line in sources
            if line["id"] in request.quantities
        ]
        assert len(lines) == len(request.quantities)
        customer = work.customers.require(actor, request.customer_id)
        identifier = uuid7()
        work.deliveries.insert(actor, identifier, request, order, customer, lines)
        work.orders.apply(actor, order, request.quantities)
        work.deliveries.action(actor, identifier, "create", None, None)
        row = (
            conn.execute(
                text("SELECT * FROM deliveries WHERE organization_id=:org AND id=:id"),
                {"org": actor.organization_id, "id": identifier},
            )
            .mappings()
            .one()
        )
        result = {
            **work.deliveries.header(row),
            "lines": [
                {
                    "order_line_id": line["id"],
                    **{
                        name: line[name]
                        for name in (
                            "line_number",
                            "quantity",
                            "description",
                            "source_unit",
                            "canonical_unit",
                            "quantity_policy",
                        )
                    },
                }
                for line in sorted(lines, key=lambda item: item["line_number"])
            ],
        }
        work.journal.audit(actor, "delivery.create", identifier)
        work.journal.finish(actor, "delivery.create", key, result)
        return result
