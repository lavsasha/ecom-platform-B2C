from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from common.app import DatabaseSettings, create_app
from common.db import Database, init_tables
from fastapi import FastAPI

import routes
from models import Base

settings = DatabaseSettings(
    service_name="users",
    service_title="Users service",
    database_url=os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://ecom:ecom@postgres:5432/ecom_users",
    ),
)
db = Database(settings.database_url, echo=settings.db_echo)
routes.bind_db(db)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await init_tables(db.engine, Base.metadata)
    yield
    await db.dispose()


app = create_app(
    settings,
    routers=[routes.router],
    lifespan=lifespan,
    readiness_checks={"postgres": db.healthcheck},
    auth_dev_mode=os.getenv("AUTH_DEV_MODE", "true").lower() == "true",
    auth_jwt_secret=os.getenv("AUTH_JWT_SECRET", "changeme"),
)
