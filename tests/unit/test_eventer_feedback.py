from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = pytest.mark.unit

from tests.support.paths import service_import


@pytest.mark.asyncio
async def test_gorse_feedback_only_for_eligible_events() -> None:
    with service_import("eventer"):
        from routes import EventIn, EventService, EventType, EventerSettings

    settings = EventerSettings(gorse_enabled=True)
    redis = AsyncMock()
    producer = AsyncMock()
    gorse = AsyncMock()
    gorse.insert_feedback = AsyncMock(return_value=1)
    service = EventService(settings, redis, producer, gorse)

    user_id = uuid.uuid4()
    item_id = uuid.uuid4()
    events = [
        EventIn(type=EventType.VIEW, user_id=user_id, item_id=item_id),
        EventIn(type=EventType.SEARCH, user_id=user_id, query="кружка"),
        EventIn(type=EventType.PAGE_VIEW, user_id=user_id, page="/home"),
    ]
    accepted, forwarded = await service.ingest(events)
    assert accepted == 3
    assert forwarded == 1
    gorse.insert_feedback.assert_called_once()
    feedback = gorse.insert_feedback.call_args[0][0]
    assert feedback[0]["FeedbackType"] == "view"
    assert feedback[0]["UserId"] == str(user_id)
