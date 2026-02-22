# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the User Management API endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.audit.logger import AuditLogger
from flydek.audit.models import AuditEvent, AuditEventType
from flydek.conversation.models import Conversation
from flydek.conversation.repository import ConversationRepository
from flydek.models.base import Base
from flydek.settings.repository import SettingsRepository


@pytest.fixture
async def client():
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDEK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydek.api.users import get_session_factory, get_settings_repo
        from flydek.server import create_app

        app = create_app()

        # Create an in-memory database and wire dependency overrides
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        conversation_repo = ConversationRepository(session_factory)
        audit_logger = AuditLogger(session_factory)
        settings_repo = SettingsRepository(session_factory)

        app.dependency_overrides[get_session_factory] = lambda: session_factory
        app.dependency_overrides[get_settings_repo] = lambda: settings_repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, conversation_repo, audit_logger, settings_repo

        await engine.dispose()


class TestUserList:
    async def test_list_users_empty(self, client):
        """GET /api/admin/users returns empty list on fresh DB."""
        ac, _, _, _ = client
        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_users_from_conversations(self, client):
        """Users are discovered from conversation user_ids."""
        ac, conversation_repo, _, _ = client

        await conversation_repo.create_conversation(
            Conversation(id="conv-1", user_id="user-alice", title="Alice chat")
        )
        await conversation_repo.create_conversation(
            Conversation(id="conv-2", user_id="user-bob", title="Bob chat")
        )

        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        user_ids = {u["user_id"] for u in data}
        assert "user-alice" in user_ids
        assert "user-bob" in user_ids

    async def test_list_users_from_audit_events(self, client):
        """Users are discovered from audit event user_ids."""
        ac, _, audit_logger, _ = client

        await audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.AUTH_LOGIN,
                user_id="user-charlie",
                action="login",
                detail={},
            )
        )

        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        user_ids = {u["user_id"] for u in data}
        assert "user-charlie" in user_ids

    async def test_list_users_deduplicates(self, client):
        """Same user_id in conversations and audit appears once."""
        ac, conversation_repo, audit_logger, _ = client

        await conversation_repo.create_conversation(
            Conversation(id="conv-1", user_id="user-shared", title="Shared user")
        )
        await audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.AUTH_LOGIN,
                user_id="user-shared",
                action="login",
                detail={},
            )
        )

        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        user_ids = [u["user_id"] for u in data]
        assert user_ids.count("user-shared") == 1

    async def test_list_users_includes_conversation_count(self, client):
        """User summaries include conversation counts."""
        ac, conversation_repo, _, _ = client

        await conversation_repo.create_conversation(
            Conversation(id="conv-1", user_id="user-active", title="Chat 1")
        )
        await conversation_repo.create_conversation(
            Conversation(id="conv-2", user_id="user-active", title="Chat 2")
        )

        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        active_user = next(u for u in data if u["user_id"] == "user-active")
        assert active_user["conversation_count"] == 2


class TestProfile:
    async def test_get_profile(self, client):
        """GET /api/profile returns the dev user's profile."""
        ac, _, _, _ = client
        response = await ac.get("/api/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "dev-user-001"
        assert data["email"] == "admin@localhost"
        assert data["display_name"] == "Dev Admin"
        assert "admin" in data["roles"]

    async def test_update_preferences(self, client):
        """PUT /api/profile/preferences updates user settings."""
        ac, _, _, _ = client
        response = await ac.put(
            "/api/profile/preferences",
            json={"theme": "dark"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["theme"] == "dark"

    async def test_update_preferences_partial(self, client):
        """Only provided fields are updated; others keep defaults."""
        ac, _, _, _ = client
        response = await ac.put(
            "/api/profile/preferences",
            json={"notifications_enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["notifications_enabled"] is False
        # Default theme should remain
        assert data["theme"] == "system"
