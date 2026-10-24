from uuid import uuid4

import pytest
from factoryflow.kernel.contracts import BusinessError
from factoryflow.kernel.quantity import QuantityError
from factoryflow.modules.fulfillment.domain.delivery import prepare_delivery


def body():
    return {
        "order_id": str(uuid4()),
        "customer_id": str(uuid4()),
        "revision_id": str(uuid4()),
        "expected_version": 1,
        "delivery_date": "2026-10-01",
        "lines": [
            {"order_line_id": str(uuid4()), "quantity": "1.000"},
            {"order_line_id": str(uuid4()), "quantity": "0.125"},
        ],
    }


def test_command_payload_canonicalizes_quantities_and_source_ordering():
    payload = body()
    first = prepare_delivery(payload).payload()
    payload["lines"][0]["quantity"] = "1"
    payload["lines"].reverse()
    assert prepare_delivery(payload).payload() == first


@pytest.mark.parametrize("value", ["0", "-1", "1.0000", 1.5, "1e0", "Infinity"])
def test_domain_rejects_bad_quantity_before_transaction(value):
    payload = body()
    payload["lines"][0]["quantity"] = value
    with pytest.raises((BusinessError, QuantityError)):
        prepare_delivery(payload)


@pytest.mark.parametrize(
    "field,value",
    [
        ("delivery_date", "2026-02-30"),
        ("delivery_date", "2026-W01-1"),
        ("expected_version", True),
        ("expected_version", 0),
    ],
)
def test_domain_rejects_bad_command_metadata(field, value):
    payload = body()
    payload[field] = value
    with pytest.raises(BusinessError):
        prepare_delivery(payload)
