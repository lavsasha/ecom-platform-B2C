from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.unit

from tests.support.paths import service_import


def test_post_mapper_camel_case_and_is_liked_default() -> None:
    with service_import("b2c"):
        from mappers import post_from_upstream

    seller = {
        "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
        "username": "maria",
        "display_name": "Мария",
        "created_at": datetime(2026, 1, 1, tzinfo=UTC),
    }
    raw = {
        "id": "e2000001-0000-4000-8000-000000000001",
        "seller_id": seller["id"],
        "title": "Пост",
        "body": "<p>html</p>",
        "likes_count": 3,
        "comments_count": 2,
        "published_at": "2026-02-01T10:00:00Z",
    }
    post = post_from_upstream(raw, seller, [])
    assert post["likesCount"] == 3
    assert post["commentsCount"] == 2
    assert post["seller"]["displayName"] == "Мария"
    assert post["isLiked"] is False


def test_comment_mapper_is_own_flag() -> None:
    with service_import("b2c"):
        from mappers import comment_from_upstream

    viewer = uuid.UUID("11111111-1111-1111-1111-111111111111")
    raw = {
        "id": "e3000001-0000-4000-8000-000000000001",
        "post_id": "e2000001-0000-4000-8000-000000000001",
        "user_id": str(viewer),
        "body": "Текст",
        "created_at": "2026-01-01T12:00:00Z",
        "updated_at": "2026-01-01T12:00:00Z",
    }
    author = {"id": str(viewer), "username": "anna", "displayName": "Anna"}
    out = comment_from_upstream(raw, author, viewer)
    assert out["isOwn"] is True
    assert out["author"]["username"] == "anna"
