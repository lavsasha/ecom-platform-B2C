from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any

from common.app import OptionalUser, RequiredUser
from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

import pages

router = APIRouter(prefix="/api/v1", tags=["actions"])

_upstream = None


def bind(upstreams: Any) -> None:
    global _upstream
    _upstream = upstreams


def _up() -> Any:
    assert _upstream is not None
    return _upstream


class CartItemIn(BaseModel):
    product_id: uuid.UUID
    offer_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    quantity: int = Field(default=1, ge=1, le=99)
    price_amount: Decimal
    title: str = ""
    image_url: str | None = None


class CartItemPatch(BaseModel):
    quantity: int | None = Field(default=None, ge=1, le=99)
    is_selected: bool | None = None


class CheckoutIn(BaseModel):
    delivery_method: str = "cdek"
    delivery_address: str | None = None
    recipient_name: str
    recipient_phone: str
    payment_method: str = "card"
    comment: str | None = None


class EventIn(BaseModel):
    type: str
    item_id: uuid.UUID | None = None
    page: str | None = None
    query: str | None = None
    value: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/cart/items")
async def add_cart_item(user: RequiredUser, body: CartItemIn) -> dict:
    cart = await _up().add_cart_item(user.id, body.model_dump(mode="json"))
    return {"cart": cart}


@router.patch("/cart/items/{item_id}")
async def patch_cart_item(
    user: RequiredUser, item_id: uuid.UUID, body: CartItemPatch
) -> dict:
    cart = await _up().patch_cart_item(
        user.id, item_id, body.model_dump(exclude_unset=True, mode="json")
    )
    return {"cart": cart}


@router.delete("/cart/items/{item_id}", status_code=204, response_class=Response)
async def delete_cart_item(user: RequiredUser, item_id: uuid.UUID) -> Response:
    await _up().delete_cart_item(user.id, item_id)
    return Response(status_code=204)


@router.put("/subscriptions/{seller_id}")
async def subscribe(user: RequiredUser, seller_id: uuid.UUID) -> dict:
    await _up().subscribe(user.id, seller_id)
    return await pages.subscriptions_page(user.id)


@router.delete("/subscriptions/{seller_id}", status_code=204, response_class=Response)
async def unsubscribe(user: RequiredUser, seller_id: uuid.UUID) -> Response:
    await _up().unsubscribe(user.id, seller_id)
    return Response(status_code=204)


@router.post("/checkout/order")
async def checkout_order(user: RequiredUser, body: CheckoutIn) -> dict:
    cart = await _up().get_cart(user.id)
    items = [i for i in cart.get("items") or [] if i.get("is_selected", True)]
    if not items:
        from common.app import BadRequestError

        raise BadRequestError("Cart is empty")
    order_payload = {
        "user_id": str(user.id),
        "items": [
            {
                "product_id": i["product_id"],
                "offer_id": i["offer_id"],
                "seller_id": i.get("seller_id"),
                "title": i.get("title", ""),
                "image_url": i.get("image_url"),
                "quantity": i["quantity"],
                "price_amount": i["price_amount"],
            }
            for i in items
        ],
        "delivery_method": body.delivery_method,
        "delivery_address": body.delivery_address,
        "recipient_name": body.recipient_name,
        "recipient_phone": body.recipient_phone,
        "payment_method": body.payment_method,
        "comment": body.comment,
    }
    order = await _up().create_order(order_payload)
    return {"order": order}


@router.post("/events", status_code=202)
async def track_event(user: OptionalUser, body: EventIn) -> dict:
    payload = {
        "type": body.type,
        "user_id": str(user.id) if user else None,
        "item_id": str(body.item_id) if body.item_id else None,
        "page": body.page,
        "query": body.query,
        "value": body.value,
        "context": body.context,
    }
    await _up().post_event(payload)
    return {"accepted": True}
