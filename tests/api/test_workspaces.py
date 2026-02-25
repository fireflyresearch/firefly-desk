# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Workspaces REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.workspaces.models import Workspace


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


def _sample_workspace(workspace_id: str = "ws-1") -> Workspace:
    return Workspace(
        id=workspace_id,
        name="Engineering",
        description="Engineering workspace",
        icon="code",
        color="#3b82f6",
        roles=["engineer"],
        users=["user-1", "user-2"],
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics WorkspaceRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_sample_workspace())
    repo.get = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=[])
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=None)
    repo.list_for_user = AsyncMock(return_value=[])
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked WorkspaceRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.workspaces import get_workspace_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_workspace_repo] = lambda: mock_repo

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
        from flydesk.api.workspaces import get_workspace_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_workspace_repo] = lambda: mock_repo

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
# Workspaces CRUD
# ---------------------------------------------------------------------------


class TestListWorkspaces:
    async def test_list_workspaces_empty(self, admin_client, mock_repo):
        mock_repo.list_all.return_value = []
        response = await admin_client.get("/api/workspaces")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_workspaces_returns_items(self, admin_client, mock_repo):
        mock_repo.list_all.return_value = [_sample_workspace()]
        response = await admin_client.get("/api/workspaces")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "ws-1"
        assert data[0]["name"] == "Engineering"


class TestCreateWorkspace:
    async def test_create_workspace_returns_201(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/workspaces",
            json={"name": "Engineering", "description": "Engineering workspace"},
        )
        assert response.status_code == 201
        mock_repo.create.assert_awaited_once()

    async def test_create_workspace_returns_body(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/workspaces",
            json={"name": "Engineering", "description": "Engineering workspace"},
        )
        data = response.json()
        assert data["id"] == "ws-1"
        assert data["name"] == "Engineering"
        assert data["roles"] == ["engineer"]
        assert data["users"] == ["user-1", "user-2"]

    async def test_create_workspace_minimal(self, admin_client, mock_repo):
        """Only name is required."""
        response = await admin_client.post(
            "/api/workspaces", json={"name": "Minimal"}
        )
        assert response.status_code == 201

    async def test_create_workspace_missing_name_returns_422(self, admin_client, mock_repo):
        response = await admin_client.post("/api/workspaces", json={})
        assert response.status_code == 422


class TestGetWorkspace:
    async def test_get_workspace_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = _sample_workspace()
        response = await admin_client.get("/api/workspaces/ws-1")
        assert response.status_code == 200
        assert response.json()["id"] == "ws-1"
        assert response.json()["name"] == "Engineering"

    async def test_get_workspace_not_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = None
        response = await admin_client.get("/api/workspaces/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateWorkspace:
    async def test_update_workspace_success(self, admin_client, mock_repo):
        updated = _sample_workspace()
        updated.name = "Updated Name"
        mock_repo.update.return_value = updated
        response = await admin_client.put(
            "/api/workspaces/ws-1",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 200
        mock_repo.update.assert_awaited_once()

    async def test_update_workspace_not_found(self, admin_client, mock_repo):
        mock_repo.update.return_value = None
        response = await admin_client.put(
            "/api/workspaces/no-such",
            json={"name": "Updated Name"},
        )
        assert response.status_code == 404

    async def test_update_workspace_partial(self, admin_client, mock_repo):
        """Only update specific fields."""
        updated = _sample_workspace()
        updated.color = "#ef4444"
        mock_repo.update.return_value = updated
        response = await admin_client.put(
            "/api/workspaces/ws-1",
            json={"color": "#ef4444"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["color"] == "#ef4444"


class TestDeleteWorkspace:
    async def test_delete_workspace_success(self, admin_client, mock_repo):
        mock_repo.get.return_value = _sample_workspace()
        response = await admin_client.delete("/api/workspaces/ws-1")
        assert response.status_code == 204
        mock_repo.delete.assert_awaited_once_with("ws-1")

    async def test_delete_workspace_not_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = None
        response = await admin_client.delete("/api/workspaces/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin-only access
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_list_workspaces(self, non_admin_client):
        response = await non_admin_client.get("/api/workspaces")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_workspace(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/workspaces", json={"name": "Test"}
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_get_workspace(self, non_admin_client):
        response = await non_admin_client.get("/api/workspaces/ws-1")
        assert response.status_code == 403

    async def test_non_admin_cannot_update_workspace(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/workspaces/ws-1", json={"name": "Test"}
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_workspace(self, non_admin_client):
        response = await non_admin_client.delete("/api/workspaces/ws-1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Field roundtrip
# ---------------------------------------------------------------------------


class TestFieldRoundtrip:
    async def test_workspace_icon_and_color(self, admin_client, mock_repo):
        ws = Workspace(
            id="ws-2",
            name="Design",
            icon="palette",
            color="#ec4899",
            roles=[],
            users=[],
        )
        mock_repo.create.return_value = ws
        response = await admin_client.post(
            "/api/workspaces",
            json={"name": "Design", "icon": "palette", "color": "#ec4899"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["icon"] == "palette"
        assert data["color"] == "#ec4899"

    async def test_workspace_roles_and_users(self, admin_client, mock_repo):
        ws = _sample_workspace()
        mock_repo.get.return_value = ws
        response = await admin_client.get("/api/workspaces/ws-1")
        assert response.status_code == 200
        data = response.json()
        assert "engineer" in data["roles"]
        assert "user-1" in data["users"]
        assert "user-2" in data["users"]
