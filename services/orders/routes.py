from __future__ import annotations

import random
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.app import ConflictError, NotFoundError
from common.db import Database
from common.kafka import EventProducer, Topics
from models import (
    STATUS_TRANSITIONS,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
)

router = APIRouter(prefix="/api/v1")
_db: Database | None = None
_producer: EventProducer | None = None
_order_number_prefix = "HM"
TWO_PLACES = Decimal("0.01")


class DeliveryOption(BaseModel):
    method: DeliveryMethod
    title: str
    description: str
    price_amount: Decimal
    eta_days: int
    currency: str = "RUB"


DELIVERY_OPTIONS: dict[DeliveryMethod, DeliveryOption] = {
    DeliveryMethod.CDEK: DeliveryOption(
        method=DeliveryMethod.CDEK,
        title="СДЭК",
        description="Доставка СДЭК",
        price_amount=Decimal("390.00"),
        eta_days=4,
    ),
    DeliveryMethod.PICKUP: DeliveryOption(
        method=DeliveryMethod.PICKUP,
        title="Самовывоз",
        description="Из пункта выдачи рядом с вами",
        price_amount=Decimal("0.00"),
        eta_days=2,
    ),
    DeliveryMethod.COURIER: DeliveryOption(
        method=DeliveryMethod.COURIER,
        title="Курьер",
        description="Доставка до двери",
        price_amount=Decimal("390.00"),
        eta_days=3,
    ),
    DeliveryMethod.POST: DeliveryOption(
        method=DeliveryMethod.POST,
        title="Почта",
        description="Доставка в отделение",
        price_amount=Decimal("250.00"),
        eta_days=7,
    ),
}


def bind_db(database: Database) -> None:
    global _db
    _db = database


def bind_producer(producer: EventProducer) -> None:
    global _producer
    _producer = producer


def configure(*, order_number_prefix: str = "HM") -> None:
    global _order_number_prefix
    _order_number_prefix = order_number_prefix


async def get_session() -> AsyncIterator[AsyncSession]:
    assert _db is not None
    async for session in _db.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    offer_id: uuid.UUID
    seller_id: uuid.UUID | None = None
    title: str = ""
    image_url: str | None = None
    quantity: int = Field(default=1, ge=1)
    price_amount: Decimal


class OrderCreate(BaseModel):
    user_id: uuid.UUID
    items: list[OrderItemIn] = Field(min_length=1)
    delivery_method: DeliveryMethod = DeliveryMethod.COURIER
    delivery_address: str | None = None
    recipient_name: str
    recipient_phone: str
    payment_method: str = "card"
    comment: str | None = None
    discount_amount: Decimal = Decimal("0")
    currency: str = "RUB"


class OrderItemOut(ORMModel):
    id: uuid.UUID
    product_id: uuid.UUID
    offer_id: uuid.UUID
    seller_id: uuid.UUID | None
    title: str
    image_url: str | None
    quantity: int
    price_amount: Decimal


class OrderStatusHistoryOut(ORMModel):
    status: OrderStatus
    comment: str | None
    created_at: datetime


class OrderOut(ORMModel):
    id: uuid.UUID
    number: str
    user_id: uuid.UUID
    status: OrderStatus
    currency: str
    items_amount: Decimal
    delivery_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    delivery_method: DeliveryMethod
    delivery_address: str | None
    delivery_eta_days: int | None
    recipient_name: str
    recipient_phone: str
    payment_method: str
    comment: str | None
    paid_at: datetime | None
    created_at: datetime
    items: list[OrderItemOut] = Field(default_factory=list)
    history: list[OrderStatusHistoryOut] = Field(default_factory=list)


class OrderListOut(BaseModel):
    items: list[OrderOut]
    total: int


class OrderStatusPatch(BaseModel):
    status: OrderStatus
    comment: str | None = None


async def _get_by_idempotency_key(session: AsyncSession, key: str) -> Order | None:
    result = await session.scalars(select(Order).where(Order.idempotency_key == key))
    return result.first()


async def _next_number() -> str:
    today = datetime.now(UTC).strftime("%y%m%d")
    suffix = f"{random.randint(0, 999999):06d}"  # noqa: S311
    return f"{_order_number_prefix}-{today}-{suffix}"


