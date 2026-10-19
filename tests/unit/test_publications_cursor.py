from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.unit

from tests.support.service_loader import load_service_module


def test_post_cursor_roundtrip() -> None:
    _, _, routes = load_service_module("publications")
    published = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    post_id = uuid.UUID("e2000001-0000-4000-8000-000000000001")
    cursor = routes.encode_cursor(published, post_id)
    decoded_at, decoded_id = routes.decode_cursor(cursor)
    assert decoded_at == published
    assert decoded_id == post_id


def test_malformed_cursor_raises() -> None:
    from common.app import BadRequestError

    _, _, routes = load_service_module("publications")
    with pytest.raises(BadRequestError):
        routes.decode_cursor("not-a-valid-cursor")
