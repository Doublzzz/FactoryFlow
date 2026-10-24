"""Disposable databases only; never connect tests to a business database."""

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import psycopg
import pytest
from factoryflow.bootstrap import build_services, create_app
from factoryflow.platform.config import Settings
from factoryflow.platform.database import engine_for
from factoryflow.platform.migrations import upgrade_database
from psycopg import sql
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
SYNTHETIC_PASSWORD = "Synthetic-Test-Password-Only-42"


class API:
    def __init__(self, app):
        self.app = app
        self.cookies = httpx.Cookies()
        self.csrf = None

    def request(self, method, path, **kwargs):
        headers = kwargs.pop("headers", {})
        if self.csrf and "x-csrf-token" not in headers:
            headers["x-csrf-token"] = self.csrf

        async def send():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=self.app),
                base_url="http://test",
                cookies=self.cookies,
            ) as client:
                response = await client.request(method, path, headers=headers, **kwargs)
                self.cookies = client.cookies
                return response

        return asyncio.run(send())

    def login(self, username="synthetic-admin", password=SYNTHETIC_PASSWORD):
        response = self.request(
            "POST", "/api/v1/auth/login", json={"username": username, "password": password}
        )
        assert response.status_code == 200, response.text
        self.csrf = response.json()["csrf_token"]
        return response

    def command(self, path, body, key=None):
        return self.request(
            "POST", path, json=body, headers={"Idempotency-Key": str(key or uuid4())}
        )


@pytest.fixture
def pg(tmp_path):
    config_path = os.environ.get("FACTORYFLOW_TEST_ADMIN_CONFIG")
    if not config_path:
        pytest.skip("Set FACTORYFLOW_TEST_ADMIN_CONFIG for disposable real PostgreSQL tests")
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    admin_url = make_url(config["admin_url"])
    if admin_url.host != "127.0.0.1" or admin_url.database != "postgres":
        pytest.fail("Test harness accepts only an explicit loopback cluster admin config")
    database = "ff_test_" + uuid4().hex
    with psycopg.connect(config["admin_url"], autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {} OWNER ff_admin").format(sql.Identifier(database)))
    owner_url = admin_url.set(drivername="postgresql+psycopg", database=database)
    owner = engine_for(owner_url.render_as_string(hide_password=False))
    runtime = None
    application = None
    try:
        upgrade_database(owner, ROOT)
        objects = tmp_path / "objects"
        objects.mkdir()
        app_url = owner_url.set(username="ff_runtime", password=config["runtime_password"])
        settings = Settings(app_url.render_as_string(hide_password=False), objects)
        runtime = build_services(settings)
        actor = runtime.identity.provision_factory(
            "Synthetic Factory", "synthetic-admin", SYNTHETIC_PASSWORD
        )
        application = create_app(settings=settings)
        api = API(application)
        api.login()
        customer = api.command("/api/v1/customers", {"full_name": "Synthetic Customer"})
        assert customer.status_code == 200, customer.text
        yield SimpleNamespace(
            owner=owner,
            runtime=runtime,
            actor=actor,
            app=application,
            api=api,
            customer_id=customer.json()["id"],
            settings=settings,
            objects=objects,
            database=database,
            admin_url=owner_url,
        )
    finally:
        if application is not None:
            application.state.services.close()
        if runtime is not None:
            runtime.close()
        owner.dispose()
        # Drop only this fixture's randomly named database, never a pre-existing one.
        assert database.startswith("ff_test_") and len(database) == 40
        with psycopg.connect(config["admin_url"], autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
