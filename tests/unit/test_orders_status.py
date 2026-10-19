from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from tests.support.service_loader import load_service_module


def test_order_status_transition_graph() -> None:
    _, models, _ = load_service_module("orders")
    OrderStatus = models.OrderStatus
    STATUS_TRANSITIONS = models.STATUS_TRANSITIONS

    assert OrderStatus.PAID in STATUS_TRANSITIONS[OrderStatus.CREATED]
    assert OrderStatus.SHIPPED in STATUS_TRANSITIONS[OrderStatus.ASSEMBLING]
    assert OrderStatus.DELIVERED not in STATUS_TRANSITIONS[OrderStatus.CREATED]
    assert STATUS_TRANSITIONS[OrderStatus.DELIVERED] == set()
