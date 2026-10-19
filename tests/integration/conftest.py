from __future__ import annotations

import pytest

from tests.support.postgres import postgres_reachable_sync


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: tests that need PostgreSQL")


@pytest.fixture(scope="session")
def require_postgres() -> None:
    if not postgres_reachable_sync("ecom_users"):
        pytest.skip(
            "PostgreSQL is not reachable. Start infra: docker compose up -d postgres "
            "and set TEST_POSTGRES_HOST=localhost (or run tests in the test compose service)."
        )
