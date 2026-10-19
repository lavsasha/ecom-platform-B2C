from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from clients import Upstreams
from contract_api.errors import forbidden, not_found, unauthorized, validation_error
from mappers import (
    comment_from_upstream,
    hydrate_products,
    post_from_upstream,
    product_from_upstream,
    seller_from_upstream,
)


class FrontendFacade:
    def __init__(self, upstream: Upstreams) -> None:
        self._up = upstream

    async def _subscribed_ids(self, user_id: uuid.UUID | None) -> set[str]:
        if not user_id:
            return set()
        subs = await self._up.list_subscriptions(user_id)
        return {s["sellerId"] for s in subs}

    async def _seller_with_follow(self, seller: dict, subscribed: set[str]) -> dict:
        sid = str(seller["id"])
        return seller_from_upstream(seller, is_following=sid in subscribed)

    async def login(self, email: str, password: str) -> dict:
        return await self._up.login(email, password)

    async def register(self, payload: dict) -> dict:
        return await self._up.register(payload)

    async def me(self, user_id: uuid.UUID) -> dict:
        return await self._up.get_user(user_id)

    async def patch_me(self, user_id: uuid.UUID, payload: dict) -> dict:
        return await self._up.patch_user(user_id, payload)

    async def become_seller(self, user_id: uuid.UUID, payload: dict) -> dict:
        return await self._up.become_seller(user_id, payload)

    async def list_sellers(
        self,
        q: str | None,
        page: int,
        page_size: int,
        viewer_id: uuid.UUID | None,
    ) -> dict:
        data = await self._up.list_sellers(q=q, page=page, page_size=page_size)
        subscribed = await self._subscribed_ids(viewer_id)
        items = [
            await self._seller_with_follow(s, subscribed) for s in data.get("items") or []
        ]
        return {
            "items": items,
            "total": data.get("total", len(items)),
            "page": page,
            "pageSize": page_size,
        }

    async def seller_by_username(self, username: str, viewer_id: uuid.UUID | None) -> dict:
        seller = await self._up.seller_by_username(username)
        subscribed = await self._subscribed_ids(viewer_id)
        return await self._seller_with_follow(seller, subscribed)

    async def seller_by_id(self, seller_id: uuid.UUID, viewer_id: uuid.UUID | None) -> dict:
        seller = await self._up.get_seller(seller_id)
        subscribed = await self._subscribed_ids(viewer_id)
        return await self._seller_with_follow(seller, subscribed)

    async def follow(self, user_id: uuid.UUID, seller_id: uuid.UUID) -> dict:
        await self._up.subscribe(user_id, seller_id)
        seller = await self._up.get_seller(seller_id)
        return {"isFollowing": True, "followersCount": seller.get("followersCount", 0)}

    async def unfollow(self, user_id: uuid.UUID, seller_id: uuid.UUID) -> dict:
        await self._up.unsubscribe(user_id, seller_id)
        seller = await self._up.get_seller(seller_id)
        return {"isFollowing": False, "followersCount": seller.get("followersCount", 0)}

    async def list_products(
        self,
        *,
        q: str | None,
        page: int,
        page_size: int,
        seller_id: uuid.UUID | None,
        delivery: str | None,
        sale_mode: str | None,
        viewer_id: uuid.UUID | None,
    ) -> dict:
        offset = (page - 1) * page_size
        data = await self._up.list_goods(
            q=q,
            seller_id=seller_id,
            limit=page_size,
            offset=offset,
            sale_mode=sale_mode,
            delivery=delivery,
        )
        subscribed = await self._subscribed_ids(viewer_id)
        items = await hydrate_products(self._up, data.get("items") or [], subscribed_seller_ids=subscribed)
        return {
            "items": items,
            "total": data.get("total", len(items)),
            "page": page,
            "pageSize": page_size,
        }

    async def get_product(self, product_id: uuid.UUID, viewer_id: uuid.UUID | None) -> dict:
        raw = await self._up.get_product(product_id)
        subscribed = await self._subscribed_ids(viewer_id)
        sid = str(raw.get("seller_id"))
        seller = await self._up.get_seller(uuid.UUID(sid))
        seller = dict(seller)
        seller["isFollowing"] = sid in subscribed
        return product_from_upstream(raw, seller)

    async def list_posts(
        self,
        *,
        q: str | None,
        page: int | None,
        page_size: int,
        cursor: str | None,
        limit: int,
        viewer_id: uuid.UUID | None,
        seller_id: uuid.UUID | None = None,
    ) -> dict:
        subscribed = await self._subscribed_ids(viewer_id)
        seller_ids = [seller_id] if seller_id else None
        if cursor is not None or page is None:
            feed = await self._up.post_feed(
                cursor=cursor, limit=limit, q=q, seller_ids=seller_ids
            )
            posts = await self._map_posts(feed.get("items") or [], subscribed, viewer_id)
            return {"items": posts, "nextCursor": feed.get("next_cursor")}
        offset = ((page or 1) - 1) * page_size
        feed = await self._up.post_feed(
            limit=page_size + offset, q=q, seller_ids=seller_ids
        )
        items = feed.get("items") or []
        sliced = items[offset : offset + page_size]
        posts = await self._map_posts(sliced, subscribed, viewer_id)
        return {
            "items": posts,
            "total": len(items),
            "page": page,
            "pageSize": page_size,
        }

    async def get_post(self, post_id: uuid.UUID, viewer_id: uuid.UUID | None) -> dict:
        raw = await self._up.get_post(post_id)
        subscribed = await self._subscribed_ids(viewer_id)
        posts = await self._map_posts([raw], subscribed, viewer_id)
        if not posts:
            raise not_found("Пост не найден")
        return posts[0]

    async def like_post(self, user_id: uuid.UUID, post_id: uuid.UUID) -> dict:
        return await self._up.like_post(user_id, post_id)

    async def unlike_post(self, user_id: uuid.UUID, post_id: uuid.UUID) -> dict:
        return await self._up.unlike_post(user_id, post_id)

    async def list_post_comments(
        self,
        post_id: uuid.UUID,
        *,
        cursor: str | None,
        limit: int,
        viewer_id: uuid.UUID | None,
    ) -> dict:
        feed = await self._up.list_post_comments(post_id, cursor=cursor, limit=limit)
        return await self._map_comment_feed(feed, viewer_id)

    async def create_post_comment(
        self, user_id: uuid.UUID, post_id: uuid.UUID, body: str
    ) -> dict:
        raw = await self._up.create_post_comment(user_id, post_id, body)
        return await self._map_single_comment(raw, viewer_id=user_id)

    async def update_post_comment(
        self, user_id: uuid.UUID, comment_id: uuid.UUID, body: str
    ) -> dict:
        raw = await self._up.update_post_comment(user_id, comment_id, body)
        return await self._map_single_comment(raw, viewer_id=user_id)

    async def delete_post_comment(self, user_id: uuid.UUID, comment_id: uuid.UUID) -> None:
        await self._up.delete_post_comment(user_id, comment_id)

    async def _map_single_comment(
        self, raw: dict, *, viewer_id: uuid.UUID | None
    ) -> dict:
        user_id = uuid.UUID(str(raw["user_id"]))
        authors = await self._up.users_batch([user_id])
        author = authors[0] if authors else {"id": str(user_id), "username": "", "displayName": ""}
        return comment_from_upstream(raw, author, viewer_id)

    async def _map_comment_feed(self, feed: dict, viewer_id: uuid.UUID | None) -> dict:
        items = feed.get("items") or []
        if not items:
            return {"items": [], "nextCursor": feed.get("next_cursor")}
        user_ids = list({uuid.UUID(str(c["user_id"])) for c in items})
        authors = await self._up.users_batch(user_ids)
        by_user = {str(u["id"]): u for u in authors}
        mapped = []
        for c in items:
            uid = str(c.get("user_id"))
            author = by_user.get(
                uid,
                {"id": uid, "username": "", "displayName": "", "avatar": ""},
            )
            mapped.append(comment_from_upstream(c, author, viewer_id))
        return {"items": mapped, "nextCursor": feed.get("next_cursor")}

    async def _map_posts(
        self,
        items: list[dict],
        subscribed: set[str],
        viewer_id: uuid.UUID | None,
    ) -> list[dict]:
        if not items:
            return []
        seller_ids = {uuid.UUID(str(p.get("seller_id"))) for p in items}
        sellers = await self._up.sellers_batch(list(seller_ids))
        by_seller = {str(s["id"]): s for s in sellers}
        liked_ids: set[str] = set()
        if viewer_id:
            liked_ids = set(await self._up.liked_posts(viewer_id, [p["id"] for p in items]))
        out = []
        for p in items:
            sid = str(p.get("seller_id"))
            seller = dict(by_seller.get(sid, {"id": sid, "username": "", "display_name": ""}))
            seller["isFollowing"] = sid in subscribed
            product_ids = [uuid.UUID(str(x["product_id"])) for x in p.get("products") or []]
            goods = await hydrate_products(
                self._up, await self._up.goods_batch(product_ids), subscribed_seller_ids=subscribed
            )
            post = post_from_upstream(p, seller, goods)
            post["isLiked"] = str(p["id"]) in liked_ids
            out.append(post)
        return out

    async def create_orders_from_cart(
        self,
        user_id: uuid.UUID,
        body: dict,
        payment_url: str,
    ) -> dict:
        groups = body.get("groups") or []
        contact = body.get("contact") or {}
        if not groups:
            raise validation_error("groups обязателен")
        orders_out = []
        for group in groups:
            seller_id = group.get("sellerId")
            delivery = group.get("delivery", "cdek")
            items_in = group.get("items") or []
            if not items_in:
                continue
            order_items = []
            for line in items_in:
                product_id = uuid.UUID(str(line["productId"]))
                qty = int(line["quantity"])
                raw = await self._up.get_product(product_id)
                offers = raw.get("offers") or []
                offer = next((o for o in offers if o.get("is_default")), offers[0] if offers else None)
                if not offer:
                    raise validation_error("Товар недоступен", productId=str(product_id))
                if raw.get("sale_mode") not in (None, "online"):
                    raise validation_error("Товар недоступен для покупки", productId=str(product_id))
                if int(offer.get("stock", 0)) < qty:
                    raise validation_error("Недостаточно на складе", productId=str(product_id))
                order_items.append(
                    {
                        "product_id": str(product_id),
                        "offer_id": str(offer["id"]),
                        "seller_id": str(raw.get("seller_id")),
                        "title": raw.get("title", ""),
                        "image_url": (raw.get("images") or [{}])[0].get("url")
                        if raw.get("images")
                        else None,
                        "quantity": qty,
                        "price_amount": str(offer["price_amount"]),
                    }
                )
            pickup = group.get("pickupPoint")
            address = None
            if pickup:
                address = f"{pickup.get('city')}, {pickup.get('address')}"
            method = "pickup" if delivery == "pickup" else "cdek"
            payload = {
                "user_id": str(user_id),
                "items": order_items,
                "delivery_method": method,
                "delivery_address": address,
                "recipient_name": contact.get("name", ""),
                "recipient_phone": contact.get("phone", ""),
                "comment": contact.get("email"),
            }
            order = await self._up.create_order(payload)
            orders_out.append(await self._map_order(order, user_id))
        return {"orders": orders_out, "paymentUrl": payment_url}

    async def list_orders(
        self,
        user_id: uuid.UUID,
        page: int,
        page_size: int,
        role: str,
        status: str | None,
    ) -> dict:
        data = await self._up.list_orders(user_id, page=page, limit=page_size)
        items = [await self._map_order(o, user_id) for o in data.get("items") or []]
        if status:
            items = [o for o in items if o.get("status") == status]
        return {
            "items": items,
            "total": data.get("total", len(items)),
            "page": page,
            "pageSize": page_size,
        }

    async def get_order(self, order_id: uuid.UUID, user_id: uuid.UUID) -> dict:
        order = await self._up.get_order(order_id)
        if str(order.get("user_id")) != str(user_id):
            raise forbidden()
        return await self._map_order(order, user_id)

    async def _map_order(self, order: dict, viewer_id: uuid.UUID) -> dict:
        from common.contract import OrderDTO, OrderItemDTO, SellerDTO, UserDTO, dto_json

        seller_id = None
        items_raw = order.get("items") or []
        if items_raw:
            seller_id = items_raw[0].get("seller_id")
        seller = (
            await self._up.get_seller(uuid.UUID(str(seller_id)))
            if seller_id
            else {"id": "", "username": "", "display_name": ""}
        )
        buyer = await self._up.get_user(viewer_id)
        subscribed = await self._subscribed_ids(viewer_id)
        line_items = []
        for it in items_raw:
            raw = await self._up.get_product(uuid.UUID(str(it["product_id"])))
            s = dict(seller)
            s["isFollowing"] = str(seller.get("id")) in subscribed
            line_items.append(
                {
                    "product": product_from_upstream(raw, s),
                    "quantity": it["quantity"],
                }
            )
        delivery = order.get("delivery_method", "cdek")
        if delivery not in ("pickup", "cdek"):
            delivery = "cdek"
        status = order.get("status", "created")
        if status not in ("created", "paid", "shipped", "delivered", "cancelled"):
            status = "created"
        dto = OrderDTO(
            id=str(order["id"]),
            createdAt=order.get("created_at"),
            status=status,
            buyer=UserDTO.model_validate(buyer),
            seller=SellerDTO.model_validate(seller_from_upstream(seller)),
            items=[OrderItemDTO.model_validate(x) for x in line_items],
            delivery=delivery,
            pickupPoint=None,
            trackingNumber=None,
            total=int(Decimal(str(order.get("total_amount", 0)))),
        )
        return dto_json(dto)
