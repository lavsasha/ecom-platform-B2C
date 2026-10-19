from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from tests.support.paths import configure_service_env, service_import

configure_service_env("b2c")

with service_import("b2c"):
    from main import app

BUYER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
BUYER_HEADER = {"X-User-Id": str(BUYER_ID)}

MOCK_USER = {
    "id": str(BUYER_ID),
    "username": "anna_buyer",
    "displayName": "Анна Покупатель",
    "avatar": "",
    "email": "buyer1@example.com",
    "roles": ["buyer"],
    "bio": None,
    "createdAt": "2026-01-01T00:00:00Z",
}


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
