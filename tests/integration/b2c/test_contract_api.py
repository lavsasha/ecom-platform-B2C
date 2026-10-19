from __future__ import annotations

import pytest
import respx
from httpx import AsyncClient, Response

from tests.integration.b2c.conftest import MOCK_USER

pytestmark = [pytest.mark.integration, pytest.mark.b2c]


@pytest.mark.asyncio
@respx.mock
async def test_plans_static(client: AsyncClient) -> None:
    response = await client.get("/api/plans")
    assert response.status_code == 200
    body = response.json()
    assert body["error"] is None
    assert len(body["data"]) >= 2


@pytest.mark.asyncio
@respx.mock
async def test_login_sets_auth_cookie(client: AsyncClient) -> None:
    respx.post("http://users:8000/api/v1/auth/login").mock(
        return_value=Response(200, json={"user": MOCK_USER})
    )
    response = await client.post(
        "/api/auth/login",
        json={"email": "buyer1@example.com", "password": "secret123"},
    )
    assert response.status_code == 200
    assert "auth-token" in response.cookies


@pytest.mark.asyncio
@respx.mock
async def test_products_list_hydrates_seller(client: AsyncClient) -> None:
    seller_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"
    respx.get("http://goods:8000/api/v1/goods").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "b1000001-0000-4000-8000-000000000001",
                        "title": "Кружка",
                        "seller_id": seller_id,
                        "images": [{"url": "https://example/img.jpg"}],
                        "offers": [
                            {
                                "id": "f1000001-0000-4000-8000-000000000001",
                                "price_amount": "890.00",
                                "stock": 5,
                                "is_default": True,
                            }
                        ],
                        "sale_mode": "online",
                        "available_deliveries": ["pickup", "cdek"],
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ],
                "total": 1,
            },
        )
    )
    respx.post("http://users:8000/api/v1/sellers/batch").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": seller_id,
                        "username": "maria-clay",
                        "display_name": "Мария",
                        "followers_count": 1,
                        "rating": 4.8,
                        "products_count": 1,
                        "posts_count": 0,
                        "created_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
        )
    )
    response = await client.get("/api/products?pageSize=5")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["seller"]["username"] == "maria-clay"
