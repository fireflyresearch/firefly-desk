# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Catalog Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint


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


def _sample_system(system_id: str = "sys-1") -> ExternalSystem:
    return ExternalSystem(
        id=system_id,
        name="Test System",
        description="A test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(auth_type=AuthType.API_KEY, credential_id="cred-1"),
        tags=["test"],
        status=SystemStatus.ACTIVE,
        metadata={"env": "test"},
    )


def _sample_endpoint(
    endpoint_id: str = "ep-1", system_id: str = "sys-1"
) -> ServiceEndpoint:
    return ServiceEndpoint(
        id=endpoint_id,
        system_id=system_id,
        name="List Users",
        description="List all users",
        method=HttpMethod.GET,
        path="/users",
        when_to_use="When you need a list of users",
        risk_level=RiskLevel.READ,
        required_permissions=["users:read"],
        tags=["users"],
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics CatalogRepository."""
    repo = AsyncMock()
    repo.create_system = AsyncMock(return_value=None)
    repo.get_system = AsyncMock(return_value=None)
    repo.list_systems = AsyncMock(return_value=([], 0))
    repo.update_system = AsyncMock(return_value=None)
    repo.delete_system = AsyncMock(return_value=None)
    repo.create_endpoint = AsyncMock(return_value=None)
    repo.get_endpoint = AsyncMock(return_value=None)
    repo.list_endpoints = AsyncMock(return_value=[])
    repo.delete_endpoint = AsyncMock(return_value=None)
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked CatalogRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.catalog import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        from flydesk.api.deps import get_audit_logger
        app.dependency_overrides[get_audit_logger] = lambda: AsyncMock()

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
        from flydesk.api.catalog import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        from flydesk.api.deps import get_audit_logger
        app.dependency_overrides[get_audit_logger] = lambda: AsyncMock()

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
# Systems CRUD
# ---------------------------------------------------------------------------


class TestCreateSystem:
    async def test_create_system_returns_201(self, admin_client, mock_repo):
        system = _sample_system()
        response = await admin_client.post(
            "/api/catalog/systems", json=system.model_dump()
        )
        assert response.status_code == 201
        mock_repo.create_system.assert_awaited_once()

    async def test_create_system_returns_created_body(self, admin_client, mock_repo):
        system = _sample_system()
        response = await admin_client.post(
            "/api/catalog/systems", json=system.model_dump()
        )
        data = response.json()
        assert data["id"] == "sys-1"
        assert data["name"] == "Test System"


class TestListSystems:
    async def test_list_systems_empty(self, admin_client, mock_repo):
        mock_repo.list_systems.return_value = ([], 0)
        response = await admin_client.get("/api/catalog/systems")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_list_systems_returns_items(self, admin_client, mock_repo):
        mock_repo.list_systems.return_value = ([_sample_system()], 1)
        response = await admin_client.get("/api/catalog/systems")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "sys-1"
        assert data["total"] == 1


class TestGetSystem:
    async def test_get_system_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        response = await admin_client.get("/api/catalog/systems/sys-1")
        assert response.status_code == 200
        assert response.json()["id"] == "sys-1"

    async def test_get_system_not_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None
        response = await admin_client.get("/api/catalog/systems/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateSystem:
    async def test_update_system_success(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        system = _sample_system()
        system.name = "Updated Name"
        response = await admin_client.put(
            "/api/catalog/systems/sys-1", json=system.model_dump()
        )
        assert response.status_code == 200
        mock_repo.update_system.assert_awaited_once()

    async def test_update_system_not_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None
        system = _sample_system()
        response = await admin_client.put(
            "/api/catalog/systems/sys-1", json=system.model_dump()
        )
        assert response.status_code == 404


class TestDeleteSystem:
    async def test_delete_system_success(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        response = await admin_client.delete("/api/catalog/systems/sys-1")
        assert response.status_code == 204
        mock_repo.delete_system.assert_awaited_once_with("sys-1")

    async def test_delete_system_not_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None
        response = await admin_client.delete("/api/catalog/systems/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Update System Status (state machine)
# ---------------------------------------------------------------------------


class TestUpdateSystemStatus:
    """Tests for PUT /systems/{system_id}/status state machine endpoint."""

    async def test_valid_transition_draft_to_active(self, admin_client, mock_repo):
        system = _sample_system()
        system.status = SystemStatus.DRAFT
        mock_repo.get_system.return_value = system

        response = await admin_client.put(
            "/api/catalog/systems/sys-1/status", json={"status": "active"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["id"] == "sys-1"
        mock_repo.update_system.assert_awaited_once()

    async def test_invalid_transition_draft_to_disabled(self, admin_client, mock_repo):
        system = _sample_system()
        system.status = SystemStatus.DRAFT
        mock_repo.get_system.return_value = system

        response = await admin_client.put(
            "/api/catalog/systems/sys-1/status", json={"status": "disabled"}
        )

        assert response.status_code == 409
        assert "cannot transition" in response.json()["detail"].lower()

    async def test_terminal_state_deprecated_to_active(self, admin_client, mock_repo):
        system = _sample_system()
        system.status = SystemStatus.DEPRECATED
        mock_repo.get_system.return_value = system

        response = await admin_client.put(
            "/api/catalog/systems/sys-1/status", json={"status": "active"}
        )

        assert response.status_code == 409
        assert "terminal state" in response.json()["detail"].lower()

    async def test_missing_system_returns_404(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None

        response = await admin_client.put(
            "/api/catalog/systems/no-such/status", json={"status": "active"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_invalid_status_value_returns_400(self, admin_client, mock_repo):
        response = await admin_client.put(
            "/api/catalog/systems/sys-1/status", json={"status": "bogus"}
        )

        assert response.status_code == 400
        assert "invalid status" in response.json()["detail"].lower()

    async def test_missing_status_field_returns_422(self, admin_client, mock_repo):
        response = await admin_client.put(
            "/api/catalog/systems/sys-1/status", json={}
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Endpoints CRUD
# ---------------------------------------------------------------------------


class TestCreateEndpoint:
    async def test_create_endpoint_returns_201(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        endpoint = _sample_endpoint()
        response = await admin_client.post(
            "/api/catalog/systems/sys-1/endpoints", json=endpoint.model_dump()
        )
        assert response.status_code == 201
        mock_repo.create_endpoint.assert_awaited_once()

    async def test_create_endpoint_system_not_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None
        endpoint = _sample_endpoint()
        response = await admin_client.post(
            "/api/catalog/systems/no-such/endpoints", json=endpoint.model_dump()
        )
        assert response.status_code == 404


class TestListEndpoints:
    async def test_list_endpoints_empty(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        mock_repo.list_endpoints.return_value = []
        response = await admin_client.get("/api/catalog/systems/sys-1/endpoints")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_endpoints_returns_items(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = _sample_system()
        mock_repo.list_endpoints.return_value = [_sample_endpoint()]
        response = await admin_client.get("/api/catalog/systems/sys-1/endpoints")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "ep-1"

    async def test_list_endpoints_system_not_found(self, admin_client, mock_repo):
        mock_repo.get_system.return_value = None
        response = await admin_client.get("/api/catalog/systems/no-such/endpoints")
        assert response.status_code == 404


class TestGetEndpoint:
    async def test_get_endpoint_found(self, admin_client, mock_repo):
        mock_repo.get_endpoint.return_value = _sample_endpoint()
        response = await admin_client.get("/api/catalog/endpoints/ep-1")
        assert response.status_code == 200
        assert response.json()["id"] == "ep-1"

    async def test_get_endpoint_not_found(self, admin_client, mock_repo):
        mock_repo.get_endpoint.return_value = None
        response = await admin_client.get("/api/catalog/endpoints/no-such")
        assert response.status_code == 404


class TestDeleteEndpoint:
    async def test_delete_endpoint_success(self, admin_client, mock_repo):
        mock_repo.get_endpoint.return_value = _sample_endpoint()
        response = await admin_client.delete("/api/catalog/endpoints/ep-1")
        assert response.status_code == 204
        mock_repo.delete_endpoint.assert_awaited_once_with("ep-1")

    async def test_delete_endpoint_not_found(self, admin_client, mock_repo):
        mock_repo.get_endpoint.return_value = None
        response = await admin_client.delete("/api/catalog/endpoints/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin-only access
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_list_systems(self, non_admin_client):
        response = await non_admin_client.get("/api/catalog/systems")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_system(self, non_admin_client):
        system = _sample_system()
        response = await non_admin_client.post(
            "/api/catalog/systems", json=system.model_dump()
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_get_system(self, non_admin_client):
        response = await non_admin_client.get("/api/catalog/systems/sys-1")
        assert response.status_code == 403

    async def test_non_admin_cannot_update_system(self, non_admin_client):
        system = _sample_system()
        response = await non_admin_client.put(
            "/api/catalog/systems/sys-1", json=system.model_dump()
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_system(self, non_admin_client):
        response = await non_admin_client.delete("/api/catalog/systems/sys-1")
        assert response.status_code == 403

    async def test_non_admin_cannot_create_endpoint(self, non_admin_client):
        endpoint = _sample_endpoint()
        response = await non_admin_client.post(
            "/api/catalog/systems/sys-1/endpoints", json=endpoint.model_dump()
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_list_endpoints(self, non_admin_client):
        response = await non_admin_client.get(
            "/api/catalog/systems/sys-1/endpoints"
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_get_endpoint(self, non_admin_client):
        response = await non_admin_client.get("/api/catalog/endpoints/ep-1")
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_endpoint(self, non_admin_client):
        response = await non_admin_client.delete("/api/catalog/endpoints/ep-1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# agent_enabled field roundtrip
# ---------------------------------------------------------------------------


class TestAgentEnabledRoundtrip:
    """Verify the ``agent_enabled`` boolean is accepted & returned by the API."""

    async def test_create_system_with_agent_enabled_true(
        self, admin_client, mock_repo
    ):
        system = _sample_system()
        payload = system.model_dump()
        payload["agent_enabled"] = True

        response = await admin_client.post("/api/catalog/systems", json=payload)

        assert response.status_code == 201
        assert response.json()["agent_enabled"] is True

    async def test_create_system_defaults_agent_enabled_false(
        self, admin_client, mock_repo
    ):
        system = _sample_system()
        payload = system.model_dump()
        # Explicitly remove agent_enabled so the model default kicks in
        payload.pop("agent_enabled", None)

        response = await admin_client.post("/api/catalog/systems", json=payload)

        assert response.status_code == 201
        assert response.json()["agent_enabled"] is False

    async def test_update_system_toggles_agent_enabled(
        self, admin_client, mock_repo
    ):
        # Existing system has agent_enabled=False (default)
        existing = _sample_system()
        mock_repo.get_system.return_value = existing

        # Send update with agent_enabled flipped to True
        payload = existing.model_dump()
        payload["agent_enabled"] = True

        response = await admin_client.put(
            "/api/catalog/systems/sys-1", json=payload
        )

        assert response.status_code == 200
        assert response.json()["agent_enabled"] is True
        mock_repo.update_system.assert_awaited_once()
