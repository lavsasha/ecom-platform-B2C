from __future__ import annotations

import os
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Query

from common.app import UpstreamUnavailableError
from indexer import INDEX_UID, ensure_index

router = APIRouter(prefix="/api/v1")


def _meili() -> httpx.AsyncClient:
    base = os.getenv("MEILI_URL", "http://meilisearch:7700").rstrip("/")
    key = os.getenv("MEILI_MASTER_KEY", "masterKeyForLocalDevOnly")
    return httpx.AsyncClient(
        base_url=base,
        headers={"Authorization": f"Bearer {key}"},
        timeout=5.0,
    )


@router.get("/search", tags=["search"])
async def search_products(
    q: str = "",
    category: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 24,
) -> dict[str, Any]:
    offset = (page - 1) * limit
    filters: list[str] = ['is_active = true']
    if category:
        filters.append(f'(category_slug = "{category}" OR category_id = "{category}")')

    body: dict[str, Any] = {
        "q": q,
        "limit": limit,
        "offset": offset,
        "facets": ["category_slug", "tags"],
    }
    if filters:
        body["filter"] = " AND ".join(filters)

    async with _meili() as client:
        try:
            await ensure_index()
            response = await client.post(f"/indexes/{INDEX_UID}/search", json=body)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError("meilisearch", details={"error": str(exc)}) from exc

    hits = data.get("hits") or []
    items = [
        {
            "product_id": hit.get("product_id"),
            "slug": hit.get("slug"),
            "title": hit.get("title"),
            "subtitle": hit.get("subtitle"),
            "seller_id": hit.get("seller_id") or hit.get("master_id"),
            "category_id": hit.get("category_id"),
            "category_slug": hit.get("category_slug"),
            "category_title": hit.get("category_title"),
            "tags": hit.get("tags") or [],
            "rating": hit.get("rating"),
            "reviews_count": hit.get("reviews_count"),
            "min_price": hit.get("min_price"),
        }
        for hit in hits
    ]
    facet_distribution = data.get("facetDistribution") or {}
    facets = {
        "category_slug": facet_distribution.get("category_slug") or {},
        "tags": facet_distribution.get("tags") or {},
    }
    total = int(data.get("estimatedTotalHits") or data.get("totalHits") or len(items))
    return {"items": items, "facets": facets, "total": total}
