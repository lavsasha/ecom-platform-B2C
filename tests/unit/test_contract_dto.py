from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.unit

from common.contract import OrderDTO, ProductDTO, SellerDTO, UserDTO, dto_json


def test_user_dto_serializes_camel_case() -> None:
    dto = UserDTO(
        id="u1",
        username="buyer",
        displayName="Buyer",
        email="b@example.com",
        createdAt=datetime(2026, 1, 1, tzinfo=UTC),
    )
    data = dto_json(dto)
    assert "displayName" in data
    assert "display_name" not in data
    assert data["email"] == "b@example.com"


def test_product_dto_accepts_alias_population() -> None:
    seller = SellerDTO(
        id="s1",
        username="shop",
        displayName="Shop",
        joinedAt=datetime(2026, 1, 1, tzinfo=UTC),
    )
    dto = ProductDTO(
        id="p1",
        title="Item",
        image="https://example/img.jpg",
        price=100,
        sellerId="s1",
        seller=seller,
        createdAt=datetime(2026, 1, 1, tzinfo=UTC),
    )
    data = dto_json(dto)
    assert data["sellerId"] == "s1"
    assert data["saleMode"] == "online"


def test_order_dto_status_literal() -> None:
    seller = SellerDTO(
        id="s1",
        username="shop",
        displayName="Shop",
        joinedAt=datetime(2026, 1, 1, tzinfo=UTC),
    )
    dto = OrderDTO(
        id="o1",
        createdAt=datetime(2026, 1, 1, tzinfo=UTC),
        status="paid",
        seller=seller,
        items=[],
        delivery="cdek",
        total=1000,
    )
    assert dto_json(dto)["status"] == "paid"
