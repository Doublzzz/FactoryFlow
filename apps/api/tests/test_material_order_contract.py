"""M1 stays optional and outside immutable order evidence."""

from factoryflow.bootstrap import create_app


def test_catalog_and_late_link_contract_exist_without_startup_io():
    schema = create_app().openapi()
    for path in ("/api/v1/materials", "/api/v1/orders/{order_id}/material-links"):
        assert path in schema["paths"], f"M1 command is missing: {path}"
    models = schema["components"]["schemas"]
    assert "material_choices" in models["OrderInput"]["properties"]
    assert "material_choices" not in models["OrderInput"].get("required", [])
    assert "material_id" in models["OrderLineResponse"]["properties"]
    assert "material_id" not in models["EvidenceLine"]["properties"]
