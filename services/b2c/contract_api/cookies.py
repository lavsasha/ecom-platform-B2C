from __future__ import annotations

from fastapi import Response

from config import B2CSettings


def set_auth_cookie(response: Response, settings: B2CSettings, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        max_age=settings.auth_access_ttl_seconds,
    )


def clear_auth_cookie(response: Response, settings: B2CSettings) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value="",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        path="/",
        max_age=0,
    )
