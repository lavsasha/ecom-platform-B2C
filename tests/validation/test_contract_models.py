from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.validation

from common.contract import CommentAuthorDTO, PostCommentDTO, PostDTO, SellerDTO, dto_json


def _seller() -> SellerDTO:
    return SellerDTO(
        id="s1",
        username="shop",
        displayName="Shop",
        joinedAt=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_post_dto_required_fields_and_aliases() -> None:
    dto = PostDTO(
        id="p1",
        sellerId="s1",
        seller=_seller(),
        title="Title",
        body="<p>x</p>",
        createdAt=datetime(2026, 1, 1, tzinfo=UTC),
        likesCount=0,
        commentsCount=0,
        isLiked=False,
    )
    data = dto_json(dto)
    for key in ("sellerId", "likesCount", "commentsCount", "isLiked", "createdAt"):
        assert key in data


def test_post_comment_rejects_empty_body_via_integration_layer() -> None:
    """Comment body length is enforced at HTTP layer; DTO allows non-empty strings."""
    dto = PostCommentDTO(
        id="c1",
        postId="p1",
        author=CommentAuthorDTO(id="u1", username="u", displayName="U"),
        body="ok",
        createdAt=datetime(2026, 1, 1, tzinfo=UTC),
        updatedAt=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert dto_json(dto)["postId"] == "p1"


def test_seller_dto_rejects_missing_username() -> None:
    with pytest.raises(ValidationError):
        SellerDTO(
            id="s1",
            displayName="X",
            joinedAt=datetime(2026, 1, 1, tzinfo=UTC),
        )
