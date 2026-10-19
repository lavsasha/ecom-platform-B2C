from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Category(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        default=None,
    )
    image_url: Mapped[str | None] = mapped_column(Text, default=None)
    position: Mapped[int] = mapped_column(default=0)


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        Index("ix_products_seller_id", "seller_id"),
        Index("ix_products_category_id", "category_id"),
    )

    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    subtitle: Mapped[str | None] = mapped_column(String(300), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    seller_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        default=None,
    )
    images: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    attributes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("0.0"))
    reviews_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    sale_mode: Mapped[str] = mapped_column(String(32), default="online")
    available_deliveries: Mapped[list[str]] = mapped_column(JSONB, default=list)
    pickup_points: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB, nullable=True)
    deal_contacts: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[Category | None] = relationship(lazy="joined")
    offers: Mapped[list[Offer]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class Offer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offers"

    product_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(200), default=None)
    price_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    old_price_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), default=None)
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    stock: Mapped[int] = mapped_column(default=0)
    is_default: Mapped[bool] = mapped_column(default=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    product: Mapped[Product] = relationship(back_populates="offers")
