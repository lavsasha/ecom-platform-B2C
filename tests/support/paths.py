from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
LIBS = ROOT / "libs"
_SERVICE_MODULE_NAMES = frozenset(
    {"main", "routes", "models", "dto", "kafka", "indexer", "gorse", "pages", "facade", "clients", "config"}
)


def postgres_dsn(database: str, host: str | None = None) -> str:
    host = host or os.getenv("TEST_POSTGRES_HOST", "localhost")
    user = os.getenv("POSTGRES_USER", "ecom")
    password = os.getenv("POSTGRES_PASSWORD", "ecom")
    port = os.getenv("TEST_POSTGRES_PORT", "5432")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"


@contextmanager
def service_import(service: str) -> Iterator[Path]:
    """Put one microservice directory on sys.path (flat imports: models, routes, main)."""
    service_dir = ROOT / "services" / service
    libs_path = str(LIBS)
    svc_path = str(service_dir)
    prev_path = sys.path.copy()
    prev_modules = {name: sys.modules[name] for name in _SERVICE_MODULE_NAMES if name in sys.modules}
    for name in prev_modules:
        del sys.modules[name]
    for entry in list(sys.path):
        if "/services/" in entry.replace("\\", "/"):
            sys.path.remove(entry)
    if libs_path not in sys.path:
        sys.path.insert(0, libs_path)
    sys.path.insert(0, svc_path)
    try:
        yield service_dir
    finally:
        for name in list(sys.modules):
            if name in _SERVICE_MODULE_NAMES and name not in prev_modules:
                del sys.modules[name]
        sys.modules.update(prev_modules)
        sys.path[:] = prev_path


def configure_service_env(service: str) -> None:
    os.environ.setdefault("AUTH_DEV_MODE", "true")
    os.environ.setdefault("AUTH_JWT_SECRET", "test-secret")
    os.environ.setdefault("KAFKA_ENABLED", "false")
    db_map = {
        "users": "ecom_users",
        "cart": "ecom_cart",
        "orders": "ecom_orders",
        "publications": "ecom_publications",
        "goods": "ecom_goods",
    }
    if service in db_map:
        env_key = f"TEST_{service.upper()}_DATABASE_URL"
        os.environ.setdefault("DATABASE_URL", os.getenv(env_key, postgres_dsn(db_map[service])))
