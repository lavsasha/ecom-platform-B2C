from __future__ import annotations

import pytest
import respx
from httpx import AsyncClient, Response

from tests.integration.b2c.conftest import BUYER_HEADER, BUYER_ID

pytestmark = [pytest.mark.integration, pytest.mark.b2c]


@pytest.mark.asyncio
@respx.mock
async def test_home_page_sections(client: AsyncClient) -> None:
    respx.get("http://publications:8000/api/v1/posts").mock(
        return_value=Response(200, json={"items": [], "next_cursor": None, "has_more": False})
    )
    respx.get("http://goods:8000/api/v1/categories").mock(
        return_value=Response(200, json={"items": []})
    )
    respx.get("http://users:8000/api/v1/sellers/popular").mock(
        return_value=Response(200, json={"items": []})
    )
    response = await client.get("/api/v1/pages/home")
    assert response.status_code == 200
    body = response.json()
    assert "recommendations" in body
    assert body["recommendations"]["status"] in ("ok", "empty", "unavailable")


@pytest.mark.asyncio
@respx.mock
async def test_events_forwarded_to_eventer(client: AsyncClient) -> None:
    route = respx.post("http://eventer:8000/api/v1/events").mock(
        return_value=Response(202, json={"accepted": 1, "forwarded_to_gorse": 0})
    )
    response = await client.post(
        "/api/v1/events",
        headers=BUYER_HEADER,
        json={
            "type": "view",
            "item_id": "b1000001-0000-4000-8000-000000000001",
            "page": "product",
        },
    )
    assert response.status_code == 202
    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_cart_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/cart/items",
        json={
            "product_id": "b1000001-0000-4000-8000-000000000001",
            "offer_id": "f1000001-0000-4000-8000-000000000001",
            "quantity": 1,
            "price_amount": "890.00",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_comments_list(client: AsyncClient) -> None:
    post_id = "e2000001-0000-4000-8000-000000000001"
    respx.get(f"http://publications:8000/api/v1/posts/{post_id}/comments").mock(
        return_value=Response(
            200,
            json={
                "items": [
                    {
                        "id": "e3000001-0000-4000-8000-000000000001",
                        "post_id": post_id,
                        "user_id": str(BUYER_ID),
                        "body": "Hi",
                        "created_at": "2026-01-01T12:00:00Z",
                        "updated_at": "2026-01-01T12:00:00Z",
                    }
                ],
                "next_cursor": None,
                "has_more": False,
            },
        )
    )
    respx.post("http://users:8000/api/v1/users/batch").mock(
        return_value=Response(200, json={"items": []})
    )
    response = await client.get(f"/api/posts/{post_id}/comments")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["body"] == "Hi"


@pytest.mark.asyncio
async def test_healthz(client: AsyncClient) -> None:
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json().get("service") == "b2c"
