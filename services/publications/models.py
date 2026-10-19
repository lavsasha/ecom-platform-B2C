from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from common.db import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Post(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_seller_id", "seller_id"),
        Index("ix_posts_published_at", "published_at"),
    )

    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    seller_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(String(600), default=None)
    body: Mapped[str] = mapped_column(Text, default="")
    cover_image: Mapped[str | None] = mapped_column(Text, default=None)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    likes_count: Mapped[int] = mapped_column(default=0)
    comments_count: Mapped[int] = mapped_column(default=0)
    is_published: Mapped[bool] = mapped_column(default=True)

    products: Mapped[list[PostProduct]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PostProduct.position",
    )
    comments: Mapped[list[PostComment]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
        lazy="raise",
    )


class PostProduct(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "post_products"
    __table_args__ = (UniqueConstraint("post_id", "product_id", name="uq_post_product"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        index=True,
    )
    product_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    position: Mapped[int] = mapped_column(default=0)

    post: Mapped[Post] = relationship(back_populates="products")


class PostComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "post_comments"
    __table_args__ = (Index("ix_post_comments_post_id_created_at", "post_id", "created_at"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    body: Mapped[str] = mapped_column(Text)

    post: Mapped[Post] = relationship(back_populates="comments")


class PostLike(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "post_likes"
    __table_args__ = (UniqueConstraint("post_id", "user_id", name="uq_post_like"),)

    post_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), index=True)
    post: Mapped[Post] = relationship()
