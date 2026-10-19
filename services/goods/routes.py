from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from common.app import NotFoundError
from common.db import Database
from models import Category, Offer, Product

router = APIRouter(prefix="/api/v1")
_db: Database | None = None


def bind_db(database: Database) -> None:
    global _db
    _db = database


async def get_session() -> AsyncIterator[AsyncSession]:
    assert _db is not None
    async for session in _db.session():
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SortOrder(StrEnum):
    POPULAR = "popular"
    NEWEST = "newest"
    PRICE_ASC = "price_asc"
    PRICE_DESC = "price_desc"
    RATING = "rating"


class CategoryOut(ORMModel):
    id: uuid.UUID
    slug: str
    title: str
    parent_id: uuid.UUID | None
    image_url: str | None
    position: int


class OfferOut(ORMModel):
    id: uuid.UUID
    title: str | None
    price_amount: Decimal
    old_price_amount: Decimal | None
    currency: str
    stock: int
    is_default: bool
    is_active: bool


class ProductOut(ORMModel):
    id: uuid.UUID
    slug: str
    title: str
    subtitle: str | None
    description: str | None
    seller_id: uuid.UUID
    category_id: uuid.UUID | None
    images: list[dict[str, Any]]
    attributes: list[dict[str, Any]]
    tags: list[str]
    rating: Decimal
    reviews_count: int
    is_active: bool
    created_at: datetime
    offers: list[OfferOut] = Field(default_factory=list)
    category: CategoryOut | None = None


class ProductListOut(BaseModel):
    items: list[ProductOut]
    total: int


class ProductBatchRequest(BaseModel):
    ids: list[uuid.UUID] = Field(max_length=200)


class OfferResolved(BaseModel):
    offer: OfferOut
    product: ProductOut


def _apply_sort(query: Select, sort: SortOrder) -> Select:
    match sort:
        case SortOrder.NEWEST:
            return query.order_by(Product.created_at.desc())
        case SortOrder.RATING:
            return query.order_by(Product.rating.desc(), Product.reviews_count.desc())
        case SortOrder.PRICE_ASC | SortOrder.PRICE_DESC:
            price = (
                select(func.min(Offer.price_amount))
                .where(Offer.product_id == Product.id, Offer.is_active.is_(True))
                .scalar_subquery()
            )
            order = price.asc() if sort is SortOrder.PRICE_ASC else price.desc()
            return query.order_by(order)
        case _:
            return query.order_by(Product.reviews_count.desc(), Product.rating.desc())


async def list_categories(session: AsyncSession) -> Sequence[Category]:
    result = await session.scalars(
        select(Category).order_by(Category.position, Category.title)
    )
    return result.all()


async def get_category_by_slug(session: AsyncSession, slug: str) -> Category | None:
    result = await session.scalars(select(Category).where(Category.slug == slug))
    return result.first()


async def get_product(session: AsyncSession, product_id: uuid.UUID) -> Product | None:
    return await session.get(Product, product_id)


async def get_many_products(
    session: AsyncSession, product_ids: Sequence[uuid.UUID]
) -> list[Product]:
    if not product_ids:
        return []
    result = await session.scalars(select(Product).where(Product.id.in_(product_ids)))
    by_id = {product.id: product for product in result.all()}
    return [by_id[pid] for pid in product_ids if pid in by_id]


async def list_products(
    session: AsyncSession,
    *,
    category_id: uuid.UUID | None = None,
    seller_id: uuid.UUID | None = None,
    q: str | None = None,
    sale_mode: str | None = None,
    delivery: str | None = None,
    sort: SortOrder = SortOrder.POPULAR,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[Product], int]:
    query = select(Product).where(Product.is_active.is_(True))
    if category_id is not None:
        query = query.where(Product.category_id == category_id)
    if seller_id is not None:
        query = query.where(Product.seller_id == seller_id)
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Product.title.ilike(like), Product.description.ilike(like)))
    if sale_mode:
        query = query.where(Product.sale_mode == sale_mode)
    if delivery:
        query = query.where(Product.available_deliveries.contains([delivery]))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    query = _apply_sort(query, sort).limit(limit).offset(offset)
    result = await session.scalars(query)
    return list(result.all()), int(total or 0)


async def get_offer(session: AsyncSession, offer_id: uuid.UUID) -> Offer | None:
    return await session.get(Offer, offer_id)


