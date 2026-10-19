"""Kafka helpers."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, Final

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from common.app import get_logger

logger = get_logger("kafka")

MessageHandler = Callable[[str, dict[str, Any]], Awaitable[None]]


class Topics:
    GOODS_CHANGED: Final = "goods.changed"
    PUBLICATIONS_CHANGED: Final = "publications.changed"
    USER_EVENTS: Final = "user.events"
    ORDERS_CHANGED: Final = "orders.changed"


class EventProducer:
    def __init__(
        self,
        bootstrap_servers: str,
        *,
        client_id: str = "ecom-platform",
        enabled: bool = True,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._enabled = enabled
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if not self._enabled:
            return
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            value_serializer=lambda value: json.dumps(value, default=str).encode(),
            key_serializer=lambda key: key.encode() if key is not None else None,
            enable_idempotence=True,
        )
        await self._producer.start()

    async def stop(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None

    async def send(self, topic: str, value: dict[str, Any], *, key: str | None = None) -> None:
        if self._producer is None:
            return
        try:
            await self._producer.send_and_wait(topic, value=value, key=key)
        except Exception as exc:
            logger.warning("kafka_send_failed", topic=topic, error=str(exc))


class ConsumerRunner:
    def __init__(
        self,
        bootstrap_servers: str,
        *,
        topics: list[str],
        group_id: str,
        handler: MessageHandler,
        enabled: bool = True,
    ) -> None:
        self._bootstrap_servers = bootstrap_servers
        self._topics = topics
        self._group_id = group_id
        self._handler = handler
        self._enabled = enabled
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if not self._enabled:
            return
        self._task = asyncio.create_task(self._run(), name=f"consumer-{self._group_id}")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stopping.is_set():
            consumer = AIOKafkaConsumer(
                *self._topics,
                bootstrap_servers=self._bootstrap_servers,
                group_id=self._group_id,
                enable_auto_commit=True,
                auto_offset_reset="earliest",
                value_deserializer=lambda raw: json.loads(raw.decode()),
            )
            try:
                await consumer.start()
                async for message in consumer:
                    try:
                        await self._handler(message.topic, message.value)
                    except Exception as exc:
                        logger.warning("kafka_handler_failed", error=str(exc))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("kafka_consumer_error", error=str(exc))
                await asyncio.sleep(5)
            finally:
                with contextlib.suppress(Exception):
                    await consumer.stop()
