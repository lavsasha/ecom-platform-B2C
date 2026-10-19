"""Frontend API contract shapes (camelCase JSON). Shared by b2c mappers and service DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ContractModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class UserDTO(ContractModel):
    id: str
    username: str
    display_name: str = Field(alias="displayName")
    avatar: str = ""
    email: str
    roles: list[Literal["buyer", "seller"]] = Field(default_factory=lambda: ["buyer"])
    bio: str | None = None
    created_at: datetime = Field(alias="createdAt")


class SellerDTO(ContractModel):
    id: str
    username: str
    display_name: str = Field(alias="displayName")
    avatar: str = ""
    bio: str | None = None
    followers_count: int = Field(0, alias="followersCount")
    is_following: bool = Field(False, alias="isFollowing")
    rating: float = 0.0
    products_count: int = Field(0, alias="productsCount")
    posts_count: int = Field(0, alias="postsCount")
    joined_at: datetime = Field(alias="joinedAt")


class ProductDTO(ContractModel):
    id: str
    title: str
    description: str | None = None
    image: str
    price: int
    currency: Literal["RUB"] = "RUB"
    seller_id: str = Field(alias="sellerId")
    seller: SellerDTO
    sale_mode: Literal["online", "out_of_stock", "deal_only"] = Field("online", alias="saleMode")
    available_deliveries: list[Literal["pickup", "cdek"]] = Field(
        default_factory=list, alias="availableDeliveries"
    )
    pickup_points: list[dict[str, str]] | None = Field(None, alias="pickupPoints")
    deal_contacts: str | None = Field(None, alias="dealContacts")
    in_stock: int = Field(0, alias="inStock")
    created_at: datetime = Field(alias="createdAt")
    default_offer_id: str | None = Field(None, alias="defaultOfferId")


class CommentAuthorDTO(ContractModel):
    id: str
    username: str
    display_name: str = Field(alias="displayName")
    avatar: str = ""


class PostCommentDTO(ContractModel):
    id: str
    post_id: str = Field(alias="postId")
    author: CommentAuthorDTO
    body: str
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    is_own: bool = Field(False, alias="isOwn")


class PostDTO(ContractModel):
    id: str
    seller_id: str = Field(alias="sellerId")
    seller: SellerDTO
    title: str
    body: str
    cover_image: str | None = Field(None, alias="coverImage")
    products: list[ProductDTO] = Field(default_factory=list)
    created_at: datetime = Field(alias="createdAt")
    likes_count: int = Field(0, alias="likesCount")
    comments_count: int = Field(0, alias="commentsCount")
    is_liked: bool = Field(False, alias="isLiked")


class OrderItemDTO(ContractModel):
    product: ProductDTO
    quantity: int


class OrderDTO(ContractModel):
    id: str
    created_at: datetime = Field(alias="createdAt")
    status: Literal["created", "paid", "shipped", "delivered", "cancelled"]
    buyer: UserDTO | None = None
    seller: SellerDTO
    items: list[OrderItemDTO]
    delivery: Literal["pickup", "cdek"]
    pickup_point: dict[str, str] | None = Field(None, alias="pickupPoint")
    tracking_number: str | None = Field(None, alias="trackingNumber")
    total: int


def dto_json(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True)
