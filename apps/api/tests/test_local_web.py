"""Synthetic, in-process tests. No browser, server, network, or real data."""

import asyncio

import httpx
import pytest
from factoryflow.bootstrap import create_app


def request(application, path):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            return await client.get(path)

    return asyncio.run(send())


@pytest.fixture
def local_app(tmp_path):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>Synthetic local Web</h1>", encoding="utf-8")
    (web / "asset.js").write_text("/* synthetic asset */", encoding="utf-8")
    (tmp_path / "outside.txt").write_text("synthetic private sentinel", encoding="utf-8")
    return create_app(web_directory=web)


def test_serves_local_assets_and_api_on_same_origin(local_app):
    assert "Synthetic local Web" in request(local_app, "/").text
    assert "synthetic asset" in request(local_app, "/asset.js").text
    assert request(local_app, "/api/v1/health/live").json()["status"] == "ok"
    assert request(local_app, "/api/v1/openapi.json").json() == create_app().openapi()


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/api/v1/missing", "/%2e%2e/outside.txt"])
def test_no_cdn_docs_spa_fallback_or_files_outside_build(local_app, path):
    response = request(local_app, path)
    assert response.status_code == 404
    assert "synthetic private sentinel" not in response.text


def test_missing_build_fails_before_startup(tmp_path):
    with pytest.raises(ValueError, match="Web build missing"):
        create_app(web_directory=tmp_path)
