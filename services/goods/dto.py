from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from common.contract import ProductDTO, SellerDTO, dto_json
from models import Offer, Product


def _primary_image(product: Product) -> str:
    images = product.images or []
    if not images:
        return ""
    first = images[0]
    if isinstance(first, dict):
        return str(first.get("url") or first.get("src") or "")
    return str(first)


def _default_offer(product: Product) -> Offer | None:
    active = [o for o in product.offers if o.is_active]
    if not active:
        return None
    for offer in active:
        if offer.is_default:
            return offer
    return active[0]


def product_to_dto(product: Product, seller: dict) -> dict:
    offer = _default_offer(product)
    price = int(offer.price_amount) if offer else 0
    in_stock = offer.stock if offer else 0
    deliveries = list(product.available_deliveries or [])
    if not deliveries:
        deliveries = ["pickup", "cdek"]
    seller_dto = SellerDTO.model_validate(seller)
    dto = ProductDTO(
        id=str(product.id),
        title=product.title,
        description=product.description,
        image=_primary_image(product),
        price=price,
        sellerId=str(product.seller_id),
        seller=seller_dto,
        saleMode=product.sale_mode if product.sale_mode in ("online", "out_of_stock", "deal_only") else "online",
        availableDeliveries=deliveries,
        pickupPoints=product.pickup_points,
        dealContacts=product.deal_contacts,
        inStock=in_stock,
        createdAt=product.created_at,
        defaultOfferId=str(offer.id) if offer else None,
    )
    return dto_json(dto)
