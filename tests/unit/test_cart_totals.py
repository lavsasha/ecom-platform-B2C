from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

pytestmark = pytest.mark.unit

from tests.support.service_loader import load_service_module


def test_cart_totals_selected_items_and_promo() -> None:
    _, models, routes = load_service_module("cart")
    _totals = routes._totals
    Cart = models.Cart
    CartItem = models.CartItem
    cart = Cart(user_id=uuid.uuid4(), currency="RUB", promo_code="HANDMADE10")
    cart.items = [
        CartItem(
            cart_id=cart.id,
            product_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            quantity=2,
            price_amount=Decimal("100.00"),
            is_selected=True,
        ),
        CartItem(
            cart_id=cart.id,
            product_id=uuid.uuid4(),
            offer_id=uuid.uuid4(),
            quantity=1,
            price_amount=Decimal("50.00"),
            is_selected=False,
        ),
    ]
    totals = _totals(cart)
    assert totals.items_count == 2
    assert totals.items_quantity == 2
    assert totals.items_amount == Decimal("200.00")
    assert totals.discount_amount == Decimal("20.00")
    assert totals.total_amount == Decimal("180.00")


def test_invalid_promo_code_detection() -> None:
    _, _, routes = load_service_module("cart")
    assert "HANDMADE10" in routes.PROMO_CODES
    assert "INVALID" not in routes.PROMO_CODES
