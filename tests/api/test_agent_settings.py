# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Agent Settings REST API endpoints (GET/PUT /api/settings/agent)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.settings.models import AgentSettings


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
    repo.get_agent_settings = AsyncMock(return_value=AgentSettings())
    repo.set_agent_settings = AsyncMock(return_value=None)
    # Needed for other settings endpoints used by the app
    repo.get_user_settings = AsyncMock()
    repo.update_user_settings = AsyncMock()
    repo.get_all_app_settings = AsyncMock(return_value={})
    repo.set_app_setting = AsyncMock(return_value=None)
    repo.get_app_setting = AsyncMock(return_value=None)
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
# GET /api/settings/agent
# ---------------------------------------------------------------------------


class TestGetAgentSettings:
    async def test_returns_defaults(self, admin_client, mock_repo):
        """GET /api/settings/agent returns Ember defaults."""
        mock_repo.get_agent_settings.return_value = AgentSettings()
        response = await admin_client.get("/api/settings/agent")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Ember"
        assert data["display_name"] == "Ember"
        assert data["personality"] == "warm, professional, knowledgeable"
        assert data["tone"] == "friendly yet precise"
        assert data["language"] == "en"
        assert data["behavior_rules"] == []
        assert data["custom_instructions"] == ""
        assert data["avatar_url"] == ""

    async def test_returns_custom_settings(self, admin_client, mock_repo):
        """GET /api/settings/agent returns custom settings from DB."""
        mock_repo.get_agent_settings.return_value = AgentSettings(
            name="Atlas",
            display_name="Atlas Bot",
            personality="formal",
            tone="corporate",
            behavior_rules=["Rule 1"],
        )
        response = await admin_client.get("/api/settings/agent")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Atlas"
        assert data["display_name"] == "Atlas Bot"
        assert data["personality"] == "formal"
        assert data["behavior_rules"] == ["Rule 1"]

    async def test_non_admin_forbidden(self, non_admin_client):
        """Non-admin users should get 403."""
        response = await non_admin_client.get("/api/settings/agent")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# PUT /api/settings/agent
# ---------------------------------------------------------------------------


class TestUpdateAgentSettings:
    async def test_update_settings(self, admin_client, mock_repo):
        """PUT /api/settings/agent updates agent settings."""
        payload = {
            "name": "Nova",
            "display_name": "Nova AI",
            "avatar_url": "https://cdn.example.com/nova.png",
            "personality": "creative, exploratory",
            "tone": "casual",
            "greeting": "Hey! I'm Nova.",
            "behavior_rules": ["Always ask clarifying questions"],
            "custom_instructions": "Focus on creative tasks.",
            "language": "en",
        }
        response = await admin_client.put("/api/settings/agent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Nova"
        assert data["display_name"] == "Nova AI"
        assert data["behavior_rules"] == ["Always ask clarifying questions"]
        mock_repo.set_agent_settings.assert_awaited_once()

    async def test_update_partial_fields(self, admin_client, mock_repo):
        """PUT with only some fields should use defaults for the rest."""
        payload = {"name": "Bolt", "personality": "efficient"}
        response = await admin_client.put("/api/settings/agent", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Bolt"
        assert data["personality"] == "efficient"
        # Defaults for unspecified fields
        assert data["display_name"] == "Ember"  # default from model
        assert data["tone"] == "friendly yet precise"

    async def test_non_admin_forbidden(self, non_admin_client):
        """Non-admin users should get 403."""
        payload = {"name": "Hacker"}
        response = await non_admin_client.put("/api/settings/agent", json=payload)
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Repository integration tests for AgentSettings
# ---------------------------------------------------------------------------


class TestAgentSettingsRepository:
    """Integration tests for get_agent_settings / set_agent_settings."""

    @pytest.fixture
    async def session_factory(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from flydesk.models.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield factory
        await engine.dispose()

    @pytest.fixture
    def repo(self, session_factory):
        from flydesk.settings.repository import SettingsRepository

        return SettingsRepository(session_factory)

    async def test_get_defaults_when_empty(self, repo):
        """get_agent_settings returns defaults when no settings are stored."""
        settings = await repo.get_agent_settings()
        assert settings.name == "Ember"
        assert settings.personality == "warm, professional, knowledgeable"
        assert settings.behavior_rules == []

    async def test_roundtrip(self, repo):
        """set_agent_settings + get_agent_settings preserves all fields."""
        custom = AgentSettings(
            name="Atlas",
            display_name="Atlas Bot",
            avatar_url="https://cdn.example.com/atlas.png",
            personality="formal, authoritative",
            tone="strict",
            greeting="Welcome. I am Atlas.",
            behavior_rules=["Rule 1", "Rule 2"],
            custom_instructions="Focus on compliance.",
            language="es",
        )
        await repo.set_agent_settings(custom)
        result = await repo.get_agent_settings()
        assert result.name == "Atlas"
        assert result.display_name == "Atlas Bot"
        assert result.avatar_url == "https://cdn.example.com/atlas.png"
        assert result.personality == "formal, authoritative"
        assert result.tone == "strict"
        assert result.greeting == "Welcome. I am Atlas."
        assert result.behavior_rules == ["Rule 1", "Rule 2"]
        assert result.custom_instructions == "Focus on compliance."
        assert result.language == "es"

    async def test_overwrite(self, repo):
        """set_agent_settings overwrites existing settings."""
        await repo.set_agent_settings(AgentSettings(name="First"))
        await repo.set_agent_settings(AgentSettings(name="Second"))
        result = await repo.get_agent_settings()
        assert result.name == "Second"

    async def test_does_not_interfere_with_other_categories(self, repo):
        """Agent settings use 'agent' category and don't clash with 'general'."""
        await repo.set_app_setting("agent_name", "FromGeneral", category="general")
        await repo.set_agent_settings(AgentSettings(name="FromAgent"))

        general = await repo.get_all_app_settings(category="general")
        assert general.get("agent_name") == "FromGeneral"

        agent = await repo.get_agent_settings()
        assert agent.name == "FromAgent"

    async def test_empty_behavior_rules_stored_as_json(self, repo):
        """Empty behavior_rules should be stored and restored as an empty list."""
        await repo.set_agent_settings(AgentSettings(behavior_rules=[]))
        result = await repo.get_agent_settings()
        assert result.behavior_rules == []

    async def test_behavior_rules_with_items(self, repo):
        """behavior_rules with items should be stored and restored correctly."""
        rules = ["Never delete data", "Always confirm first"]
        await repo.set_agent_settings(AgentSettings(behavior_rules=rules))
        result = await repo.get_agent_settings()
        assert result.behavior_rules == rules
