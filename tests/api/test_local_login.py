# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the POST /api/auth/login local-authentication endpoint."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from flydesk.api.auth import get_local_user_repo, router as auth_router
from flydesk.auth.password import hash_password


# ---------------------------------------------------------------------------
# Fake user for testing
# ---------------------------------------------------------------------------

@dataclass
class FakeUser:
    id: str = "user-1"
    username: str = "admin"
    email: str = "admin@example.com"
    display_name: str = "Admin"
    password_hash: str = ""
    role: str = "admin"
    is_active: bool = True


class FakeLocalUserRepo:
    """In-memory stand-in for LocalUserRepository."""

    def __init__(self, users: dict[str, FakeUser] | None = None) -> None:
        self._users = users or {}

    async def get_by_username(self, username: str) -> FakeUser | None:
        return self._users.get(username)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _make_app(repo: FakeLocalUserRepo) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router)
    app.dependency_overrides[get_local_user_repo] = lambda: repo
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_login_success():
    pw_hash = hash_password("secret123")
    user = FakeUser(password_hash=pw_hash)
    repo = FakeLocalUserRepo({"admin": user})
    app = _make_app(repo)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret123"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 86400

    # Cookie should be set
    cookie = resp.cookies.get("flydesk_token")
    assert cookie is not None
    assert cookie == data["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password():
    pw_hash = hash_password("secret123")
    user = FakeUser(password_hash=pw_hash)
    repo = FakeLocalUserRepo({"admin": user})
    app = _make_app(repo)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrongpass"},
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_login_unknown_user():
    repo = FakeLocalUserRepo({})
    app = _make_app(repo)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "nobody", "password": "whatever"},
        )

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid username or password"


@pytest.mark.asyncio
async def test_login_disabled_account():
    pw_hash = hash_password("secret123")
    user = FakeUser(password_hash=pw_hash, is_active=False)
    repo = FakeLocalUserRepo({"admin": user})
    app = _make_app(repo)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret123"},
        )

    assert resp.status_code == 403
    assert resp.json()["detail"] == "Account is disabled"


@pytest.mark.asyncio
async def test_login_jwt_is_decodable():
    """The returned token should be a valid local JWT."""
    import jwt as pyjwt

    from flydesk.auth.jwt_local import LOCAL_ISSUER
    from flydesk.config import get_config

    pw_hash = hash_password("secret123")
    user = FakeUser(password_hash=pw_hash)
    repo = FakeLocalUserRepo({"admin": user})
    app = _make_app(repo)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "secret123"},
        )

    token = resp.json()["access_token"]
    config = get_config()
    claims = pyjwt.decode(
        token,
        config.effective_jwt_secret,
        algorithms=["HS256"],
        issuer=LOCAL_ISSUER,
    )
    assert claims["sub"] == "user-1"
    assert claims["email"] == "admin@example.com"
    assert claims["name"] == "Admin"
    assert claims["roles"] == ["admin"]
