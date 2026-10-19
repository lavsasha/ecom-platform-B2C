from __future__ import annotations

import os
import uuid
from typing import Any

from common.app import get_logger
from common.db import Database
from common.kafka import ConsumerRunner, Topics

import routes

logger = get_logger("goods.consumer")
_db: Database | None = None


def bind_db(database: Database) -> None:
    global _db
    _db = database


async def handle_goods_changed(topic: str, payload: dict[str, Any]) -> None:
    assert _db is not None
    action = payload.get("action")
    async with _db.session_factory() as session:
        if action == "upserted" and payload.get("product"):
            product = await routes.upsert_from_event(session, payload["product"])
            await session.commit()
            logger.info("product_upserted", topic=topic, product_id=str(product.id))
        elif action == "deleted" and payload.get("product_id"):
            removed = await routes.delete_product(session, uuid.UUID(str(payload["product_id"])))
            await session.commit()
            logger.info("product_deleted", topic=topic, found=removed)
        else:
            logger.warning("unknown_goods_event", topic=topic, action=action)


def build_consumer() -> ConsumerRunner:
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    enabled = os.getenv("KAFKA_ENABLED", "true").lower() == "true"
    group_id = os.getenv("KAFKA_CONSUMER_GROUP", "goods-read-model")
    return ConsumerRunner(
        bootstrap,
        topics=[Topics.GOODS_CHANGED],
        group_id=group_id,
        handler=handle_goods_changed,
        enabled=enabled,
    )
