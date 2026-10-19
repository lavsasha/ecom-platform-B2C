from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Request

from config import B2CSettings
from contract_api.errors import unauthorized


def issue_token(settings: B2CSettings, user_id: uuid.UUID) -> str:
    exp = datetime.now(UTC) + timedelta(seconds=settings.auth_access_ttl_seconds)
    return jwt.encode(
        {"sub": str(user_id), "exp": exp},
        settings.auth_jwt_secret,
        algorithm=settings.auth_jwt_algorithm,
    )


def user_id_from_request(request: Request, settings: B2CSettings) -> uuid.UUID | None:
    if settings.auth_dev_mode:
        raw = request.headers.get("X-User-Id")
        if raw:
            try:
                return uuid.UUID(raw)
            except ValueError:
                raise unauthorized("Некорректный X-User-Id")
    token = request.cookies.get(settings.auth_cookie_name)
    if not token:
        return None
    try:
        payload = jwt.decode(
            token,
            settings.auth_jwt_secret,
            algorithms=[settings.auth_jwt_algorithm],
        )
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, ValueError, KeyError):
        return None


def require_user_id(request: Request, settings: B2CSettings) -> uuid.UUID:
    uid = user_id_from_request(request, settings)
    if uid is None:
        raise unauthorized()
    return uid
