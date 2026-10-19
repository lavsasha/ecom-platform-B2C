"""FastAPI app factory, settings, errors, auth, logging, request middleware."""

from __future__ import annotations

import logging
import sys
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
import structlog
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# --- context ---------------------------------------------------------------------

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
REQUEST_ID_HEADER = "X-Request-Id"
USER_ID_HEADER = "X-User-Id"


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str | None:
    return _request_id.get()


# --- settings --------------------------------------------------------------------


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )
    service_name: str = "service"
    service_title: str = "Service"
    environment: str = "local"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = True


class DatabaseSettings(BaseServiceSettings):
    database_url: str = ""
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 5


class KafkaSettings(BaseServiceSettings):
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_enabled: bool = True
    kafka_client_id: str = "ecom-platform"


# --- logging ---------------------------------------------------------------------


def _add_request_id(_: Any, __: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    rid = get_request_id()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging(*, service_name: str, level: str = "INFO", json_output: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
    for noisy in ("uvicorn.access", "aiokafka", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    renderer: structlog.types.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _add_request_id,
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(service=service_name)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)  # type: ignore[no-any-return]


# --- errors ----------------------------------------------------------------------

logger = get_logger("app")


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"
    message: str = "Internal server error"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.details = details or {}
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"
    message = "Bad request"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication required"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"
    message = "Access denied"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"
    message = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"
    message = "Conflicting state"


class UpstreamError(AppError):
    status_code = 502
    code = "upstream_error"
    message = "Upstream service failed"

    def __init__(
        self,
        upstream: str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.upstream = upstream
        super().__init__(message or f"Upstream {upstream} failed", details=details)


class UpstreamUnavailableError(UpstreamError):
    status_code = 503
    code = "upstream_unavailable"


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def _error_json(status: int, code: str, message: str, details: dict[str, Any]) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=code, message=message, details=details, request_id=get_request_id()
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_json(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error_json(422, "validation_error", "Request validation failed", {"errors": exc.errors()})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error_json(exc.status_code, f"http_{exc.status_code}", str(exc.detail), {})

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled", error=str(exc))
        return _error_json(500, "internal_error", "Internal server error", {})


# --- auth ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: uuid.UUID


class AuthConfig:
    dev_mode: bool = True
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    auth_cookie_name: str = "auth-token"


def configure_auth(
    *,
    dev_mode: bool,
    jwt_secret: str,
    jwt_algorithm: str = "HS256",
    auth_cookie_name: str = "auth-token",
) -> None:
    AuthConfig.dev_mode = dev_mode
    AuthConfig.jwt_secret = jwt_secret
    AuthConfig.jwt_algorithm = jwt_algorithm
    AuthConfig.auth_cookie_name = auth_cookie_name


def _user_id_from_access_token(token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            AuthConfig.jwt_secret,
            algorithms=[AuthConfig.jwt_algorithm],
        )
        return uuid.UUID(str(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def optional_user(request: Request) -> CurrentUser | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        user_id = _user_id_from_access_token(auth.split(" ", 1)[1].strip())
        if user_id is None:
            raise UnauthorizedError("Invalid access token")
        return CurrentUser(id=user_id)
    if AuthConfig.dev_mode:
        raw = request.headers.get(USER_ID_HEADER)
        if raw:
            try:
                return CurrentUser(id=uuid.UUID(raw))
            except ValueError as exc:
                raise UnauthorizedError(f"Malformed {USER_ID_HEADER}") from exc
    cookie_name = AuthConfig.auth_cookie_name
    if cookie_name:
        token = request.cookies.get(cookie_name)
        if token:
            user_id = _user_id_from_access_token(token)
            if user_id is not None:
                return CurrentUser(id=user_id)
    return None


def required_user(user: Annotated[CurrentUser | None, Depends(optional_user)]) -> CurrentUser:
    if user is None:
        raise UnauthorizedError()
    return user


OptionalUser = Annotated[CurrentUser | None, Depends(optional_user)]
RequiredUser = Annotated[CurrentUser, Depends(required_user)]


# --- middleware ------------------------------------------------------------------

_SILENT = {"/healthz", "/readyz"}


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        set_request_id(rid)
        structlog.contextvars.bind_contextvars(request_id=rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[REQUEST_ID_HEADER] = rid
        if request.url.path not in _SILENT:
            get_logger("access").info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round((time.perf_counter() - started) * 1000, 2),
            )
        return response


# --- app factory -----------------------------------------------------------------

ReadinessCheck = Callable[[], Awaitable[bool]]
Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    settings: BaseServiceSettings,
    *,
    routers: Sequence[APIRouter] = (),
    lifespan: Lifespan | None = None,
    readiness_checks: dict[str, ReadinessCheck] | None = None,
    cors_origins: Sequence[str] = ("*",),
    auth_dev_mode: bool = True,
    auth_jwt_secret: str = "changeme",
    auth_cookie_name: str = "auth-token",
) -> FastAPI:
    configure_logging(
        service_name=settings.service_name,
        level=settings.log_level,
        json_output=settings.log_json,
    )
    configure_auth(
        dev_mode=auth_dev_mode,
        jwt_secret=auth_jwt_secret,
        auth_cookie_name=auth_cookie_name,
    )
    checks = readiness_checks or {}

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        if lifespan is None:
            yield
        else:
            async with lifespan(app):
                yield

    app = FastAPI(
        title=settings.service_title,
        version="0.1.0",
        debug=settings.debug,
        lifespan=_lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID_HEADER],
    )
    register_exception_handlers(app)

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": settings.service_name}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> dict[str, Any]:
        results = {name: await fn() for name, fn in checks.items()}
        return {
            "status": "ok" if all(results.values()) else "degraded",
            "service": settings.service_name,
            "dependencies": results,
        }

    for router in routers:
        app.include_router(router)
    return app
