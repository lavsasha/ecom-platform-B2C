from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from tests.support.paths import service_import


def test_product_to_document_min_price() -> None:
    with service_import("search"):
        from indexer import product_to_document

    doc = product_to_document(
        {
            "id": "b1000001-0000-4000-8000-000000000001",
            "slug": "mug",
            "title": "Кружка",
            "seller_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
            "category_id": "c1",
            "category": {"slug": "ceramics", "title": "Керамика"},
            "offers": [
                {"price_amount": "1200.00", "is_active": True},
                {"price_amount": "890.00", "is_active": True},
                {"price_amount": "1.00", "is_active": False},
            ],
            "is_active": True,
        }
    )
    assert doc["product_id"] == "b1000001-0000-4000-8000-000000000001"
    assert doc["min_price"] == 890.0
    assert doc["category_slug"] == "ceramics"