async def _replace_offers(session: AsyncSession, product: Product, offers: list[dict]) -> None:
    if not offers:
        return
    existing = {offer.id: offer for offer in product.offers}
    seen: set[uuid.UUID] = set()
    for raw in offers:
        offer_id = uuid.UUID(str(raw["id"]))
        seen.add(offer_id)
        offer = existing.get(offer_id) or Offer(id=offer_id, product_id=product.id)
        offer.title = raw.get("title")
        offer.price_amount = raw["price_amount"]
        offer.old_price_amount = raw.get("old_price_amount")
        offer.currency = raw.get("currency", "RUB")
        offer.stock = raw.get("stock", 0)
        offer.is_default = raw.get("is_default", True)
        offer.is_active = raw.get("is_active", True)
        if offer.id not in existing:
            session.add(offer)
    for offer_id, offer in existing.items():
        if offer_id not in seen:
            await session.delete(offer)
    await session.flush()


async def upsert_from_event(session: AsyncSession, payload: dict) -> Product:
    product_id = uuid.UUID(str(payload["id"]))
    product = await get_product(session, product_id)
    if product is None:
        product = Product(id=product_id)
        session.add(product)

    for field in (
        "slug",
        "title",
        "subtitle",
        "description",
        "images",
        "attributes",
        "tags",
        "rating",
        "reviews_count",
        "is_active",
    ):
        if field in payload:
            setattr(product, field, payload[field])
    product.seller_id = uuid.UUID(str(payload.get("seller_id") or payload["master_id"]))
    if payload.get("sale_mode"):
        product.sale_mode = payload["sale_mode"]
    if payload.get("available_deliveries"):
        product.available_deliveries = payload["available_deliveries"]
    if "pickup_points" in payload:
        product.pickup_points = payload["pickup_points"]
    if "deal_contacts" in payload:
        product.deal_contacts = payload["deal_contacts"]
    if payload.get("category_id"):
        product.category_id = uuid.UUID(str(payload["category_id"]))

    await session.flush()
    await _replace_offers(session, product, payload.get("offers", []))
    return product


async def delete_product(session: AsyncSession, product_id: uuid.UUID) -> bool:
    product = await get_product(session, product_id)
    if product is None:
        return False
    await session.delete(product)
    return True


@router.get("/categories", response_model=list[CategoryOut], tags=["categories"])
async def list_categories_route(session: SessionDep) -> list[Category]:
    return list(await list_categories(session))


@router.get("/categories/{slug}", response_model=CategoryOut, tags=["categories"])
async def get_category(slug: str, session: SessionDep) -> Category:
    category = await get_category_by_slug(session, slug)
    if category is None:
        raise NotFoundError(f"Category {slug} not found")
    return category


@router.get("/goods", response_model=ProductListOut, tags=["goods"])
async def list_goods(
    session: SessionDep,
    category_id: uuid.UUID | None = None,
    seller_id: uuid.UUID | None = None,
    q: str | None = None,
    sale_mode: str | None = None,
    delivery: str | None = None,
    sort: SortOrder = SortOrder.POPULAR,
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ProductListOut:
    items, total = await list_products(
        session,
        category_id=category_id,
        seller_id=seller_id,
        q=q,
        sale_mode=sale_mode,
        delivery=delivery,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return ProductListOut(items=[ProductOut.model_validate(item) for item in items], total=total)


@router.post(
    "/goods/batch",
    response_model=list[ProductOut],
    summary="Hydrate ranked product ids",
    description="Returns products in the exact order of the requested ids, skipping unknown ones.",
    tags=["goods"],
)
async def get_goods_batch(payload: ProductBatchRequest, session: SessionDep) -> list[Product]:
    return await get_many_products(session, payload.ids)


@router.get("/goods/offers/{offer_id}", response_model=OfferResolved, tags=["goods"])
async def resolve_offer(offer_id: uuid.UUID, session: SessionDep) -> OfferResolved:
    offer = await get_offer(session, offer_id)
    if offer is None:
        raise NotFoundError(f"Offer {offer_id} not found")
    product = await get_product(session, offer.product_id)
    if product is None:
        raise NotFoundError(f"Product for offer {offer_id} not found")
    return OfferResolved.model_validate({"offer": offer, "product": product}, from_attributes=True)


@router.get("/goods/{product_id}", response_model=ProductOut, tags=["goods"])
async def get_product_route(product_id: uuid.UUID, session: SessionDep) -> Product:
    product = await get_product(session, product_id)
    if product is None:
        raise NotFoundError(f"Product {product_id} not found")
    return product
