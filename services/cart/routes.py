from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.app import BadRequestError, NotFoundError
from common.db import Database
from models import Cart, CartItem

router = APIRouter(prefix="/api/v1")
_db: Database | None = None

PROMO_CODES: dict[str, Decimal] = {
    "HANDMADE10": Decimal("0.10"),
    "WELCOME500": Decimal("0.05"),
}
MAX_ITEM_QUANTITY = 99
TWO_PLACES = Decimal("0.01")


def bind_db(database: Database) -> None:
    global _db
    _db = database


async def get_session() -> AsyncIterator[AsyncSession]:
    assert _db is not None
    async for session in _db.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


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


class CartItemOut(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    offer_id: uuid.UUID
    seller_id: uuid.UUID | None
    quantity: int
    price_amount: Decimal
    title: str
    image_url: str | None
    is_selected: bool


class CartTotals(BaseModel):
    items_count: int
    items_quantity: int
    items_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    currency: str


class CartOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    currency: str
    promo_code: str | None
    items: list[CartItemOut]
    totals: CartTotals


class PromoIn(BaseModel):
    code: str | None = Field(default=None, max_length=64)


async def _get_or_create(session: AsyncSession, user_id: uuid.UUID) -> Cart:
    result = await session.scalars(select(Cart).where(Cart.user_id == user_id))
    cart = result.first()
    if cart is None:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
        await session.refresh(cart)
    return cart


async def _reload(session: AsyncSession, cart_id: uuid.UUID) -> Cart:
    await session.flush()
    session.expire_all()
    cart = await session.get(Cart, cart_id)
    if cart is None:
        raise NotFoundError(f"Cart {cart_id} not found")
    return cart


def _totals(cart: Cart) -> CartTotals:
    selected = [item for item in cart.items if item.is_selected]
    items_amount = sum(
        (item.price_amount * item.quantity for item in selected),
        Decimal("0"),
    )
    discount_rate = PROMO_CODES.get(cart.promo_code or "", Decimal("0"))
    discount_amount = (items_amount * discount_rate).quantize(TWO_PLACES)
    return CartTotals(
        items_count=len(cart.items),
        items_quantity=sum(item.quantity for item in selected),
        items_amount=items_amount.quantize(TWO_PLACES),
        discount_amount=discount_amount,
        total_amount=(items_amount - discount_amount).quantize(TWO_PLACES),
        currency=cart.currency,
    )


def _to_out(cart: Cart) -> CartOut:
    return CartOut(
        id=cart.id,
        user_id=cart.user_id,
        currency=cart.currency,
        promo_code=cart.promo_code,
        items=[CartItemOut.model_validate(item) for item in cart.items],
        totals=_totals(cart),
    )


@router.get("/carts/{user_id}", response_model=CartOut, tags=["cart"])
async def get_cart(user_id: uuid.UUID, session: SessionDep) -> CartOut:
    return _to_out(await _get_or_create(session, user_id))


@router.post("/carts/{user_id}/items", response_model=CartOut, tags=["cart"])
async def add_item(user_id: uuid.UUID, payload: CartItemIn, session: SessionDep) -> CartOut:
    cart = await _get_or_create(session, user_id)
    existing = next((item for item in cart.items if item.offer_id == payload.offer_id), None)
    if existing is not None:
        existing.quantity = min(existing.quantity + payload.quantity, MAX_ITEM_QUANTITY)
        existing.price_amount = payload.price_amount
    else:
        session.add(CartItem(cart_id=cart.id, **payload.model_dump()))
    await session.flush()
    return _to_out(await _reload(session, cart.id))


@router.patch("/carts/{user_id}/items/{item_id}", response_model=CartOut, tags=["cart"])
async def update_item(
    user_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: CartItemPatch,
    session: SessionDep,
) -> CartOut:
    cart = await _get_or_create(session, user_id)
    item = next((candidate for candidate in cart.items if candidate.id == item_id), None)
    if item is None:
        raise NotFoundError(f"Cart item {item_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.flush()
    return _to_out(await _reload(session, cart.id))


@router.delete("/carts/{user_id}/items/{item_id}", response_model=CartOut, tags=["cart"])
async def remove_item(user_id: uuid.UUID, item_id: uuid.UUID, session: SessionDep) -> CartOut:
    cart = await _get_or_create(session, user_id)
    item = next((candidate for candidate in cart.items if candidate.id == item_id), None)
    if item is None:
        raise NotFoundError(f"Cart item {item_id} not found")
    await session.delete(item)
    await session.flush()
    return _to_out(await _reload(session, cart.id))


@router.post("/carts/{user_id}/promo", response_model=CartOut, tags=["cart"])
async def apply_promo(user_id: uuid.UUID, payload: PromoIn, session: SessionDep) -> CartOut:
    cart = await _get_or_create(session, user_id)
    code = payload.code
    if code and code.upper() not in PROMO_CODES:
        raise BadRequestError(f"Promo code {code} is not valid", code="invalid_promo_code")
    cart.promo_code = code.upper() if code else None
    await session.flush()
    return _to_out(await _reload(session, cart.id))


@router.post(
    "/carts/{user_id}/clear",
    response_model=CartOut,
    summary="Empty the cart",
    description="Called by the b2c module after an order has been created from the cart.",
    tags=["cart"],
)
async def clear_cart(user_id: uuid.UUID, session: SessionDep) -> CartOut:
    cart = await _get_or_create(session, user_id)
    for item in list(cart.items):
        await session.delete(item)
    cart.promo_code = None
    await session.flush()
    return _to_out(await _reload(session, cart.id))
