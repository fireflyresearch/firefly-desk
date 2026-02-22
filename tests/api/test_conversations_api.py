# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Conversations API endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.conversation.repository import ConversationRepository
from flydek.models.base import Base


@pytest.fixture
async def client():
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydek.api.conversations import get_conversation_repo
        from flydek.server import create_app

        app = create_app()

        # Create an in-memory database and wire the dependency override
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = ConversationRepository(session_factory)
        app.dependency_overrides[get_conversation_repo] = lambda: repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


class TestConversationsAPI:
    async def test_list_conversations_empty(self, client):
        """GET /api/conversations returns empty list initially."""
        response = await client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_conversation(self, client):
        """POST /api/conversations creates a new conversation."""
        response = await client.post(
            "/api/conversations",
            json={"title": "My first conversation"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My first conversation"
        assert data["status"] == "active"
        assert data["id"] is not None

    async def test_get_conversation_with_messages(self, client):
        """GET /api/conversations/{id} returns conversation with messages."""
        # Create a conversation
        create_resp = await client.post(
            "/api/conversations",
            json={"title": "Test conversation"},
        )
        conv_id = create_resp.json()["id"]

        # Get conversation (with messages field)
        response = await client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert data["title"] == "Test conversation"
        assert data["messages"] == []

    async def test_rename_conversation(self, client):
        """PATCH /api/conversations/{id} updates the title."""
        # Create a conversation
        create_resp = await client.post(
            "/api/conversations",
            json={"title": "Original title"},
        )
        conv_id = create_resp.json()["id"]

        # Rename it
        response = await client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Updated title"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "Updated title"

    async def test_delete_conversation(self, client):
        """DELETE /api/conversations/{id} soft-deletes the conversation."""
        # Create a conversation
        create_resp = await client.post(
            "/api/conversations",
            json={"title": "To be deleted"},
        )
        conv_id = create_resp.json()["id"]

        # Delete it
        response = await client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 204

        # Should no longer appear in list
        list_resp = await client.get("/api/conversations")
        assert len(list_resp.json()) == 0

    async def test_get_conversation_not_found(self, client):
        """GET /api/conversations/{id} returns 404 for nonexistent."""
        response = await client.get("/api/conversations/nonexistent")
        assert response.status_code == 404

    async def test_list_messages_for_conversation(self, client):
        """GET /api/conversations/{id}/messages returns messages."""
        # Create a conversation
        create_resp = await client.post(
            "/api/conversations",
            json={"title": "Test conversation"},
        )
        conv_id = create_resp.json()["id"]

        # Get messages (should be empty)
        response = await client.get(f"/api/conversations/{conv_id}/messages")
        assert response.status_code == 200
        assert response.json() == []

    async def test_create_and_list_conversations(self, client):
        """Multiple conversations appear in list."""
        await client.post(
            "/api/conversations",
            json={"title": "Conversation 1"},
        )
        await client.post(
            "/api/conversations",
            json={"title": "Conversation 2"},
        )

        response = await client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
