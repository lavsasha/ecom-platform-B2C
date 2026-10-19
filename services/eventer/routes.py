from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from common.app import KafkaSettings, get_logger
from common.kafka import EventProducer, Topics
from gorse import GorseFeedbackClient


class EventerSettings(KafkaSettings):
    service_name: str = "eventer"
    service_title: str = "Eventer service"
    redis_url: str = "redis://redis:6379/0"
    event_stream_key: str = "events:stream"
    event_stream_maxlen: int = 100_000
    gorse_url: str = "http://gorse:8088"
    gorse_api_key: str = "gorseApiKeyForLocalDevOnly"
    gorse_enabled: bool = True

router = APIRouter(prefix="/api/v1")
logger = get_logger("eventer.service")
_service: "EventService | None" = None


def bind_service(service: "EventService") -> None:
    global _service
    _service = service


def get_event_service() -> "EventService":
    assert _service is not None
    return _service


EventServiceDep = Annotated["EventService", Depends(get_event_service)]


class EventType(StrEnum):
    VIEW = "view"
    ADD_TO_CART = "add_to_cart"
    REMOVE_FROM_CART = "remove_from_cart"
    FAVORITE = "favorite"
    PURCHASE = "purchase"
    SEARCH = "search"
    SUBSCRIBE = "subscribe"
    PAGE_VIEW = "page_view"


FEEDBACK_EVENTS: frozenset[EventType] = frozenset(
    {
        EventType.VIEW,
        EventType.ADD_TO_CART,
        EventType.FAVORITE,
        EventType.PURCHASE,
        EventType.SUBSCRIBE,
    }
)


class EventIn(BaseModel):
    type: EventType
    user_id: uuid.UUID | None = None
    anonymous_id: str | None = Field(default=None, max_length=64)
    item_id: uuid.UUID | None = Field(default=None, description="Product the event is about")
    page: str | None = Field(default=None, max_length=120)
    query: str | None = Field(default=None, max_length=300)
    value: float | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EventBatchIn(BaseModel):
    events: list[EventIn] = Field(min_length=1, max_length=50)


class EventAccepted(BaseModel):
    accepted: int
    forwarded_to_gorse: int


class EventService:
    def __init__(
        self,
        settings: EventerSettings,
        redis: Redis,
        producer: EventProducer,
        gorse: GorseFeedbackClient,
    ) -> None:
        self.settings = settings
        self.redis = redis
        self.producer = producer
        self.gorse = gorse

    async def ingest(self, events: list[EventIn]) -> tuple[int, int]:
        feedback = []
        for event in events:
            payload = self._serialise(event)
            await self._write_to_redis(payload)
            await self.producer.send(Topics.USER_EVENTS, payload, key=self._actor(event))
            entry = self._to_gorse_feedback(event)
            if entry is not None:
                feedback.append(entry)

        forwarded = 0
        if feedback and self.settings.gorse_enabled:
            forwarded = await self.gorse.insert_feedback(feedback)
        return len(events), forwarded

    async def _write_to_redis(self, payload: dict) -> None:
        stream_key = self.settings.event_stream_key
        maxlen = self.settings.event_stream_maxlen
        try:
            await self.redis.xadd(
                stream_key,
                {"payload": json.dumps(payload, default=str)},
                maxlen=maxlen,
                approximate=True,
            )
        except Exception as exc:
            logger.warning("redis_write_failed", error=str(exc))

    @staticmethod
    def _actor(event: EventIn) -> str:
        return str(event.user_id) if event.user_id else (event.anonymous_id or "anonymous")

    def _serialise(self, event: EventIn) -> dict:
        payload = event.model_dump(mode="json")
        payload["actor_id"] = self._actor(event)
        return payload

    def _to_gorse_feedback(self, event: EventIn) -> dict | None:
        if event.type not in FEEDBACK_EVENTS or event.item_id is None or event.user_id is None:
            return None
        return {
            "FeedbackType": event.type.value,
            "UserId": str(event.user_id),
            "ItemId": str(event.item_id),
            "Timestamp": event.occurred_at.isoformat(),
        }


@router.post("/events", response_model=EventAccepted, status_code=status.HTTP_202_ACCEPTED, tags=["events"])
async def ingest_event(payload: EventIn, service: EventServiceDep) -> EventAccepted:
    accepted, forwarded = await service.ingest([payload])
    return EventAccepted(accepted=accepted, forwarded_to_gorse=forwarded)


@router.post(
    "/events/batch",
    response_model=EventAccepted,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of events",
    description="The storefront buffers events and flushes them on navigation or unload.",
    tags=["events"],
)
async def ingest_batch(payload: EventBatchIn, service: EventServiceDep) -> EventAccepted:
    accepted, forwarded = await service.ingest(payload.events)
    return EventAccepted(accepted=accepted, forwarded_to_gorse=forwarded)
