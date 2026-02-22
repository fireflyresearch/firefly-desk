# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Roles admin REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.models.base import Base
from flydesk.rbac.permissions import Permission
from flydesk.rbac.repository import RoleRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_session(*, permissions: list[str]) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="test-user-1",
        email="test@example.com",
        display_name="Test User",
        roles=["admin"] if "*" in permissions else ["viewer"],
        permissions=permissions,
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client():
    """AsyncClient backed by a real SQLite database with admin permissions."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.roles import get_role_repo
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        role_repo = RoleRepository(session_factory)
        await role_repo.seed_builtin_roles()
        app.dependency_overrides[get_role_repo] = lambda: role_repo

        admin_session = _make_user_session(permissions=["*"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


@pytest.fixture
async def non_admin_client():
    """AsyncClient with a non-admin user session (no admin:roles permission)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.roles import get_role_repo
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        role_repo = RoleRepository(session_factory)
        await role_repo.seed_builtin_roles()
        app.dependency_overrides[get_role_repo] = lambda: role_repo

        viewer_session = _make_user_session(permissions=["knowledge:read"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


# ---------------------------------------------------------------------------
# Tests -- List / Read
# ---------------------------------------------------------------------------


class TestListRoles:
    async def test_list_roles_returns_builtins(self, admin_client):
        """GET /api/admin/roles returns seeded built-in roles."""
        response = await admin_client.get("/api/admin/roles")
        assert response.status_code == 200
        roles = response.json()
        assert isinstance(roles, list)
        names = {r["name"] for r in roles}
        assert "admin" in names
        assert "operator" in names
        assert "viewer" in names

    async def test_list_roles_builtin_flag(self, admin_client):
        """Built-in roles have is_builtin=True."""
        response = await admin_client.get("/api/admin/roles")
        roles = response.json()
        for role in roles:
            if role["name"] in ("admin", "operator", "viewer"):
                assert role["is_builtin"] is True


class TestGetRole:
    async def test_get_role_by_id(self, admin_client):
        """GET /api/admin/roles/{id} returns role details."""
        response = await admin_client.get("/api/admin/roles/role-admin")
        assert response.status_code == 200
        role = response.json()
        assert role["name"] == "admin"
        assert role["display_name"] == "Administrator"
        assert role["is_builtin"] is True

    async def test_get_role_not_found(self, admin_client):
        """GET /api/admin/roles/{id} returns 404 for unknown role."""
        response = await admin_client.get("/api/admin/roles/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Create / Update / Delete
# ---------------------------------------------------------------------------


class TestCreateRole:
    async def test_create_custom_role(self, admin_client):
        """POST /api/admin/roles creates a custom role."""
        response = await admin_client.post(
            "/api/admin/roles",
            json={
                "name": "support",
                "display_name": "Support Agent",
                "description": "First-line support role",
                "permissions": ["knowledge:read", "chat:send"],
            },
        )
        assert response.status_code == 201
        role = response.json()
        assert role["name"] == "support"
        assert role["display_name"] == "Support Agent"
        assert role["is_builtin"] is False
        assert "knowledge:read" in role["permissions"]
        assert "chat:send" in role["permissions"]
        assert role["id"].startswith("role-")

    async def test_create_duplicate_name_returns_409(self, admin_client):
        """POST /api/admin/roles refuses duplicate names."""
        await admin_client.post(
            "/api/admin/roles",
            json={"name": "unique-role", "display_name": "Unique"},
        )
        response = await admin_client.post(
            "/api/admin/roles",
            json={"name": "unique-role", "display_name": "Duplicate"},
        )
        assert response.status_code == 409


class TestUpdateRole:
    async def test_update_custom_role_permissions(self, admin_client):
        """PUT /api/admin/roles/{id} updates role permissions."""
        create_resp = await admin_client.post(
            "/api/admin/roles",
            json={
                "name": "updatable",
                "display_name": "Updatable",
                "permissions": ["knowledge:read"],
            },
        )
        role_id = create_resp.json()["id"]

        update_resp = await admin_client.put(
            f"/api/admin/roles/{role_id}",
            json={"permissions": ["knowledge:read", "knowledge:write", "chat:send"]},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert set(updated["permissions"]) == {
            "knowledge:read",
            "knowledge:write",
            "chat:send",
        }

    async def test_update_role_not_found(self, admin_client):
        """PUT /api/admin/roles/{id} returns 404 for unknown role."""
        response = await admin_client.put(
            "/api/admin/roles/nonexistent",
            json={"display_name": "New Name"},
        )
        assert response.status_code == 404


class TestDeleteRole:
    async def test_delete_custom_role(self, admin_client):
        """DELETE /api/admin/roles/{id} deletes a custom role."""
        create_resp = await admin_client.post(
            "/api/admin/roles",
            json={"name": "deletable", "display_name": "Deletable"},
        )
        role_id = create_resp.json()["id"]

        delete_resp = await admin_client.delete(f"/api/admin/roles/{role_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await admin_client.get(f"/api/admin/roles/{role_id}")
        assert get_resp.status_code == 404

    async def test_refuse_delete_builtin_role(self, admin_client):
        """DELETE /api/admin/roles/{id} refuses to delete built-in roles."""
        response = await admin_client.delete("/api/admin/roles/role-admin")
        assert response.status_code == 400
        assert "built-in" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Tests -- Permissions listing
# ---------------------------------------------------------------------------


class TestListPermissions:
    async def test_list_permissions_returns_all(self, admin_client):
        """GET /api/admin/permissions returns all Permission enum values."""
        response = await admin_client.get("/api/admin/permissions")
        assert response.status_code == 200
        perms = response.json()
        assert isinstance(perms, list)
        assert len(perms) == len(Permission)

        # Each entry has the expected shape
        for perm in perms:
            assert "value" in perm
            assert "name" in perm
            assert "resource" in perm
            assert "action" in perm
            assert ":" in perm["value"]


# ---------------------------------------------------------------------------
# Tests -- Permission guard enforcement
# ---------------------------------------------------------------------------


class TestPermissionGuard:
    async def test_non_admin_gets_403(self, non_admin_client):
        """Non-admin users receive 403 on admin role endpoints."""
        response = await non_admin_client.get("/api/admin/roles")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_role(self, non_admin_client):
        """Non-admin users cannot create roles."""
        response = await non_admin_client.post(
            "/api/admin/roles",
            json={"name": "hacker", "display_name": "Hacker"},
        )
        assert response.status_code == 403
