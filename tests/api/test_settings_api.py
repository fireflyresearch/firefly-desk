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


# ---------------------------------------------------------------------------
# Embedding Configuration Tests
# ---------------------------------------------------------------------------


class TestGetEmbeddingConfig:
    async def test_returns_default_config(self, admin_client, mock_repo):
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.get("/api/settings/embedding")
        assert response.status_code == 200
        data = response.json()
        assert "embedding_model" in data
        assert "embedding_dimensions" in data
        assert data["embedding_dimensions"] >= 1

    async def test_returns_db_config(self, admin_client, mock_repo):
        mock_repo.get_all_app_settings.return_value = {
            "embedding_model": "voyage:voyage-3",
            "embedding_dimensions": "1024",
            "embedding_api_key": "sk-voyage-secret-key-12345678",
            "embedding_base_url": "https://custom.api.com",
        }
        response = await admin_client.get("/api/settings/embedding")
        assert response.status_code == 200
        data = response.json()
        assert data["embedding_model"] == "voyage:voyage-3"
        assert data["embedding_dimensions"] == 1024
        # API key should be masked
        assert data["embedding_api_key"].startswith("***")
        assert data["embedding_api_key"].endswith("5678")

    async def test_non_admin_cannot_access(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/embedding")
        assert response.status_code == 403


class TestUpdateEmbeddingConfig:
    async def test_saves_embedding_config(self, admin_client, mock_repo):
        mock_repo.get_all_app_settings.return_value = {}
        payload = {
            "embedding_model": "openai:text-embedding-3-large",
            "embedding_api_key": "sk-new-key",
            "embedding_base_url": "",
            "embedding_dimensions": 3072,
        }
        response = await admin_client.put("/api/settings/embedding", json=payload)
        assert response.status_code == 200
        # Should have called set_app_setting for each field
        assert mock_repo.set_app_setting.await_count >= 3

    async def test_non_admin_cannot_update(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/settings/embedding",
            json={"embedding_model": "openai:text-embedding-3-small"},
        )
        assert response.status_code == 403


class TestEmbeddingTest:
    async def test_non_admin_cannot_test(self, non_admin_client):
        response = await non_admin_client.post("/api/settings/embedding/test")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Knowledge Quality Configuration
# ---------------------------------------------------------------------------


class TestGetKnowledgeConfig:
    async def test_returns_defaults_when_no_db_settings(self, admin_client, mock_repo):
        """GET /settings/knowledge returns defaults when no DB values are set."""
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.get("/api/settings/knowledge")
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_size"] == 500
        assert data["chunk_overlap"] == 50
        assert data["chunking_mode"] == "auto"
        assert data["auto_kg_extract"] is True

    async def test_returns_db_values_when_set(self, admin_client, mock_repo):
        """GET /settings/knowledge returns values from DB settings."""
        mock_repo.get_all_app_settings.return_value = {
            "chunk_size": "1000",
            "chunk_overlap": "100",
            "chunking_mode": "structural",
            "auto_kg_extract": "false",
        }
        response = await admin_client.get("/api/settings/knowledge")
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_size"] == 1000
        assert data["chunk_overlap"] == 100
        assert data["chunking_mode"] == "structural"
        assert data["auto_kg_extract"] is False

    async def test_non_admin_cannot_access(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/knowledge")
        assert response.status_code == 403


class TestUpdateKnowledgeConfig:
    async def test_saves_knowledge_config(self, admin_client, mock_repo):
        """PUT /settings/knowledge saves all knowledge quality fields."""
        mock_repo.get_all_app_settings.return_value = {}
        payload = {
            "chunk_size": 750,
            "chunk_overlap": 75,
            "chunking_mode": "structural",
            "auto_kg_extract": False,
        }
        response = await admin_client.put("/api/settings/knowledge", json=payload)
        assert response.status_code == 200
        # Should have called set_app_setting for each of the 4 fields
        assert mock_repo.set_app_setting.await_count >= 4

    async def test_non_admin_cannot_update(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/settings/knowledge",
            json={"chunk_size": 500, "chunk_overlap": 50, "chunking_mode": "auto", "auto_kg_extract": True},
        )
        assert response.status_code == 403


class TestEmbeddingStatus:
    async def test_non_admin_cannot_check_status(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/embedding/status")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Process Discovery Configuration
# ---------------------------------------------------------------------------


class TestGetProcessDiscoveryConfig:
    async def test_returns_defaults_when_no_db_settings(self, admin_client, mock_repo):
        """GET /settings/process-discovery returns defaults when no DB values."""
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.get("/api/settings/process-discovery")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == []
        assert data["document_types"] == []
        assert data["focus_hint"] == ""

    async def test_returns_db_values_when_set(self, admin_client, mock_repo):
        """GET /settings/process-discovery returns persisted values."""
        mock_repo.get_all_app_settings.return_value = {
            "workspace_ids": '["ws-1", "ws-2"]',
            "document_types": '["manual", "faq"]',
            "focus_hint": "Focus on onboarding workflows",
        }
        response = await admin_client.get("/api/settings/process-discovery")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == ["ws-1", "ws-2"]
        assert data["document_types"] == ["manual", "faq"]
        assert data["focus_hint"] == "Focus on onboarding workflows"

    async def test_non_admin_cannot_access(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/process-discovery")
        assert response.status_code == 403


class TestUpdateProcessDiscoveryConfig:
    async def test_saves_process_discovery_config(self, admin_client, mock_repo):
        """PUT /settings/process-discovery saves all fields."""
        payload = {
            "workspace_ids": ["ws-1"],
            "document_types": ["manual", "tutorial"],
            "focus_hint": "Focus on HR processes",
        }
        response = await admin_client.put(
            "/api/settings/process-discovery", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == ["ws-1"]
        assert data["document_types"] == ["manual", "tutorial"]
        assert data["focus_hint"] == "Focus on HR processes"
        # 3 fields: workspace_ids, document_types, focus_hint
        assert mock_repo.set_app_setting.await_count == 3

    async def test_saves_empty_config(self, admin_client, mock_repo):
        """PUT /settings/process-discovery with empty lists is valid."""
        payload = {"workspace_ids": [], "document_types": [], "focus_hint": ""}
        response = await admin_client.put(
            "/api/settings/process-discovery", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == []
        assert data["document_types"] == []

    async def test_non_admin_cannot_update(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/settings/process-discovery",
            json={"workspace_ids": [], "document_types": [], "focus_hint": ""},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# System Discovery Configuration
# ---------------------------------------------------------------------------


class TestGetSystemDiscoveryConfig:
    async def test_returns_defaults_when_no_db_settings(self, admin_client, mock_repo):
        """GET /settings/system-discovery returns defaults when no DB values."""
        mock_repo.get_all_app_settings.return_value = {}
        response = await admin_client.get("/api/settings/system-discovery")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == []
        assert data["document_types"] == []
        assert data["focus_hint"] == ""
        assert data["confidence_threshold"] == 0.5

    async def test_returns_db_values_when_set(self, admin_client, mock_repo):
        """GET /settings/system-discovery returns persisted values."""
        mock_repo.get_all_app_settings.return_value = {
            "workspace_ids": '["ws-3"]',
            "document_types": '["api_spec", "reference"]',
            "focus_hint": "Look for CRM integrations",
            "confidence_threshold": "0.7",
        }
        response = await admin_client.get("/api/settings/system-discovery")
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == ["ws-3"]
        assert data["document_types"] == ["api_spec", "reference"]
        assert data["focus_hint"] == "Look for CRM integrations"
        assert data["confidence_threshold"] == 0.7

    async def test_non_admin_cannot_access(self, non_admin_client):
        response = await non_admin_client.get("/api/settings/system-discovery")
        assert response.status_code == 403


class TestUpdateSystemDiscoveryConfig:
    async def test_saves_system_discovery_config(self, admin_client, mock_repo):
        """PUT /settings/system-discovery saves all fields."""
        payload = {
            "workspace_ids": ["ws-1", "ws-2"],
            "document_types": ["policy"],
            "focus_hint": "ERP systems only",
            "confidence_threshold": 0.8,
        }
        response = await admin_client.put(
            "/api/settings/system-discovery", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["workspace_ids"] == ["ws-1", "ws-2"]
        assert data["document_types"] == ["policy"]
        assert data["focus_hint"] == "ERP systems only"
        assert data["confidence_threshold"] == 0.8
        # 4 fields: workspace_ids, document_types, focus_hint, confidence_threshold
        assert mock_repo.set_app_setting.await_count == 4

    async def test_saves_empty_config(self, admin_client, mock_repo):
        """PUT /settings/system-discovery with defaults is valid."""
        payload = {
            "workspace_ids": [],
            "document_types": [],
            "focus_hint": "",
            "confidence_threshold": 0.5,
        }
        response = await admin_client.put(
            "/api/settings/system-discovery", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["confidence_threshold"] == 0.5

    async def test_non_admin_cannot_update(self, non_admin_client):
        response = await non_admin_client.put(
            "/api/settings/system-discovery",
            json={
                "workspace_ids": [],
                "document_types": [],
                "focus_hint": "",
                "confidence_threshold": 0.5,
            },
        )
        assert response.status_code == 403
