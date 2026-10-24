import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "architecture", ROOT / "scripts/check_architecture.py"
)
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)


def test_repository_import_boundaries():
    assert checker.check_tree() == []


@pytest.mark.parametrize(
    ("module", "code"),
    [
        ("factoryflow.modules.orders.domain.model", "from fastapi import FastAPI"),
        ("factoryflow.modules.orders.domain.model", "from ..adapters import repository"),
        ("factoryflow.modules.orders.application.command", "from ..adapters.sql import Repo"),
        (
            "factoryflow.modules.orders.application.command",
            "from factoryflow.modules.fulfillment.adapters.sql import Repo",
        ),
        (
            "factoryflow.modules.orders.application.command",
            "from factoryflow.modules.fulfillment import adapters",
        ),
        ("factoryflow.platform.database", "from factoryflow.modules.orders import public"),
        ("factoryflow.kernel.quantity", "from pydantic import BaseModel"),
    ],
)
def test_guard_rejects_forbidden_dependency(module, code):
    assert checker.violations(code, module)


def test_public_contract_and_domain_values_are_allowed():
    assert (
        checker.violations(
            "from factoryflow.modules.orders.public import OrderReader",
            "factoryflow.modules.fulfillment.application.create",
        )
        == []
    )
    assert (
        checker.violations(
            "from decimal import Decimal\n"
            "from factoryflow.kernel.quantity import ConfirmedQuantity",
            "factoryflow.modules.orders.domain.model",
        )
        == []
    )
