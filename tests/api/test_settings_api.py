# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Settings REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.settings.models import UserSettings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics SettingsRepository."""
    repo = AsyncMock()
    repo.get_user_settings = AsyncMock(return_value=UserSettings())
    repo.update_user_settings = AsyncMock(return_value=None)
    repo.get_all_app_settings = AsyncMock(return_value={})
    repo.set_app_setting = AsyncMock(return_value=None)
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked SettingsRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.settings import get_settings_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_settings_repo] = lambda: mock_repo

        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def non_admin_client(mock_repo):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.settings import get_settings_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_settings_repo] = lambda: mock_repo

        viewer_session = _make_user_session(roles=["viewer"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# User Settings Tests
# ---------------------------------------------------------------------------


class TestGetUserSettings:
    async def test_get_user_settings_defaults(self, admin_client, mock_repo):
        mock_repo.get_user_settings.return_value = UserSettings()
        response = await admin_client.get("/api/settings/user")
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "system"
        assert data["agent_verbose"] is False
        assert data["notifications_enabled"] is True

    async def test_get_user_settings_custom(self, admin_client, mock_repo):
        mock_repo.get_user_settings.return_value = UserSettings(
            theme="dark", agent_verbose=True
        )
        response = await admin_client.get("/api/settings/user")
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["agent_verbose"] is True


class TestUpdateUserSettings:
    async def test_update_user_settings(self, admin_client, mock_repo):
        payload = {
            "theme": "dark",
            "agent_verbose": True,
            "sidebar_collapsed": False,
            "notifications_enabled": True,
            "default_model_id": None,
            "display_preferences": {},
        }
        response = await admin_client.put(
            "/api/settings/user", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"
        assert data["agent_verbose"] is True
        mock_repo.update_user_settings.assert_awaited_once()


# ---------------------------------------------------------------------------
# App Settings Tests (admin only)
# ---------------------------------------------------------------------------


class TestGetAppSettings:
    async def test_get_app_settings(self, admin_client, mock_repo):
        mock_repo.get_all_app_settings.return_value = {
            "app_title": "My Desk",
            "accent_color": "#FF0000",
        }
        response = await admin_client.get("/api/settings/app")
        assert response.status_code == 200
        data = response.json()
        assert data["app_title"] == "My Desk"
        assert data["accent_color"] == "#FF0000"


class TestUpdateAppSettings:
    async def test_update_app_settings(self, admin_client, mock_repo):
        payload = {"app_title": "New Title", "accent_color": "#00FF00"}
        response = await admin_client.put(
            "/api/settings/app", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["app_title"] == "New Title"
        assert mock_repo.set_app_setting.await_count == 2


# ---------------------------------------------------------------------------
# Admin Guard
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_access_app_settings(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/app")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_update_app_settings(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/settings/app", json={"key": "value"}
        )
        assert response.status_code == 403

    async def test_non_admin_can_access_user_settings(self, non_admin_client, mock_repo):
        """Any authenticated user should be able to access their own settings."""
        mock_repo.get_user_settings.return_value = UserSettings()
        response = await non_admin_client.get("/api/settings/user")
        assert response.status_code == 200
