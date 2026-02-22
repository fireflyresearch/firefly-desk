# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the LLM Providers Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.llm.models import LLMProvider, ProviderHealthStatus, ProviderType


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


def _sample_provider(provider_id: str = "prov-1") -> LLMProvider:
    return LLMProvider(
        id=provider_id,
        name="Test OpenAI",
        provider_type=ProviderType.OPENAI,
        api_key="sk-secret-key",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
        is_default=False,
        is_active=True,
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics LLMProviderRepository."""
    repo = AsyncMock()
    repo.create_provider = AsyncMock(return_value=None)
    repo.get_provider = AsyncMock(return_value=None)
    repo.get_default_provider = AsyncMock(return_value=None)
    repo.list_providers = AsyncMock(return_value=[])
    repo.update_provider = AsyncMock(return_value=None)
    repo.delete_provider = AsyncMock(return_value=None)
    repo.set_default = AsyncMock(return_value=None)
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked LLMProviderRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.llm_providers import get_llm_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_llm_repo] = lambda: mock_repo

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
        from flydesk.api.llm_providers import get_llm_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_llm_repo] = lambda: mock_repo

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
# CRUD Tests
# ---------------------------------------------------------------------------


class TestListProviders:
    async def test_list_providers_empty(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = []
        response = await admin_client.get("/api/admin/llm-providers")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_providers_returns_items(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = [_sample_provider()]
        response = await admin_client.get("/api/admin/llm-providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "prov-1"
        assert data[0]["name"] == "Test OpenAI"

    async def test_list_providers_hides_api_key(self, admin_client, mock_repo):
        mock_repo.list_providers.return_value = [_sample_provider()]
        response = await admin_client.get("/api/admin/llm-providers")
        data = response.json()
        assert "api_key" not in data[0]
        assert data[0]["has_api_key"] is True


class TestCreateProvider:
    async def test_create_provider(self, admin_client, mock_repo):
        provider = _sample_provider()
        response = await admin_client.post(
            "/api/admin/llm-providers", json=provider.model_dump()
        )
        assert response.status_code == 201
        mock_repo.create_provider.assert_awaited_once()
        data = response.json()
        assert data["id"] == "prov-1"
        assert data["has_api_key"] is True

    async def test_create_provider_returns_body_without_api_key(
        self, admin_client, mock_repo
    ):
        provider = _sample_provider()
        response = await admin_client.post(
            "/api/admin/llm-providers", json=provider.model_dump()
        )
        data = response.json()
        assert "api_key" not in data


class TestGetProvider:
    async def test_get_provider_hides_api_key(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_provider()
        response = await admin_client.get("/api/admin/llm-providers/prov-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "prov-1"
        assert "api_key" not in data
        assert data["has_api_key"] is True

    async def test_get_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.get("/api/admin/llm-providers/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestUpdateProvider:
    async def test_update_provider(self, admin_client, mock_repo):
        original = _sample_provider()
        mock_repo.get_provider.return_value = original
        updated = _sample_provider()
        updated.name = "Updated Name"
        response = await admin_client.put(
            "/api/admin/llm-providers/prov-1", json=updated.model_dump()
        )
        assert response.status_code == 200
        mock_repo.update_provider.assert_awaited_once()

    async def test_update_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        provider = _sample_provider()
        response = await admin_client.put(
            "/api/admin/llm-providers/prov-1", json=provider.model_dump()
        )
        assert response.status_code == 404


class TestDeleteProvider:
    async def test_delete_provider(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = _sample_provider()
        response = await admin_client.delete("/api/admin/llm-providers/prov-1")
        assert response.status_code == 204
        mock_repo.delete_provider.assert_awaited_once_with("prov-1")

    async def test_delete_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.delete("/api/admin/llm-providers/no-such")
        assert response.status_code == 404


class TestSetDefaultProvider:
    async def test_set_default_provider(self, admin_client, mock_repo):
        provider = _sample_provider()
        provider.is_default = True
        # First call returns original, second call returns updated
        mock_repo.get_provider.side_effect = [_sample_provider(), provider]
        response = await admin_client.put("/api/admin/llm-providers/prov-1/default")
        assert response.status_code == 200
        mock_repo.set_default.assert_awaited_once_with("prov-1")
        data = response.json()
        assert data["is_default"] is True

    async def test_set_default_provider_not_found(self, admin_client, mock_repo):
        mock_repo.get_provider.return_value = None
        response = await admin_client.put("/api/admin/llm-providers/no-such/default")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------


class TestAdminGuard:
    async def test_non_admin_cannot_list_providers(self, non_admin_client):
        response = await non_admin_client.get("/api/admin/llm-providers")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_provider(self, non_admin_client):
        provider = _sample_provider()
        response = await non_admin_client.post(
            "/api/admin/llm-providers", json=provider.model_dump()
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_provider(self, non_admin_client):
        response = await non_admin_client.delete("/api/admin/llm-providers/prov-1")
        assert response.status_code == 403
