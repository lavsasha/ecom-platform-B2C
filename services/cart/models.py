from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Cart(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), unique=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    promo_code: Mapped[str | None] = mapped_column(String(64), default=None)

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CartItem.created_at",
    )


class CartItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "cart_items"
    __table_args__ = (UniqueConstraint("cart_id", "offer_id", name="uq_cart_item_offer"),)

    cart_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    offer_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    seller_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True), default=None)
    quantity: Mapped[int] = mapped_column(default=1)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    title: Mapped[str] = mapped_column(String(300), default="")
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    is_selected: Mapped[bool] = mapped_column(default=True)

    cart: Mapped[Cart] = relationship(back_populates="items")
