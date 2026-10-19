from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.app import DatabaseSettings, create_app
from common.db import Database, init_tables
from common.kafka import EventProducer
from fastapi import FastAPI

import routes
from models import Base

settings = DatabaseSettings(
    service_name="orders",
    service_title="Orders service",
    database_url=os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://ecom:ecom@postgres:5432/ecom_orders",
    ),
)
db = Database(settings.database_url, echo=settings.db_echo)
producer = EventProducer(
    os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
    client_id=settings.service_name,
    enabled=os.getenv("KAFKA_ENABLED", "true").lower() == "true",
)
routes.bind_db(db)
routes.bind_producer(producer)
routes.configure(order_number_prefix=os.getenv("ORDER_NUMBER_PREFIX", "HM"))


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_tables(db.engine, Base.metadata)
    await producer.start()
    yield
    await producer.stop()
    await db.dispose()


app = create_app(
    settings,
    routers=[routes.router],
    lifespan=lifespan,
    readiness_checks={"postgres": db.healthcheck},
    auth_dev_mode=os.getenv("AUTH_DEV_MODE", "true").lower() == "true",
    auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "changeme"),
)
