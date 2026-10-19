from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _enum_str_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class OrderStatus(enum.StrEnum):
    CREATED = "created"
    PAID = "paid"
    ASSEMBLING = "assembling"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DeliveryMethod(enum.StrEnum):
    PICKUP = "pickup"
    CDEK = "cdek"
    COURIER = "courier"
    POST = "post"


STATUS_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.CREATED: {OrderStatus.PAID, OrderStatus.CANCELLED},
    OrderStatus.PAID: {OrderStatus.ASSEMBLING, OrderStatus.CANCELLED},
    OrderStatus.ASSEMBLING: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: set(),
    OrderStatus.CANCELLED: set(),
}


class Order(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "orders"

    number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            native_enum=False,
            values_callable=_enum_str_values,
        ),
        default=OrderStatus.CREATED,
        index=True,
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(80), unique=True, default=None)

    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    items_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    delivery_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))

    delivery_method: Mapped[DeliveryMethod] = mapped_column(
        Enum(
            DeliveryMethod,
            name="delivery_method",
            native_enum=False,
            values_callable=_enum_str_values,
        ),
        default=DeliveryMethod.COURIER,
    )
    delivery_address: Mapped[str | None] = mapped_column(Text, default=None)
    delivery_eta_days: Mapped[int | None] = mapped_column(default=None)
    recipient_name: Mapped[str] = mapped_column(String(200), default="")
    recipient_phone: Mapped[str] = mapped_column(String(32), default="")
    payment_method: Mapped[str] = mapped_column(String(32), default="card")
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderStatusHistory.created_at",
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    offer_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    seller_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), default=None)
    title: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    quantity: Mapped[int] = mapped_column(default=1)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    order: Mapped[Order] = relationship(back_populates="items")


class OrderStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        index=True,
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            native_enum=False,
            values_callable=_enum_str_values,
        )
    )
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    order: Mapped[Order] = relationship(back_populates="history")
