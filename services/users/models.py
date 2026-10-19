from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str | None] = mapped_column(String(255), default=None)
    phone: Mapped[str | None] = mapped_column(String(32), default=None)
    avatar: Mapped[str | None] = mapped_column(Text, default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    roles: Mapped[list] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)
    addresses: Mapped[list[Address]] = relationship(
        back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )
    seller_profile: Mapped["Seller | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin"
    )


class Address(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(64), default=None)
    city: Mapped[str] = mapped_column(String(120))
    street: Mapped[str] = mapped_column(String(200))
    building: Mapped[str] = mapped_column(String(32))
    apartment: Mapped[str | None] = mapped_column(String(32), default=None)
    postal_code: Mapped[str | None] = mapped_column(String(16), default=None)
    recipient_name: Mapped[str] = mapped_column(String(200))
    recipient_phone: Mapped[str] = mapped_column(String(32))
    is_default: Mapped[bool] = mapped_column(default=False)
    user: Mapped[User] = relationship(back_populates="addresses")


class Seller(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sellers"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), unique=True, nullable=True
    )
    username: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    avatar: Mapped[str | None] = mapped_column(Text, default=None)
    cover_url: Mapped[str | None] = mapped_column(Text, default=None)
    city: Mapped[str | None] = mapped_column(String(120), default=None)
    rating: Mapped[Decimal] = mapped_column(Numeric(2, 1), default=Decimal("0.0"))
    followers_count: Mapped[int] = mapped_column(default=0)
    products_count: Mapped[int] = mapped_column(default=0)
    posts_count: Mapped[int] = mapped_column(default=0)
    is_verified: Mapped[bool] = mapped_column(default=False)

    user: Mapped[User | None] = relationship(back_populates="seller_profile")


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        UniqueConstraint("user_id", "seller_id", name="uq_subscription_user_seller"),
        Index("ix_subscriptions_seller_id", "seller_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    notifications_enabled: Mapped[bool] = mapped_column(default=True)
