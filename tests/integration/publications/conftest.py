from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from common.db import init_tables
from tests.support.service_loader import load_service_module

_pub, _pub_models, _ = load_service_module("publications")
app = _pub.app
db = _pub.db
Post = _pub_models.Post

POST_ID = uuid.UUID("f0000001-0000-4000-8000-000000000099")


@pytest.fixture(autouse=True)
async def ensure_demo_post() -> None:
    await init_tables(db.engine, _pub_models.Base.metadata)
    async with db.session_factory() as session:
        existing = await session.get(Post, POST_ID)
        if existing is None:
            session.add(
                Post(
                    id=POST_ID,
                    slug=f"test-post-{POST_ID.hex[:8]}",
                    seller_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1"),
                    title="Integration post",
                    body="body",
                    published_at=datetime.now(UTC),
                    is_published=True,
                )
            )
            await session.commit()


@pytest.fixture
async def publications_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.fixture(autouse=True)
def _require_postgres(require_postgres: None) -> None:
    return None
