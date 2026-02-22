# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Credentials Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.catalog.models import Credential


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


def _sample_credential(credential_id: str = "cred-1") -> Credential:
    return Credential(
        id=credential_id,
        system_id="sys-1",
        name="API Key for System 1",
        encrypted_value="enc-secret-value",
        credential_type="api_key",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        last_rotated=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_store():
    """Return an AsyncMock that mimics CredentialStore."""
    store = AsyncMock()
    store.list_credentials = AsyncMock(return_value=[])
    store.get_credential = AsyncMock(return_value=None)
    store.create_credential = AsyncMock(return_value=None)
    store.update_credential = AsyncMock(return_value=None)
    store.delete_credential = AsyncMock(return_value=None)
    return store


@pytest.fixture
async def admin_client(mock_store):
    """AsyncClient with an admin user session and mocked CredentialStore."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.credentials import get_credential_store
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_credential_store] = lambda: mock_store

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
async def non_admin_client(mock_store):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.credentials import get_credential_store
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_credential_store] = lambda: mock_store

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
# List Credentials
# ---------------------------------------------------------------------------


class TestListCredentials:
    async def test_list_credentials_empty(self, admin_client, mock_store):
        mock_store.list_credentials.return_value = []
        response = await admin_client.get("/api/credentials")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_credentials_returns_items(self, admin_client, mock_store):
        mock_store.list_credentials.return_value = [_sample_credential()]
        response = await admin_client.get("/api/credentials")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "cred-1"
        assert data[0]["name"] == "API Key for System 1"

    async def test_list_credentials_strips_encrypted_value(
        self, admin_client, mock_store
    ):
        mock_store.list_credentials.return_value = [_sample_credential()]
        response = await admin_client.get("/api/credentials")
        data = response.json()
        assert "encrypted_value" not in data[0]


# ---------------------------------------------------------------------------
# Create Credential
# ---------------------------------------------------------------------------


class TestCreateCredential:
    async def test_create_credential_returns_201(self, admin_client, mock_store):
        cred = _sample_credential()
        response = await admin_client.post(
            "/api/credentials", json=cred.model_dump(mode="json")
        )
        assert response.status_code == 201
        mock_store.create_credential.assert_awaited_once()

    async def test_create_credential_returns_body(self, admin_client, mock_store):
        cred = _sample_credential()
        response = await admin_client.post(
            "/api/credentials", json=cred.model_dump(mode="json")
        )
        data = response.json()
        assert data["id"] == "cred-1"
        assert data["name"] == "API Key for System 1"


# ---------------------------------------------------------------------------
# Update Credential
# ---------------------------------------------------------------------------


class TestUpdateCredential:
    async def test_update_credential_success(self, admin_client, mock_store):
        mock_store.get_credential.return_value = _sample_credential()
        cred = _sample_credential()
        cred.name = "Rotated Key"
        response = await admin_client.put(
            "/api/credentials/cred-1", json=cred.model_dump(mode="json")
        )
        assert response.status_code == 200
        mock_store.update_credential.assert_awaited_once()

    async def test_update_credential_not_found(self, admin_client, mock_store):
        mock_store.get_credential.return_value = None
        cred = _sample_credential()
        response = await admin_client.put(
            "/api/credentials/cred-1", json=cred.model_dump(mode="json")
        )
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Delete Credential
# ---------------------------------------------------------------------------


class TestDeleteCredential:
    async def test_delete_credential_success(self, admin_client, mock_store):
        mock_store.get_credential.return_value = _sample_credential()
        response = await admin_client.delete("/api/credentials/cred-1")
        assert response.status_code == 204
        mock_store.delete_credential.assert_awaited_once_with("cred-1")

    async def test_delete_credential_not_found(self, admin_client, mock_store):
        mock_store.get_credential.return_value = None
        response = await admin_client.delete("/api/credentials/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin-only access
# ---------------------------------------------------------------------------


class TestCredentialsAdminGuard:
    async def test_non_admin_cannot_list_credentials(self, non_admin_client):
        response = await non_admin_client.get("/api/credentials")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_credential(self, non_admin_client):
        cred = _sample_credential()
        response = await non_admin_client.post(
            "/api/credentials", json=cred.model_dump(mode="json")
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_update_credential(self, non_admin_client):
        cred = _sample_credential()
        response = await non_admin_client.put(
            "/api/credentials/cred-1", json=cred.model_dump(mode="json")
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_credential(self, non_admin_client):
        response = await non_admin_client.delete("/api/credentials/cred-1")
        assert response.status_code == 403
