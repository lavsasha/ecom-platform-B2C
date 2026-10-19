from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_register_login_and_batch(users_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    email = f"test_{suffix}@example.com"
    username = f"user_{suffix}"

    reg = await users_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secret123",
            "username": username,
            "display_name": "Test User",
        },
    )
    assert reg.status_code == 201
    user = reg.json()["user"]
    user_id = user["id"]

    login = await users_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "secret123"},
    )
    assert login.status_code == 200
    assert login.json()["user"]["email"] == email

    batch = await users_client.post("/api/v1/users/batch", json={"ids": [user_id]})
    assert batch.status_code == 200
    assert len(batch.json()["items"]) == 1
    assert batch.json()["items"][0]["username"] == username
