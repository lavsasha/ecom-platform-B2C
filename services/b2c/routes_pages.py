from __future__ import annotations

import uuid
from typing import Annotated

from common.app import NotFoundError, OptionalUser, RequiredUser
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

import pages

router = APIRouter(prefix="/api/v1/pages", tags=["pages"])


@router.get("/home")
async def page_home(user: OptionalUser) -> dict:
    return await pages.home_page(user.id if user else None)


class SearchPageBody(BaseModel):
    q: str = ""
    page: int = Field(1, ge=1)
    limit: int = Field(24, ge=1, le=100)


@router.get("/search")
async def page_search(
    q: str = "",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
) -> dict:
    return await pages.search_page(q, page, limit)


@router.post("/search")
async def page_search_post(body: SearchPageBody) -> dict:
    """Same as GET /search; use for non-ASCII q from curl/PowerShell (UTF-8 in JSON body)."""
    return await pages.search_page(body.q, body.page, body.limit)


@router.get("/publications")
async def page_publications(
    user: OptionalUser,
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
) -> dict:
    return await pages.publications_page(cursor, limit, user.id if user else None)


@router.get("/publications/{publication_id}")
async def page_publication(publication_id: uuid.UUID, user: OptionalUser) -> dict:
    try:
        return await pages.publication_detail(publication_id, user.id if user else None)
    except NotFoundError:
        raise


@router.get("/products/{product_id}")
async def page_product(product_id: uuid.UUID, user: OptionalUser) -> dict:
    try:
        return await pages.product_detail(product_id, user.id if user else None)
    except NotFoundError:
        raise


@router.get("/sellers/{seller_id}")
async def page_seller(seller_id: uuid.UUID, user: OptionalUser) -> dict:
    return await pages.seller_detail(seller_id, user.id if user else None)


@router.get("/masters/{master_id}")
async def page_master_alias(master_id: uuid.UUID, user: OptionalUser) -> dict:
    return await pages.seller_detail(master_id, user.id if user else None)


@router.get("/subscriptions")
async def page_subscriptions(user: RequiredUser) -> dict:
    return await pages.subscriptions_page(user.id)


@router.get("/cart")
async def page_cart(user: RequiredUser) -> dict:
    return await pages.cart_page(user.id)


@router.get("/checkout")
async def page_checkout(user: RequiredUser) -> dict:
    return await pages.checkout_page(user.id)


@router.get("/orders")
async def page_orders(
    user: RequiredUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    return await pages.orders_page(user.id, page, limit)


@router.get("/orders/{order_id}")
async def page_order(order_id: uuid.UUID) -> dict:
    return await pages.order_detail(order_id)


@router.get("/order-success/{order_id}")
async def page_order_success(order_id: uuid.UUID) -> dict:
    return await pages.order_detail(order_id)