async def _publish(order: Order) -> None:
    if _producer is None:
        return
    await _producer.send(
        Topics.ORDERS_CHANGED,
        {
            "order_id": str(order.id),
            "number": order.number,
            "user_id": str(order.user_id),
            "status": order.status.value,
            "total_amount": str(order.total_amount),
            "items": [
                {"product_id": str(item.product_id), "quantity": item.quantity}
                for item in order.items
            ],
        },
        key=str(order.user_id),
    )


async def create_order(
    session: AsyncSession, payload: OrderCreate, idempotency_key: str | None
) -> Order:
    if idempotency_key:
        existing = await _get_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return existing

    delivery = DELIVERY_OPTIONS[payload.delivery_method]
    items_amount = sum(
        (item.price_amount * item.quantity for item in payload.items),
        Decimal("0"),
    ).quantize(TWO_PLACES)
    total = (items_amount + delivery.price_amount - payload.discount_amount).quantize(TWO_PLACES)

    order = Order(
        number=await _next_number(),
        user_id=payload.user_id,
        status=OrderStatus.CREATED,
        idempotency_key=idempotency_key,
        currency=payload.currency,
        items_amount=items_amount,
        delivery_amount=delivery.price_amount,
        discount_amount=payload.discount_amount,
        total_amount=total,
        delivery_method=payload.delivery_method,
        delivery_address=payload.delivery_address,
        delivery_eta_days=delivery.eta_days,
        recipient_name=payload.recipient_name,
        recipient_phone=payload.recipient_phone,
        payment_method=payload.payment_method,
        comment=payload.comment,
    )
    order.items = [OrderItem(**item.model_dump()) for item in payload.items]
    order.history = [OrderStatusHistory(status=OrderStatus.CREATED, comment="Заказ оформлен")]
    session.add(order)

    try:
        await session.flush()
    except Exception as exc:
        await session.rollback()
        if idempotency_key:
            existing = await _get_by_idempotency_key(session, idempotency_key)
            if existing is not None:
                return existing
        raise ConflictError("Could not create order") from exc

    await _publish(order)
    return order


async def get_order(
    session: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> Order:
    order = await session.get(Order, order_id)
    if order is None or (user_id is not None and order.user_id != user_id):
        raise NotFoundError(f"Order {order_id} not found")
    return order


async def list_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    status: OrderStatus | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[Sequence[Order], int]:
    query = select(Order).where(Order.user_id == user_id)
    if status is not None:
        query = query.where(Order.status == status)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    result = await session.scalars(
        query.order_by(Order.created_at.desc()).limit(limit).offset(offset)
    )
    return result.all(), int(total or 0)


async def change_status(
    session: AsyncSession,
    order_id: uuid.UUID,
    new_status: OrderStatus,
    comment: str | None = None,
) -> Order:
    order = await get_order(session, order_id)
    if new_status not in STATUS_TRANSITIONS[order.status]:
        raise ConflictError(
            f"Cannot move order from {order.status} to {new_status}",
            code="invalid_status_transition",
        )
    order.status = new_status
    if new_status is OrderStatus.PAID:
        order.paid_at = datetime.now(UTC)
    session.add(OrderStatusHistory(order_id=order.id, status=new_status, comment=comment))
    await session.flush()
    await _publish(order)
    return order


@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED, tags=["orders"])
async def create_order_route(
    payload: OrderCreate,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Order:
    return await create_order(session, payload, idempotency_key)


@router.get("/orders", response_model=OrderListOut, tags=["orders"])
async def list_orders(
    session: SessionDep,
    user_id: uuid.UUID,
    order_status: OrderStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> OrderListOut:
    items, total = await list_for_user(
        session,
        user_id,
        status=order_status,
        limit=limit,
        offset=offset,
    )
    return OrderListOut(items=[OrderOut.model_validate(item) for item in items], total=total)


@router.get("/orders/{order_id}", response_model=OrderOut, tags=["orders"])
async def get_order_route(
    order_id: uuid.UUID,
    session: SessionDep,
    user_id: uuid.UUID | None = None,
) -> Order:
    return await get_order(session, order_id, user_id)


@router.patch("/orders/{order_id}/status", response_model=OrderOut, tags=["orders"])
async def change_status_route(
    order_id: uuid.UUID,
    payload: OrderStatusPatch,
    session: SessionDep,
) -> Order:
    return await change_status(session, order_id, payload.status, payload.comment)


@router.get("/delivery-options", response_model=list[DeliveryOption], tags=["delivery"])
async def list_delivery_options() -> list[DeliveryOption]:
    return list(DELIVERY_OPTIONS.values())
