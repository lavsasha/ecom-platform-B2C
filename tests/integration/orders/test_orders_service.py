from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_create_list_and_change_status(orders_client: AsyncClient) -> None:
    user_id = uuid.uuid4()
    product_id = uuid.uuid4()
    offer_id = uuid.uuid4()

    create = await orders_client.post(
        "/api/v1/orders",
        json={
            "user_id": str(user_id),
            "items": [
                {
                    "product_id": str(product_id),
                    "offer_id": str(offer_id),
                    "quantity": 1,
                    "price_amount": "500.00",
                    "title": "Order item",
                }
            ],
            "delivery_method": "pickup",
            "recipient_name": "Test",
            "recipient_phone": "+79000000000",
        },
        headers={"Idempotency-Key": f"test-{uuid.uuid4()}"},
    )
    assert create.status_code == 201
    order = create.json()
    order_id = order["id"]
    assert order["status"] == "created"
    assert order["total_amount"] is not None

    listing = await orders_client.get("/api/v1/orders", params={"user_id": str(user_id)})
    assert listing.status_code == 200
    assert listing.json()["total"] >= 1

    paid = await orders_client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": "paid", "comment": "test payment"},
    )
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"
    assert paid.json()["paid_at"] is not None

    delivery = await orders_client.get("/api/v1/delivery-options")
    assert delivery.status_code == 200
    methods = {item["method"] for item in delivery.json()}
    assert "pickup" in methods
    assert "cdek" in methods
