from __future__ import annotations

import uuid
from typing import Any

from clients import Upstreams
from common.app import NotFoundError
from gather import Section, SectionStatus, gather_sections
from mappers import hydrate_products, post_from_upstream, product_from_upstream, seller_from_upstream

_upstream: Upstreams | None = None


def bind(upstreams: Upstreams) -> None:
    global _upstream
    _upstream = upstreams


def _u() -> Upstreams:
    assert _upstream is not None
    return _upstream


def _section(sec: Section[Any]) -> dict:
    return {
        "status": sec.status,
        "items": sec.items if sec.items is not None else [],
        "data": sec.data,
    }


async def home_page(user_id: uuid.UUID | None) -> dict:
    up = _u()
    subscribed_ids: set[str] = set()
    if user_id:
        subs = await up.list_subscriptions(user_id)
        subscribed_ids = {s["sellerId"] for s in subs}

    async def recommendations() -> list[dict]:
        if not user_id:
            goods = await up.list_goods(limit=12)
            return await hydrate_products(up, goods.get("items") or [])
        ids = await up.gorse_recommend(user_id, n=12)
        if not ids:
            goods = await up.list_goods(limit=12)
            return await hydrate_products(up, goods.get("items") or [], subscribed_seller_ids=subscribed_ids)
        products = await up.goods_batch([uuid.UUID(i) for i in ids if _valid_uuid(i)])
        return await hydrate_products(up, products, subscribed_seller_ids=subscribed_ids)

    async def categories() -> list[dict]:
        return await up.get_categories()

    async def popular_sellers() -> list[dict]:
        sellers = await up.popular_sellers(12)
        return [
            seller_from_upstream(s, is_following=str(s["id"]) in subscribed_ids) for s in sellers
        ]

    async def subscription_feed() -> list[dict]:
        if not user_id:
            return []
        subs = await up.list_subscriptions(user_id)
        seller_ids = [uuid.UUID(s["sellerId"]) for s in subs]
        if not seller_ids:
            return []
        feed = await up.post_feed(seller_ids=seller_ids, limit=10)
        return await _map_posts(feed.get("items") or [], subscribed_ids)

    sections = await gather_sections(
        {
            "recommendations": recommendations,
            "categories": categories,
            "popular_sellers": popular_sellers,
            "subscription_feed": subscription_feed,
        }
    )
    return {k: _section(v) for k, v in sections.items()}


def _valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False


async def _map_posts(items: list[dict], subscribed_ids: set[str]) -> list[dict]:
    up = _u()
    seller_ids = {uuid.UUID(str(p.get("seller_id") or p.get("master_id"))) for p in items}
    sellers = await up.sellers_batch(list(seller_ids))
    by_seller = {str(s["id"]): s for s in sellers}
    out = []
    for p in items:
        sid = str(p.get("seller_id") or p.get("master_id"))
        seller = by_seller.get(sid, {"id": sid, "username": "unknown", "display_name": ""})
        seller = dict(seller)
        seller["isFollowing"] = sid in subscribed_ids
        product_ids = [uuid.UUID(str(x["product_id"])) for x in p.get("products") or []]
        goods = await hydrate_products(up, await up.goods_batch(product_ids), subscribed_seller_ids=subscribed_ids)
        out.append(post_from_upstream(p, seller, goods))
    return out


async def search_page(q: str, page: int, limit: int) -> dict:
    up = _u()
    result = await up.search(q, page=page, limit=limit)
    ids = [uuid.UUID(str(hit["product_id"])) for hit in result.get("items") or [] if hit.get("product_id")]
    products = await hydrate_products(up, await up.goods_batch(ids))
    sections = await gather_sections(
        {
            "products": lambda: products,
            "facets": lambda: result.get("facets") or {},
        }
    )
    return {k: _section(v) for k, v in sections.items()}


