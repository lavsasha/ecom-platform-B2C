from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.app import BaseServiceSettings, create_app
from fastapi import FastAPI

import indexer
import routes

settings = BaseServiceSettings(
    service_name="search",
    service_title="Search service",
)
consumer = indexer.build_consumer()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await consumer.start()
    yield
    await consumer.stop()
    await indexer.aclose_meili()


app = create_app(
    settings,
    routers=[routes.router],
    lifespan=lifespan,
    auth_dev_mode=os.getenv("AUTH_DEV_MODE", "true").lower() == "true",
    auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "changeme"),
)
