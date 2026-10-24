"""Missing configuration must fail closed; transport cannot create an anonymous order."""

from test_http import request


def test_readiness_does_not_confuse_live_with_ready():
    response = request("GET", "/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["code"] == "NOT_CONFIGURED"


def test_orders_require_configured_local_identity():
    response = request("POST", "/api/v1/orders", json={})
    assert response.status_code == 503
    assert response.json()["code"] == "NOT_CONFIGURED"


def test_login_password_is_not_echoed_in_validation_errors():
    response = request("POST", "/api/v1/auth/login", json={"username": "synthetic"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "INVALID_INPUT"
    assert "input" not in str(body)
    assert body["request_id"]
