from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any

import httpx

from common.app import get_logger
from common.kafka import ConsumerRunner, Topics

logger = get_logger("search.indexer")

INDEX_UID = "products"
_meili: httpx.AsyncClient | None = None


def _meili_client() -> httpx.AsyncClient:
    global _meili
    if _meili is None:
        base = os.getenv("MEILI_URL", "http://meilisearch:7700").rstrip("/")
        key = os.getenv("MEILI_MASTER_KEY", "masterKeyForLocalDevOnly")
        _meili = httpx.AsyncClient(
            base_url=base,
            headers={"Authorization": f"Bearer {key}"},
            timeout=10.0,
        )
    return _meili


async def aclose_meili() -> None:
    global _meili
    if _meili is not None:
        await _meili.aclose()
        _meili = None


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def product_to_document(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers") or []
    active_prices = [
        _decimal(o.get("price_amount"))
        for o in offers
        if o.get("is_active", True) and _decimal(o.get("price_amount")) is not None
    ]
    min_price = min(active_prices) if active_prices else None
    category = product.get("category") or {}
    return {
        "product_id": str(product["id"]),
        "slug": product.get("slug", ""),
        "title": product.get("title", ""),
        "subtitle": product.get("subtitle"),
        "description": product.get("description"),
        "seller_id": str(product.get("seller_id") or product.get("master_id", "")),
        "category_id": str(product["category_id"]) if product.get("category_id") else None,
        "category_slug": category.get("slug"),
        "category_title": category.get("title"),
        "tags": product.get("tags") or [],
        "rating": float(_decimal(product.get("rating")) or 0),
        "reviews_count": int(product.get("reviews_count") or 0),
        "is_active": bool(product.get("is_active", True)),
        "min_price": float(min_price) if min_price is not None else None,
        "created_at": product.get("created_at"),
    }


async def ensure_index() -> None:
    client = _meili_client()
    response = await client.get(f"/indexes/{INDEX_UID}")
    if response.status_code == 404:
        await client.post(
            "/indexes",
            json={"uid": INDEX_UID, "primaryKey": "product_id"},
        )
        await client.patch(
            f"/indexes/{INDEX_UID}/settings",
            json={
                "searchableAttributes": [
                    "title",
                    "subtitle",
                    "description",
                    "tags",
                    "category_title",
                ],
                "filterableAttributes": [
                    "category_id",
                    "category_slug",
                    "seller_id",
                    "is_active",
                    "tags",
                ],
                "sortableAttributes": ["rating", "reviews_count", "min_price", "created_at"],
            },
        )


async def upsert_documents(documents: list[dict[str, Any]]) -> None:
    if not documents:
        return
    client = _meili_client()
    await ensure_index()
    response = await client.post(f"/indexes/{INDEX_UID}/documents", json=documents)
    response.raise_for_status()


async def delete_document(product_id: uuid.UUID | str) -> None:
    client = _meili_client()
    pid = str(product_id)
    response = await client.delete(f"/indexes/{INDEX_UID}/documents/{pid}")
    if response.status_code not in (200, 202, 404):
        response.raise_for_status()


async def handle_goods_changed(_topic: str, payload: dict[str, Any]) -> None:
    action = payload.get("action")
    if action == "upserted" and payload.get("product"):
        doc = product_to_document(payload["product"])
        await upsert_documents([doc])
        logger.info("indexed_product", product_id=doc["product_id"])
    elif action == "deleted" and payload.get("product_id"):
        await delete_document(payload["product_id"])
        logger.info("removed_product", product_id=str(payload["product_id"]))
    else:
        logger.warning("unknown_goods_event", action=action)


def build_consumer() -> ConsumerRunner:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    enabled = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "search-indexer")
    return ConsumerRunner(
        bootstrap,
        topics=[Topics.GOODS_CHANGED],
        group_id=group_id,
        handler=handle_goods_changed,
        enabled=enabled,
    )
