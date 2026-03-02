# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the model routing admin API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.agent.router.models import RoutingConfig
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
def mock_routing_repo():
    """Return an AsyncMock that mimics RoutingConfigRepository."""
    repo = AsyncMock()
    repo.get_config = AsyncMock(
        return_value=RoutingConfig(
            enabled=True,
            classifier_model="anthropic:claude-haiku-4-5-20251001",
            tier_mappings={
                "fast": "anthropic:claude-haiku-4-5-20251001",
                "balanced": "anthropic:claude-sonnet-4-6",
                "powerful": "anthropic:claude-opus-4-6",
            },
        )
    )
    repo.update_config = AsyncMock(
        return_value=RoutingConfig(
            enabled=True,
            classifier_model="anthropic:claude-haiku-4-5-20251001",
            tier_mappings={"fast": "anthropic:claude-haiku-4-5-20251001"},
        )
    )
    return repo


@pytest.fixture
async def admin_client(mock_routing_repo):
    """AsyncClient with an admin user session and mocked RoutingConfigRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_routing_config_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_routing_config_repo] = lambda: mock_routing_repo

        # Inject admin user_session into request state via middleware
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
async def non_admin_client(mock_routing_repo):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_routing_config_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_routing_config_repo] = lambda: mock_routing_repo

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
# GET /api/admin/model-routing
# ---------------------------------------------------------------------------


class TestGetRoutingConfig:
    async def test_returns_config(self, admin_client, mock_routing_repo):
        resp = await admin_client.get("/api/admin/model-routing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert "fast" in data["tier_mappings"]
        assert data["tier_mappings"]["fast"] == "anthropic:claude-haiku-4-5-20251001"

    async def test_returns_defaults_when_no_config(self, admin_client, mock_routing_repo):
        mock_routing_repo.get_config = AsyncMock(return_value=None)
        resp = await admin_client.get("/api/admin/model-routing")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["tier_mappings"] == {}


# ---------------------------------------------------------------------------
# PUT /api/admin/model-routing
# ---------------------------------------------------------------------------


class TestUpdateRoutingConfig:
    async def test_updates_config(self, admin_client, mock_routing_repo):
        resp = await admin_client.put(
            "/api/admin/model-routing",
            json={
                "enabled": True,
                "classifier_model": "anthropic:claude-haiku-4-5-20251001",
                "tier_mappings": {"fast": "anthropic:claude-haiku-4-5-20251001"},
            },
        )
        assert resp.status_code == 200
        mock_routing_repo.update_config.assert_called_once()
        data = resp.json()
        assert data["enabled"] is True

    async def test_update_returns_updated_config(self, admin_client, mock_routing_repo):
        resp = await admin_client.put(
            "/api/admin/model-routing",
            json={
                "enabled": True,
                "classifier_model": "anthropic:claude-haiku-4-5-20251001",
                "tier_mappings": {"fast": "anthropic:claude-haiku-4-5-20251001"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        # The mock returns a config with just "fast" mapping
        assert "fast" in data["tier_mappings"]
        assert len(data["tier_mappings"]) == 1


# ---------------------------------------------------------------------------
# POST /api/admin/model-routing/test
# ---------------------------------------------------------------------------


class TestClassifierTest:
    async def test_test_endpoint(self, admin_client, mock_routing_repo):
        resp = await admin_client.post(
            "/api/admin/model-routing/test",
            json={"message": "Hello!", "tool_count": 3},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Hello!"
        assert "config" in data

    async def test_test_endpoint_when_disabled(self, admin_client, mock_routing_repo):
        mock_routing_repo.get_config = AsyncMock(return_value=None)
        resp = await admin_client.post(
            "/api/admin/model-routing/test",
            json={"message": "Hello!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
        assert "not enabled" in data["error"].lower()

    async def test_test_endpoint_when_config_disabled(self, admin_client, mock_routing_repo):
        mock_routing_repo.get_config = AsyncMock(
            return_value=RoutingConfig(enabled=False)
        )
        resp = await admin_client.post(
            "/api/admin/model-routing/test",
            json={"message": "Complex analysis request"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data


# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_get_config(self, non_admin_client):
        response = await non_admin_client.get("/api/admin/model-routing")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_update_config(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/admin/model-routing",
            json={"enabled": True, "tier_mappings": {}},
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_test_classifier(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/admin/model-routing/test",
            json={"message": "Hello!"},
        )
        assert response.status_code == 403
