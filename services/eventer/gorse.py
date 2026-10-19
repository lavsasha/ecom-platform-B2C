from __future__ import annotations

from typing import Any

from common.app import get_logger
from common.http import BaseHttpClient

logger = get_logger("eventer.gorse")


class GorseFeedbackClient(BaseHttpClient):
    upstream = "gorse"

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 2.0) -> None:
        super().__init__(base_url, timeout=timeout, retries=1, headers={"X-API-Key": api_key})

    async def insert_feedback(self, feedback: list[dict[str, Any]]) -> int:
        if not feedback:
            return 0
        try:
            await self.request("POST", "/api/feedback", json=feedback, retry=False)
        except Exception as exc:
            logger.warning("gorse_feedback_failed", error=str(exc), count=len(feedback))
            return 0
        return len(feedback)

    async def ping(self, path: str = "/api/health/live") -> bool:
        return await super().ping(path)
