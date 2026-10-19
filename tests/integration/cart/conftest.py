from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from common.db import init_tables
from tests.support.service_loader import load_service_module

_cart, _cart_models, _ = load_service_module("cart")
app = _cart.app
db = _cart.db


@pytest.fixture(autouse=True)
async def _init_schema() -> None:
    await init_tables(db.engine, _cart_models.Base.metadata)


@pytest.fixture
async def cart_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as http:
        yield http


@pytest.fixture(autouse=True)
def _require_postgres(require_postgres: None) -> None:
    return None
