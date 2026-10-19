from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_cart_item_crud_and_promo(cart_client: AsyncClient) -> None:
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    offer_id = uuid.uuid4()

    add = await cart_client.post(
        f"/api/v1/carts/{user_id}/items",
        json={
            "product_id": str(product_id),
            "offer_id": str(offer_id),
            "quantity": 2,
            "price_amount": "100.50",
            "title": "Test item",
        },
    )
    assert add.status_code == 200
    cart = add.json()
    assert cart["totals"]["items_quantity"] == 2
    item_id = cart["items"][0]["id"]

    patch = await cart_client.patch(
        f"/api/v1/carts/{user_id}/items/{item_id}",
        json={"quantity": 1, "is_selected": True},
    )
    assert patch.status_code == 200
    assert patch.json()["items"][0]["quantity"] == 1

    promo = await cart_client.post(f"/api/v1/carts/{user_id}/promo", json={"code": "HANDMADE10"})
    assert promo.status_code == 200
    assert promo.json()["promo_code"] == "HANDMADE10"
    assert Decimal(promo.json()["totals"]["discount_amount"]) > 0

    delete = await cart_client.delete(f"/api/v1/carts/{user_id}/items/{item_id}")
    assert delete.status_code == 200
    assert delete.json()["items"] == []

    clear = await cart_client.post(f"/api/v1/carts/{user_id}/clear")
    assert clear.status_code == 200
    assert clear.json()["promo_code"] is None
