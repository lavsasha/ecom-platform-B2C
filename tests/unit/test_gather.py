from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

from tests.support.paths import service_import

with service_import("b2c"):
    from gather import SectionStatus, gather_sections


@pytest.mark.asyncio
async def test_gather_sections_awaits_coroutines() -> None:
    async def load_items() -> list[str]:
        return ["a"]

    sections = await gather_sections({"items": load_items})
    assert sections["items"].status == SectionStatus.OK
    assert sections["items"].items == ["a"]


@pytest.mark.asyncio
async def test_gather_sections_accepts_plain_values() -> None:
    sections = await gather_sections(
        {
            "items": lambda: [],
            "meta": lambda: {"k": 1},
        }
    )
    assert sections["items"].status == SectionStatus.EMPTY
    assert sections["meta"].status == SectionStatus.OK
    assert sections["meta"].data == {"k": 1}


@pytest.mark.asyncio
async def test_gather_sections_unavailable_on_exception() -> None:
    async def boom() -> None:
        raise RuntimeError("upstream down")

    sections = await gather_sections({"broken": boom})
    assert sections["broken"].status == SectionStatus.UNAVAILABLE
