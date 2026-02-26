# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Search Engine Configuration REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession


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
    repo.get_user_settings = AsyncMock()
    repo.update_user_settings = AsyncMock()
    repo.get_all_app_settings = AsyncMock(return_value={})
    repo.set_app_setting = AsyncMock(return_value=None)
    repo.get_app_setting = AsyncMock(return_value=None)
    repo.get_agent_settings = AsyncMock()
    repo.set_agent_settings = AsyncMock()
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
# GET /api/settings/search
# ---------------------------------------------------------------------------


class TestGetSearchConfig:
    async def test_returns_defaults_when_nothing_configured(
        self, admin_client, mock_repo
    ):
        """GET /settings/search returns defaults when no DB values are set."""
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.get("/api/settings/search")
        assert response.status_code == 200
        data = response.json()
        assert data["search_provider"] == ""
        assert data["search_api_key"] == ""
        assert data["search_max_results"] == 5

    async def test_returns_db_values_with_masked_key(
        self, admin_client, mock_repo
    ):
        """GET /settings/search returns persisted values with masked API key."""
        mock_repo.get_all_app_settings.return_value = {
            "search_provider": "tavily",
            "search_api_key": "tvly-secret-key-12345678",
            "search_max_results": "10",
        }
        response = await admin_client.get("/api/settings/search")
        assert response.status_code == 200
        data = response.json()
        assert data["search_provider"] == "tavily"
        # API key should be masked
        assert data["search_api_key"].startswith("***")
        assert data["search_api_key"].endswith("5678")
        assert data["search_max_results"] == 10

    async def test_non_admin_cannot_access(self, non_admin_client):
        """Non-admin users should get 403."""
        response = await non_admin_client.get("/api/settings/search")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/settings/search
# ---------------------------------------------------------------------------


class TestUpdateSearchConfig:
    async def test_persists_settings(self, admin_client, mock_repo):
        """PUT /settings/search persists all search config fields."""
        mock_repo.get_all_app_settings.return_value = {}
        payload = {
            "search_provider": "tavily",
            "search_api_key": "tvly-new-key-99999999",
            "search_max_results": 10,
        }
        response = await admin_client.put(
            "/api/settings/search", json=payload
        )
        assert response.status_code == 200
        # Should have called set_app_setting for provider, api_key, and max_results
        assert mock_repo.set_app_setting.await_count >= 3

    async def test_skips_masked_api_key(self, admin_client, mock_repo):
        """PUT /settings/search does not overwrite key when masked value sent."""
        mock_repo.get_all_app_settings.return_value = {}
        payload = {
            "search_provider": "tavily",
            "search_api_key": "***5678",
            "search_max_results": 5,
        }
        response = await admin_client.put(
            "/api/settings/search", json=payload
        )
        assert response.status_code == 200
        # Should have called set_app_setting for provider and max_results,
        # but NOT for the masked api_key
        calls = mock_repo.set_app_setting.call_args_list
        saved_keys = [c.args[0] for c in calls]
        assert "search_provider" in saved_keys
        assert "search_max_results" in saved_keys
        assert "search_api_key" not in saved_keys

    async def test_non_admin_cannot_update(self, non_admin_client):
        """Non-admin users should get 403."""
        payload = {
            "search_provider": "tavily",
            "search_api_key": "tvly-hacker",
            "search_max_results": 5,
        }
        response = await non_admin_client.put(
            "/api/settings/search", json=payload
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST /api/settings/search/test
# ---------------------------------------------------------------------------


class TestSearchTest:
    async def test_non_admin_cannot_test(self, non_admin_client):
        """Non-admin users should get 403."""
        response = await non_admin_client.post("/api/settings/search/test")
        assert response.status_code == 403

    async def test_returns_error_when_no_provider(self, admin_client, mock_repo):
        """POST /settings/search/test returns error when no provider configured."""
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.post("/api/settings/search/test")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["provider"] == "none"
        assert "No search provider configured" in data["error"]
