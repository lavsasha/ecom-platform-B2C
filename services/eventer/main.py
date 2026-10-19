from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.app import create_app
from common.kafka import EventProducer
from fastapi import FastAPI
from redis.asyncio import Redis

import routes
from gorse import GorseFeedbackClient

settings = routes.EventerSettings(
    redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    gorse_url=os.getenv("GORSE_URL", "http://gorse:8088"),
    gorse_api_key=os.getenv("GORSE_API_KEY", "gorseApiKeyForLocalDevOnly"),
    gorse_enabled=os.getenv("GORSE_ENABLED", "true").lower() == "true",
    kafka_bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
    kafka_enabled=os.getenv("KAFKA_ENABLED", "true").lower() == "true",
)
redis = Redis.from_url(settings.redis_url, decode_responses=True)
producer = EventProducer(
    settings.kafka_bootstrap_servers,
    client_id=settings.service_name,
    enabled=settings.kafka_enabled,
)
gorse = GorseFeedbackClient(settings.gorse_url, settings.gorse_api_key)
routes.bind_service(routes.EventService(settings, redis, producer, gorse))


async def redis_healthcheck() -> bool:
    try:
        return bool(await redis.ping())
    except Exception:
        return False


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await producer.start()
    yield
    await producer.stop()
    await gorse.aclose()
    await redis.aclose()


app = create_app(
    settings,
    routers=[routes.router],
    lifespan=lifespan,
    readiness_checks={
        "redis": redis_healthcheck,
        "gorse": gorse.ping,
    },
    auth_dev_mode=os.getenv("AUTH_DEV_MODE", "true").lower() == "true",
    auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "changeme"),
)
