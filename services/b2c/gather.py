from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


class SectionStatus(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    UNAVAILABLE = "unavailable"


@dataclass(slots=True)
class Section(Generic[T]):
    status: SectionStatus
    items: T | None = None
    data: Any = None


async def gather_sections(
    loaders: dict[str, Callable[[], Awaitable[Any]]],
) -> dict[str, Section[Any]]:
    async def _wrap(name: str, fn: Callable[[], Awaitable[Any]]) -> tuple[str, Section[Any]]:
        try:
            result = fn()
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return name, Section(status=SectionStatus.EMPTY, data=None, items=None)
            if isinstance(result, list) and len(result) == 0:
                return name, Section(status=SectionStatus.EMPTY, items=[])
            if isinstance(result, list):
                return name, Section(status=SectionStatus.OK, items=result)
            return name, Section(status=SectionStatus.OK, data=result)
        except Exception:
            return name, Section(status=SectionStatus.UNAVAILABLE, data=None, items=None)

    pairs = await asyncio.gather(*[_wrap(k, fn) for k, fn in loaders.items()])
    return dict(pairs)
