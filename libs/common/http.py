"""HTTP client for service-to-service calls."""

from __future__ import annotations

import asyncio
from typing import Any, Self

import httpx

from common.app import (
    REQUEST_ID_HEADER,
    AppError,
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    UpstreamError,
    UpstreamUnavailableError,
    get_logger,
    get_request_id,
)

logger = get_logger("http")
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "PUT", "DELETE"})
_STATUS: dict[int, type[AppError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    422: BadRequestError,
}


class BaseHttpClient:
    upstream: str = "upstream"

    def __init__(
        self,
        base_url: str,
        *,
        upstream: str | None = None,
        timeout: float = 2.0,
        retries: int = 2,
        backoff: float = 0.1,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.upstream = upstream or self.upstream
        self.retries = max(retries, 0)
        self.backoff = backoff
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            headers=headers or {},
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ping(self, path: str = "/healthz") -> bool:
        try:
            r = await self._client.get(path, timeout=1.0)
        except httpx.HTTPError:
            return False
        return r.status_code < 500

    async def request(
        self, method: str, path: str, *, retry: bool | None = None, **kwargs: Any
    ) -> httpx.Response:
        should = retry if retry is not None else method.upper() in SAFE_METHODS
        attempts = self.retries + 1 if should else 1
        headers = dict(kwargs.pop("headers", {}) or {})
        rid = get_request_id()
        if rid:
            headers.setdefault(REQUEST_ID_HEADER, rid)
        last: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._client.request(method, path, headers=headers, **kwargs)
            except httpx.HTTPError as exc:
                last = exc
            else:
                if response.status_code < 500:
                    self._raise(response)
                    return response
                last = UpstreamError(self.upstream, details={"status": response.status_code})
            if attempt < attempts - 1:
                await asyncio.sleep(self.backoff * (2**attempt))
        if isinstance(last, UpstreamError):
            raise last
        raise UpstreamUnavailableError(self.upstream)

    def _raise(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        cls = _STATUS.get(response.status_code)
        details = {"status": response.status_code, "upstream": self.upstream}
        if cls is None:
            raise UpstreamError(self.upstream, details=details)
        raise cls(details=details)

    async def get_json(self, path: str, **kwargs: Any) -> Any:
        return (await self.request("GET", path, **kwargs)).json()

    async def get_json_or_none(self, path: str, **kwargs: Any) -> Any | None:
        try:
            return await self.get_json(path, **kwargs)
        except NotFoundError:
            return None

    async def post_json(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        r = await self.request("POST", path, json=json, **kwargs)
        return None if r.status_code == 204 else r.json()

    async def put_json(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        r = await self.request("PUT", path, json=json, **kwargs)
        return None if r.status_code == 204 else r.json()

    async def patch_json(self, path: str, json: Any = None, **kwargs: Any) -> Any:
        r = await self.request("PATCH", path, json=json, **kwargs)
        return None if r.status_code == 204 else r.json()

    async def delete(self, path: str, **kwargs: Any) -> None:
        await self.request("DELETE", path, **kwargs)
