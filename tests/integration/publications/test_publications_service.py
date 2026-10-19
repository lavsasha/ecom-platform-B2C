from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

POST_ID = "f0000001-0000-4000-8000-000000000099"


@pytest.mark.asyncio
async def test_comments_and_likes(publications_client: AsyncClient) -> None:
    user_id = uuid.uuid4()
    post_id = POST_ID

    create = await publications_client.post(
        f"/api/v1/posts/{post_id}/comments",
        params={"user_id": str(user_id)},
        json={"body": "First comment"},
    )
    assert create.status_code == 201
    comment_id = create.json()["id"]

    listing = await publications_client.get(f"/api/v1/posts/{post_id}/comments")
    assert listing.status_code == 200
    assert any(item["id"] == comment_id for item in listing.json()["items"])

    update = await publications_client.patch(
        f"/api/v1/comments/{comment_id}",
        params={"user_id": str(user_id)},
        json={"body": "Updated"},
    )
    assert update.status_code == 200
    assert update.json()["body"] == "Updated"

    delete = await publications_client.delete(
        f"/api/v1/comments/{comment_id}",
        params={"user_id": str(user_id)},
    )
    assert delete.status_code == 200

    like = await publications_client.post(
        f"/api/v1/posts/{post_id}/like",
        params={"user_id": str(user_id)},
    )
    assert like.status_code == 200
    assert like.json()["isLiked"] is True

    unlike = await publications_client.delete(
        f"/api/v1/posts/{post_id}/like",
        params={"user_id": str(user_id)},
    )
    assert unlike.json()["isLiked"] is False
