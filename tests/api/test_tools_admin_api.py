# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Tools Management admin REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.catalog.enums import HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import (
    AuthConfig,
    ExternalSystem,
    ServiceEndpoint,
)
from flydesk.catalog.repository import CatalogRepository
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


def _sample_system() -> ExternalSystem:
    """Build a sample external system."""
    return ExternalSystem(
        id="sys-jira",
        name="Jira",
        description="Jira issue tracker",
        base_url="https://jira.example.com",
        status=SystemStatus.ACTIVE,
        auth_config=AuthConfig(
            auth_type="api_key",
            credential_id="cred-jira",
        ),
    )


def _sample_endpoint(*, endpoint_id: str = "ep-get-issue") -> ServiceEndpoint:
    """Build a sample service endpoint."""
    return ServiceEndpoint(
        id=endpoint_id,
        system_id="sys-jira",
        name="Get Issue",
        description="Retrieve a Jira issue by key",
        method=HttpMethod.GET,
        path="/rest/api/2/issue/{issueKey}",
        path_params={
            "issueKey": {
                "type": "string",
                "description": "The Jira issue key",
                "required": True,
            }
        },
        query_params={
            "fields": {
                "type": "string",
                "description": "Comma-separated list of fields",
                "required": False,
            }
        },
        request_body=None,
        when_to_use="When you need to look up a Jira issue",
        examples=["Get issue PROJ-123"],
        risk_level=RiskLevel.READ,
        required_permissions=["jira:read"],
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
        from flydesk.api.tools_admin import (
            get_catalog_repo as tools_get_catalog,
            get_settings_repo as tools_get_settings,
        )
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        catalog_repo = CatalogRepository(session_factory)
        settings_repo = SettingsRepository(session_factory)
        app.dependency_overrides[tools_get_catalog] = lambda: catalog_repo
        app.dependency_overrides[tools_get_settings] = lambda: settings_repo

        admin_session = _make_user_session(permissions=["*"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Expose repos for seeding data in tests
            ac._catalog_repo = catalog_repo  # type: ignore[attr-defined]
            ac._settings_repo = settings_repo  # type: ignore[attr-defined]
            yield ac

        await engine.dispose()


@pytest.fixture
async def non_admin_client():
    """AsyncClient with a non-admin user session (no admin:settings permission)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.tools_admin import (
            get_catalog_repo as tools_get_catalog,
            get_settings_repo as tools_get_settings,
        )
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        catalog_repo = CatalogRepository(session_factory)
        settings_repo = SettingsRepository(session_factory)
        app.dependency_overrides[tools_get_catalog] = lambda: catalog_repo
        app.dependency_overrides[tools_get_settings] = lambda: settings_repo

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


async def _seed_system_and_endpoint(client: AsyncClient) -> str:
    """Seed a system + endpoint via the catalog repo attached to the client."""
    repo: CatalogRepository = client._catalog_repo  # type: ignore[attr-defined]
    await repo.create_system(_sample_system())
    ep = _sample_endpoint()
    await repo.create_endpoint(ep)
    return ep.id


# ---------------------------------------------------------------------------
# Tests -- List tools
# ---------------------------------------------------------------------------


class TestListTools:
    async def test_list_tools_empty(self, admin_client):
        """GET /api/admin/tools returns empty list when no endpoints exist."""
        response = await admin_client.get("/api/admin/tools")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_tools_with_data(self, admin_client):
        """GET /api/admin/tools returns tool summaries."""
        await _seed_system_and_endpoint(admin_client)

        response = await admin_client.get("/api/admin/tools")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        tool = data[0]
        assert tool["id"] == "ep-get-issue"
        assert tool["name"] == "Get Issue"
        assert tool["system_id"] == "sys-jira"
        assert tool["method"] == "GET"
        assert tool["risk_level"] == "read"
        assert tool["required_permissions"] == ["jira:read"]
        assert tool["enabled"] is True


# ---------------------------------------------------------------------------
# Tests -- Get tool detail
# ---------------------------------------------------------------------------


class TestGetTool:
    async def test_get_tool_detail(self, admin_client):
        """GET /api/admin/tools/{id} returns full tool detail."""
        await _seed_system_and_endpoint(admin_client)

        response = await admin_client.get("/api/admin/tools/ep-get-issue")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "ep-get-issue"
        assert data["name"] == "Get Issue"
        assert data["when_to_use"] == "When you need to look up a Jira issue"
        assert data["path_params"] is not None
        assert data["timeout_seconds"] == 30.0

    async def test_get_tool_not_found(self, admin_client):
        """GET /api/admin/tools/{id} returns 404 for unknown endpoint."""
        response = await admin_client.get("/api/admin/tools/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Test endpoint (preview mode)
# ---------------------------------------------------------------------------


class TestToolTest:
    async def test_tool_preview(self, admin_client):
        """POST /api/admin/tools/{id}/test returns a preview of the call."""
        await _seed_system_and_endpoint(admin_client)

        response = await admin_client.post(
            "/api/admin/tools/ep-get-issue/test",
            json={"params": {"issueKey": "PROJ-456", "fields": "summary,status"}},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["endpoint_id"] == "ep-get-issue"
        assert data["method"] == "GET"
        assert data["resolved_path"] == "/rest/api/2/issue/PROJ-456"
        assert data["query_params"] == {"fields": "summary,status"}
        assert data["preview"] is True
        assert data["would_require_permissions"] == ["jira:read"]

    async def test_tool_test_not_found(self, admin_client):
        """POST /api/admin/tools/{id}/test returns 404 for unknown endpoint."""
        response = await admin_client.post(
            "/api/admin/tools/nonexistent/test",
            json={"params": {}},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Update tool config
# ---------------------------------------------------------------------------


class TestUpdateToolConfig:
    async def test_disable_tool(self, admin_client):
        """PUT /api/admin/tools/{id}/config can disable a tool."""
        await _seed_system_and_endpoint(admin_client)

        response = await admin_client.put(
            "/api/admin/tools/ep-get-issue/config",
            json={"enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["endpoint_id"] == "ep-get-issue"
        assert data["config"]["enabled"] is False

        # Verify it shows as disabled in the list
        list_resp = await admin_client.get("/api/admin/tools")
        tools = list_resp.json()
        assert len(tools) == 1
        assert tools[0]["enabled"] is False

    async def test_override_permissions(self, admin_client):
        """PUT /api/admin/tools/{id}/config can override required permissions."""
        await _seed_system_and_endpoint(admin_client)

        response = await admin_client.put(
            "/api/admin/tools/ep-get-issue/config",
            json={"required_permissions": ["custom:perm1", "custom:perm2"]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["config"]["required_permissions"] == [
            "custom:perm1",
            "custom:perm2",
        ]

        # Verify it reflects in detail
        detail_resp = await admin_client.get("/api/admin/tools/ep-get-issue")
        assert detail_resp.json()["required_permissions"] == [
            "custom:perm1",
            "custom:perm2",
        ]

    async def test_update_config_not_found(self, admin_client):
        """PUT /api/admin/tools/{id}/config returns 404 for unknown endpoint."""
        response = await admin_client.put(
            "/api/admin/tools/nonexistent/config",
            json={"enabled": True},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Permission guard enforcement
# ---------------------------------------------------------------------------


class TestPermissionGuard:
    async def test_non_admin_gets_403(self, non_admin_client):
        """Non-admin users receive 403 on admin tools endpoints."""
        response = await non_admin_client.get("/api/admin/tools")
        assert response.status_code == 403

    async def test_non_admin_cannot_get_tool(self, non_admin_client):
        """Non-admin users cannot get tool detail."""
        response = await non_admin_client.get("/api/admin/tools/some-id")
        assert response.status_code == 403

    async def test_non_admin_cannot_test_tool(self, non_admin_client):
        """Non-admin users cannot test tools."""
        response = await non_admin_client.post(
            "/api/admin/tools/some-id/test",
            json={"params": {}},
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_update_config(self, non_admin_client):
        """Non-admin users cannot update tool config."""
        response = await non_admin_client.put(
            "/api/admin/tools/some-id/config",
            json={"enabled": True},
        )
        assert response.status_code == 403