async def publications_page(cursor: str | None, limit: int, user_id: uuid.UUID | None) -> dict:
    subscribed: set[str] = set()
    if user_id:
        subs = await _u().list_subscriptions(user_id)
        subscribed = {s["sellerId"] for s in subs}
    feed = await _u().post_feed(cursor=cursor, limit=limit)
    posts = await _map_posts(feed.get("items") or [], subscribed)
    return {
        "posts": {"status": SectionStatus.OK, "items": posts, "data": None},
        "next_cursor": feed.get("next_cursor"),
        "has_more": feed.get("has_more", False),
    }


async def publication_detail(publication_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    raw = await _u().get_post(publication_id)
    subscribed: set[str] = set()
    if user_id:
        subs = await _u().list_subscriptions(user_id)
        subscribed = {s["sellerId"] for s in subs}
    posts = await _map_posts([raw], subscribed)
    if not posts:
        raise NotFoundError("Post not found")
    return {"post": posts[0]}


async def product_detail(product_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    up = _u()
    raw = await up.get_product(product_id)
    seller_id = uuid.UUID(str(raw.get("seller_id") or raw.get("master_id")))
    seller = await up.get_seller(seller_id)
    subscribed = set()
    if user_id:
        subs = await up.list_subscriptions(user_id)
        subscribed = {s["sellerId"] for s in subs}
    product = product_from_upstream(
        raw,
        {**seller, "isFollowing": str(seller_id) in subscribed},
    )
    feed = await up.post_feed(product_id=product_id, limit=5)
    related = await _map_posts(feed.get("items") or [], subscribed)
    return {
        "product": product,
        "seller": _section(Section(status=SectionStatus.OK, data=seller_from_upstream(seller))),
        "related_posts": _section(Section(status=SectionStatus.OK, items=related)),
    }


async def seller_detail(seller_id: uuid.UUID, user_id: uuid.UUID | None) -> dict:
    up = _u()
    seller = await up.get_seller(seller_id)
    subscribed = set()
    if user_id:
        subs = await up.list_subscriptions(user_id)
        subscribed = {s["sellerId"] for s in subs}
    goods = await up.list_goods(seller_id=seller_id, limit=24)
    products = await hydrate_products(up, goods.get("items") or [], subscribed_seller_ids=subscribed)
    feed = await up.post_feed(seller_ids=[seller_id], limit=10)
    posts = await _map_posts(feed.get("items") or [], subscribed)
    return {
        "seller": seller_from_upstream(seller, is_following=str(seller_id) in subscribed),
        "products": _section(Section(status=SectionStatus.OK, items=products)),
        "posts": _section(Section(status=SectionStatus.OK, items=posts)),
    }


async def subscriptions_page(user_id: uuid.UUID) -> dict:
    subs = await _u().list_subscriptions(user_id)
    seller_ids = [uuid.UUID(s["sellerId"]) for s in subs]
    sellers = await _u().sellers_batch(seller_ids)
    items = [seller_from_upstream(s, is_following=True) for s in sellers]
    return {"subscriptions": _section(Section(status=SectionStatus.OK, items=items))}


async def cart_page(user_id: uuid.UUID) -> dict:
    cart = await _u().get_cart(user_id)
    return {"cart": _section(Section(status=SectionStatus.OK, data=cart))}


async def checkout_page(user_id: uuid.UUID) -> dict:
    up = _u()
    sections = await gather_sections(
        {
            "cart": lambda: up.get_cart(user_id),
            "delivery_options": lambda: up.delivery_options(),
        }
    )
    return {k: _section(v) for k, v in sections.items()}


async def orders_page(user_id: uuid.UUID, page: int, limit: int) -> dict:
    data = await _u().list_orders(user_id, page=page, limit=limit)
    return {"orders": _section(Section(status=SectionStatus.OK, items=data.get("items") or []))}


async def order_detail(order_id: uuid.UUID) -> dict:
    order = await _u().get_order(order_id)
    return {"order": order}
