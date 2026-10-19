from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.support.paths import postgres_dsn


async def postgres_reachable(database: str = "ecom_users") -> bool:
    url = postgres_dsn(database)
    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
    finally:
        await engine.dispose()


def postgres_reachable_sync(database: str = "ecom_users") -> bool:
    return asyncio.run(postgres_reachable(database))
