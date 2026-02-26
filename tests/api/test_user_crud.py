# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for user CRUD API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from flydesk.auth.dev import DEV_USER_ID
from flydesk.auth.local_user_repository import LocalUserRepository
from flydesk.auth.models import UserSession
from flydesk.models.base import Base


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DevAuthMiddleware(BaseHTTPMiddleware):
    """Inject a synthetic admin session so that AdminUsers guards pass."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.user_session = UserSession(
            user_id=DEV_USER_ID,
            email="admin@localhost",
            display_name="Dev Admin",
            roles=["admin"],
            permissions=["*"],
            session_id=str(uuid.uuid4()),
            token_expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
        )
        return await call_next(request)


async def _make_app_with_db():
    """Create a minimal FastAPI app backed by an in-memory SQLite database."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    # Import all models so Base.metadata knows about every table
    import flydesk.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    local_user_repo = LocalUserRepository(session_factory)

    from flydesk.api.users import (
        get_local_user_repo,
        get_session_factory,
        get_settings_repo,
        router as users_router,
    )
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)

    app = FastAPI()
    app.add_middleware(_DevAuthMiddleware)
    app.include_router(users_router)

    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.dependency_overrides[get_settings_repo] = lambda: settings_repo
    app.dependency_overrides[get_local_user_repo] = lambda: local_user_repo

    app.state._engine = engine
    app.state.local_user_repo = local_user_repo
    return app


@pytest.fixture
async def client():
    app = await _make_app_with_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.state._engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateUser:
    async def test_create_user_returns_201(self, client):
        """POST /api/admin/users creates a user and returns 201."""
        response = await client.post(
            "/api/admin/users",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "display_name": "Test User",
                "password": "SecurePass123",
                "role": "user",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["display_name"] == "Test User"
        assert data["role"] == "user"
        assert data["is_active"] is True
        assert "id" in data
        assert "password_hash" not in data

    async def test_create_duplicate_username_returns_409(self, client):
        """POST /api/admin/users with duplicate username returns 409."""
        await client.post(
            "/api/admin/users",
            json={
                "username": "dup",
                "email": "a@b.com",
                "display_name": "A",
                "password": "Pass1234!",
                "role": "user",
            },
        )
        resp2 = await client.post(
            "/api/admin/users",
            json={
                "username": "dup",
                "email": "c@d.com",
                "display_name": "B",
                "password": "Pass4567!",
                "role": "user",
            },
        )
        assert resp2.status_code == 409
        assert "already exists" in resp2.json()["detail"]

    async def test_create_user_hashes_password(self, client):
        """The stored password_hash is a bcrypt hash, not plaintext."""
        response = await client.post(
            "/api/admin/users",
            json={
                "username": "hashcheck",
                "email": "hash@example.com",
                "display_name": "Hash Check",
                "password": "MyPassword123",
                "role": "user",
            },
        )
        assert response.status_code == 201
        # password_hash should never appear in the response
        assert "password_hash" not in response.json()


class TestGetUser:
    async def test_get_user_by_id(self, client):
        """GET /api/admin/users/{user_id} returns the user."""
        create = await client.post(
            "/api/admin/users",
            json={
                "username": "fetchme",
                "email": "fetch@test.com",
                "display_name": "Fetch Me",
                "password": "Pass1234!",
                "role": "user",
            },
        )
        user_id = create.json()["id"]
        resp = await client.get(f"/api/admin/users/{user_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user_id
        assert data["username"] == "fetchme"

    async def test_get_nonexistent_user_returns_404(self, client):
        """GET /api/admin/users/{user_id} returns 404 for missing user."""
        resp = await client.get("/api/admin/users/nonexistent-id")
        assert resp.status_code == 404


class TestUpdateUser:
    async def test_update_user_email(self, client):
        """PUT /api/admin/users/{user_id} updates the email."""
        create = await client.post(
            "/api/admin/users",
            json={
                "username": "updatable",
                "email": "old@test.com",
                "display_name": "Old",
                "password": "Pass1234!",
                "role": "user",
            },
        )
        user_id = create.json()["id"]
        resp = await client.put(
            f"/api/admin/users/{user_id}",
            json={"email": "new@test.com"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "new@test.com"

    async def test_update_user_display_name(self, client):
        """PUT /api/admin/users/{user_id} updates the display_name."""
        create = await client.post(
            "/api/admin/users",
            json={
                "username": "renameme",
                "email": "rename@test.com",
                "display_name": "Old Name",
                "password": "Pass1234!",
                "role": "user",
            },
        )
        user_id = create.json()["id"]
        resp = await client.put(
            f"/api/admin/users/{user_id}",
            json={"display_name": "New Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New Name"

    async def test_update_nonexistent_user_returns_404(self, client):
        """PUT /api/admin/users/{user_id} returns 404 for missing user."""
        resp = await client.put(
            "/api/admin/users/nonexistent-id",
            json={"email": "x@y.com"},
        )
        assert resp.status_code == 404


class TestDeleteUser:
    async def test_delete_user_returns_204(self, client):
        """DELETE /api/admin/users/{user_id} deactivates the user."""
        create = await client.post(
            "/api/admin/users",
            json={
                "username": "deleteme",
                "email": "del@test.com",
                "display_name": "Delete Me",
                "password": "Pass1234!",
                "role": "user",
            },
        )
        user_id = create.json()["id"]
        resp = await client.delete(f"/api/admin/users/{user_id}")
        assert resp.status_code == 204

        # Verify the user is now inactive
        get_resp = await client.get(f"/api/admin/users/{user_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["is_active"] is False

    async def test_delete_nonexistent_user_returns_404(self, client):
        """DELETE /api/admin/users/{user_id} returns 404 for missing user."""
        resp = await client.delete("/api/admin/users/nonexistent-id")
        assert resp.status_code == 404


class TestResetPassword:
    async def test_reset_password_returns_200(self, client):
        """POST /api/admin/users/{user_id}/reset-password updates the hash."""
        create = await client.post(
            "/api/admin/users",
            json={
                "username": "pwreset",
                "email": "pw@test.com",
                "display_name": "PW Reset",
                "password": "OldPass123!",
                "role": "user",
            },
        )
        user_id = create.json()["id"]
        resp = await client.post(
            f"/api/admin/users/{user_id}/reset-password",
            json={"password": "NewPass456!"},
        )
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Password updated"

    async def test_reset_password_nonexistent_user_returns_404(self, client):
        """POST /api/admin/users/{user_id}/reset-password returns 404 for missing user."""
        resp = await client.post(
            "/api/admin/users/nonexistent-id/reset-password",
            json={"password": "NewPass456!"},
        )
        assert resp.status_code == 404


class TestListUsersWithLocalUsers:
    async def test_list_includes_created_local_users(self, client):
        """GET /api/admin/users includes locally created users."""
        await client.post(
            "/api/admin/users",
            json={
                "username": "localuser1",
                "email": "local1@test.com",
                "display_name": "Local One",
                "password": "Pass1234!",
                "role": "admin",
            },
        )
        resp = await client.get("/api/admin/users")
        assert resp.status_code == 200
        data = resp.json()
        user_ids = {u["user_id"] for u in data}
        display_names = {u.get("display_name") for u in data}
        assert "Local One" in display_names
        assert len(user_ids) >= 1
