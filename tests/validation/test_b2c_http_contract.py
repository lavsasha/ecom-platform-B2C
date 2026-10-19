from __future__ import annotations

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

pytestmark = pytest.mark.validation

from tests.integration.b2c.conftest import BUYER_ID, MOCK_USER, app


@pytest.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.mark.asyncio
@respx.mock
async def test_contract_login_response_envelope(client: AsyncClient) -> None:
    respx.post("http://users:8000/api/v1/auth/login").mock(
        return_value=Response(200, json={"user": MOCK_USER})
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "buyer1@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "data" in body and "error" in body
    assert body["error"] is None
    assert body["data"]["user"]["email"] == "buyer1@example.com"


@pytest.mark.asyncio
async def test_contract_validation_error_envelope(client: AsyncClient) -> None:
    response = await client.post("/api/auth/login", json={"email": "not-an-email"})
    assert response.status_code == 400
    body = response.json()
    assert body["data"] is None
    assert body["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.asyncio
async def test_bff_events_validation_envelope(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/events",
        headers={"X-User-Id": str(BUYER_ID), "Content-Type": "application/json"},
        content=b"{broken",
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
