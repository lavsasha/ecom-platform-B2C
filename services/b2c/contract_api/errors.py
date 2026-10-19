from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        *,
        http_status: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.http_status = http_status
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validation_error(message: str, **details: Any) -> ApiError:
    return ApiError(http_status=400, code="VALIDATION_ERROR", message=message, details=details)


def unauthorized(message: str = "Требуется авторизация") -> ApiError:
    return ApiError(http_status=401, code="UNAUTHORIZED", message=message)


def forbidden(message: str = "Доступ запрещён") -> ApiError:
    return ApiError(http_status=403, code="FORBIDDEN", message=message)


def not_found(message: str = "Не найдено") -> ApiError:
    return ApiError(http_status=404, code="NOT_FOUND", message=message)


def conflict(message: str) -> ApiError:
    return ApiError(http_status=409, code="CONFLICT", message=message)


def server_error(message: str = "Внутренняя ошибка") -> ApiError:
    return ApiError(http_status=500, code="SERVER_ERROR", message=message)
