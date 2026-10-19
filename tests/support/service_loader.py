from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

from tests.support.paths import ROOT, configure_service_env, service_import


def _reset_shared_sqlalchemy_metadata() -> None:
    """Services share ``common.db.Base``; clear ORM state before loading another service."""
    from common.db import Base

    Base.metadata.clear()
    Base.registry.dispose()


def load_service_module(
    service: str, module_name: str = "main"
) -> tuple[ModuleType, ModuleType, ModuleType]:
    """Import service ``main``, ``models``, and ``routes`` in one isolated load."""
    configure_service_env(service)
    _reset_shared_sqlalchemy_metadata()
    service_dir = ROOT / "services" / service
    file_path = service_dir / f"{module_name}.py"
    qualname = f"ecom_test_{service}_{module_name}"
    models_snapshot: ModuleType | None = None
    routes_snapshot: ModuleType | None = None
    with service_import(service):
        spec = importlib.util.spec_from_file_location(qualname, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualname] = module
        spec.loader.exec_module(module)
        models_path = service_dir / "models.py"
        if not models_path.exists():
            raise ImportError(f"Service {service} has no models.py for DB integration tests")
        import models

        models_snapshot = models
        routes_path = service_dir / "routes.py"
        if routes_path.exists():
            import routes

            routes_snapshot = routes
        else:
            routes_snapshot = module
    assert models_snapshot is not None and routes_snapshot is not None
    return module, models_snapshot, routes_snapshot
