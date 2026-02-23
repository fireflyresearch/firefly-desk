# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the SSO Attribute Mapping admin REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.models.base import Base
from flydesk.settings.repository import SettingsRepository


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
        from flydesk.api.sso_mappings import get_settings_repo as sso_get_settings
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        settings_repo = SettingsRepository(session_factory)
        app.dependency_overrides[sso_get_settings] = lambda: settings_repo

        admin_session = _make_user_session(permissions=["*"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._settings_repo = settings_repo  # type: ignore[attr-defined]
            yield ac

        await engine.dispose()


@pytest.fixture
async def non_admin_client():
    """AsyncClient with a non-admin user session (no admin:sso permission)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.sso_mappings import get_settings_repo as sso_get_settings
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        settings_repo = SettingsRepository(session_factory)
        app.dependency_overrides[sso_get_settings] = lambda: settings_repo

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
# Tests -- CRUD operations
# ---------------------------------------------------------------------------


class TestListSSOMapping:
    async def test_list_empty(self, admin_client):
        """GET /api/admin/sso-mappings returns empty list initially."""
        response = await admin_client.get("/api/admin/sso-mappings")
        assert response.status_code == 200
        assert response.json() == []


class TestCreateSSOMapping:
    async def test_create_mapping(self, admin_client):
        """POST /api/admin/sso-mappings creates a new mapping."""
        response = await admin_client.post(
            "/api/admin/sso-mappings",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
                "target_type": "header",
                "system_filter": None,
                "transform": "uppercase",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["claim_path"] == "employee_id"
        assert data["target_header"] == "X-Employee-ID"
        assert data["target_type"] == "header"
        assert data["transform"] == "uppercase"
        assert "id" in data

    async def test_create_and_list(self, admin_client):
        """Creating a mapping makes it appear in the list."""
        await admin_client.post(
            "/api/admin/sso-mappings",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
            },
        )
        response = await admin_client.get("/api/admin/sso-mappings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["claim_path"] == "employee_id"


class TestUpdateSSOMapping:
    async def test_update_mapping(self, admin_client):
        """PUT /api/admin/sso-mappings/{id} updates an existing mapping."""
        create_resp = await admin_client.post(
            "/api/admin/sso-mappings",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
            },
        )
        mapping_id = create_resp.json()["id"]

        update_resp = await admin_client.put(
            f"/api/admin/sso-mappings/{mapping_id}",
            json={
                "claim_path": "custom_claims.hr_id",
                "target_header": "X-HR-ID",
                "target_type": "header",
                "system_filter": "sys-hr",
                "transform": "prefix:HR-",
            },
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["claim_path"] == "custom_claims.hr_id"
        assert data["target_header"] == "X-HR-ID"
        assert data["system_filter"] == "sys-hr"
        assert data["transform"] == "prefix:HR-"

    async def test_update_not_found(self, admin_client):
        """PUT /api/admin/sso-mappings/{id} returns 404 for unknown mapping."""
        response = await admin_client.put(
            "/api/admin/sso-mappings/nonexistent",
            json={
                "claim_path": "foo",
                "target_header": "X-Foo",
            },
        )
        assert response.status_code == 404


class TestDeleteSSOMapping:
    async def test_delete_mapping(self, admin_client):
        """DELETE /api/admin/sso-mappings/{id} removes the mapping."""
        create_resp = await admin_client.post(
            "/api/admin/sso-mappings",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
            },
        )
        mapping_id = create_resp.json()["id"]

        delete_resp = await admin_client.delete(
            f"/api/admin/sso-mappings/{mapping_id}"
        )
        assert delete_resp.status_code == 200

        # Verify it no longer appears in the list
        list_resp = await admin_client.get("/api/admin/sso-mappings")
        assert list_resp.json() == []

    async def test_delete_not_found(self, admin_client):
        """DELETE /api/admin/sso-mappings/{id} returns 404 for unknown mapping."""
        response = await admin_client.delete(
            "/api/admin/sso-mappings/nonexistent"
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Permission guard enforcement
# ---------------------------------------------------------------------------


class TestPermissionGuard:
    async def test_non_admin_list_403(self, non_admin_client):
        """Non-admin users receive 403 on list SSO mappings."""
        response = await non_admin_client.get("/api/admin/sso-mappings")
        assert response.status_code == 403

    async def test_non_admin_create_403(self, non_admin_client):
        """Non-admin users cannot create SSO mappings."""
        response = await non_admin_client.post(
            "/api/admin/sso-mappings",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
            },
        )
        assert response.status_code == 403

    async def test_non_admin_update_403(self, non_admin_client):
        """Non-admin users cannot update SSO mappings."""
        response = await non_admin_client.put(
            "/api/admin/sso-mappings/some-id",
            json={
                "claim_path": "employee_id",
                "target_header": "X-Employee-ID",
            },
        )
        assert response.status_code == 403

    async def test_non_admin_delete_403(self, non_admin_client):
        """Non-admin users cannot delete SSO mappings."""
        response = await non_admin_client.delete(
            "/api/admin/sso-mappings/some-id"
        )
        assert response.status_code == 403
