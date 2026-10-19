from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from common.contract import CommentAuthorDTO, PostCommentDTO, PostDTO, ProductDTO, SellerDTO, dto_json


def seller_from_upstream(raw: dict, *, is_following: bool = False) -> dict:
    dto = SellerDTO(
        id=str(raw.get("id")),
        username=raw.get("username") or raw.get("slug", ""),
        displayName=raw.get("displayName") or raw.get("display_name", ""),
        avatar=raw.get("avatar") or raw.get("avatar_url") or "",
        bio=raw.get("bio") or raw.get("headline"),
        followersCount=int(
            raw.get("followersCount")
            or raw.get("followers_count")
            or raw.get("subscribers_count")
            or 0
        ),
        isFollowing=is_following,
        rating=float(raw.get("rating") or 0),
        productsCount=int(raw.get("productsCount") or raw.get("products_count") or 0),
        postsCount=int(raw.get("postsCount") or raw.get("posts_count") or 0),
        joinedAt=raw.get("joinedAt") or raw.get("created_at") or datetime.now(),
    )
    return dto_json(dto)


def product_from_upstream(raw: dict, seller: dict) -> dict:
    images = raw.get("images") or []
    image = ""
    if images:
        first = images[0]
        image = first.get("url") if isinstance(first, dict) else str(first)
    offers = raw.get("offers") or []
    offer = next((o for o in offers if o.get("is_default")), offers[0] if offers else None)
    price = int(Decimal(str(offer.get("price_amount", 0)))) if offer else 0
    in_stock = int(offer.get("stock", 0)) if offer else 0
    seller_dto = SellerDTO.model_validate(seller_from_upstream(seller))
    dto = ProductDTO(
        id=str(raw["id"]),
        title=raw.get("title", ""),
        description=raw.get("description"),
        image=image,
        price=price,
        sellerId=str(raw.get("seller_id") or raw.get("master_id")),
        seller=seller_dto,
        saleMode=raw.get("sale_mode") or "online",
        availableDeliveries=raw.get("available_deliveries") or ["pickup", "cdek"],
        pickupPoints=raw.get("pickup_points"),
        dealContacts=raw.get("deal_contacts"),
        inStock=in_stock,
        createdAt=raw.get("created_at") or datetime.now(),
        defaultOfferId=str(offer["id"]) if offer else None,
    )
    return dto_json(dto)


async def hydrate_products(
    upstream: Any,
    goods_rows: list[dict],
    *,
    subscribed_seller_ids: set[str] | None = None,
) -> list[dict]:
    seller_ids = {
        uuid.UUID(str(g.get("seller_id") or g.get("master_id"))) for g in goods_rows
    }
    sellers = await upstream.sellers_batch(list(seller_ids))
    by_seller = {str(s["id"]): s for s in sellers}
    subscribed = subscribed_seller_ids or set()
    out: list[dict] = []
    for g in goods_rows:
        sid = str(g.get("seller_id") or g.get("master_id"))
        seller_raw = by_seller.get(sid) or {
            "id": sid,
            "username": "unknown",
            "display_name": "Продавец",
        }
        seller_raw = dict(seller_raw)
        seller_raw["isFollowing"] = sid in subscribed
        out.append(product_from_upstream(g, seller_raw))
    return out


def comment_from_upstream(
    raw: dict, author: dict, viewer_id: uuid.UUID | None
) -> dict:
    author_dto = CommentAuthorDTO(
        id=str(author.get("id") or raw.get("user_id")),
        username=author.get("username") or "",
        displayName=author.get("displayName") or author.get("display_name") or "",
        avatar=author.get("avatar") or "",
    )
    dto = PostCommentDTO(
        id=str(raw["id"]),
        postId=str(raw["post_id"]),
        author=author_dto,
        body=raw.get("body") or "",
        createdAt=raw.get("created_at") or datetime.now(),
        updatedAt=raw.get("updated_at") or raw.get("created_at") or datetime.now(),
        isOwn=viewer_id is not None and str(viewer_id) == str(raw.get("user_id")),
    )
    return dto_json(dto)


def post_from_upstream(raw: dict, seller: dict, products: list[dict]) -> dict:
    seller_dto = SellerDTO.model_validate(seller_from_upstream(seller))
    dto = PostDTO(
        id=str(raw["id"]),
        sellerId=str(raw.get("seller_id") or raw.get("master_id")),
        seller=seller_dto,
        title=raw.get("title", ""),
        body=raw.get("body") or raw.get("content") or "",
        coverImage=raw.get("cover_image") or raw.get("cover_url"),
        products=products,
        createdAt=raw.get("published_at") or raw.get("created_at") or datetime.now(),
        likesCount=int(raw.get("likes_count") or 0),
        commentsCount=int(raw.get("comments_count") or 0),
        isLiked=False,
    )
    return dto_json(dto)
