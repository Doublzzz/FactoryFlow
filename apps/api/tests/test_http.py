import asyncio

import httpx
from factoryflow.bootstrap import create_app


def request(method, path, **kwargs):
    async def send():
        transport = httpx.ASGITransport(app=create_app())
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_liveness_is_explicit_about_no_business_storage():
    response = request("GET", "/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "FactoryFlow", "version": "0.1.0"}


def test_openapi_is_versioned_and_has_stable_operation_id():
    schema = create_app().openapi()
    assert schema["openapi"].startswith("3.1.")
    operation = schema["paths"]["/api/v1/health/live"]["get"]
    assert operation["operationId"] == "getLiveness"
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/Liveness"
    }


def test_business_contract_declares_cookie_authentication():
    operation = create_app().openapi()["paths"]["/api/v1/orders"]["post"]
    assert operation["security"] == [{"APIKeyCookie": []}]
    assert request("POST", "/api/v1/orders", json={}).status_code == 503


def test_unknown_route_has_no_write_fallback():
    response = request("POST", "/api/v1/unknown-command", json={})
    assert response.status_code == 404
