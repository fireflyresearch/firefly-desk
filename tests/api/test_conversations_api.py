# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Conversations API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.auth.models import UserSession
from flydek.conversation.repository import ConversationRepository
from flydek.models.base import Base

# ---------------------------------------------------------------------------
# Shared environment used by all fixtures
# ---------------------------------------------------------------------------

_TEST_ENV = {
    "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
    "FLYDEK_OIDC_CLIENT_ID": "test",
    "FLYDEK_OIDC_CLIENT_SECRET": "test",
    "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
}


# ---------------------------------------------------------------------------
# ASGI middleware that injects a UserSession from a test header
# ---------------------------------------------------------------------------


class _TestUserMiddleware:
    """Read ``X-Test-User-Id`` from request headers and inject a
    :class:`UserSession` into ``scope["state"]`` so that downstream
    handlers (and the DevAuthMiddleware) see the desired user identity.

    If the header is absent the request is passed through untouched and
    the normal DevAuthMiddleware will inject the default dev user.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Extract user_id from headers
            headers = dict(scope.get("headers", []))
            raw = headers.get(b"x-test-user-id")
            if raw is not None:
                user_id = raw.decode()
                scope.setdefault("state", {})
                scope["state"]["user_session"] = UserSession(
                    user_id=user_id,
                    display_name=f"Test User {user_id}",
                    email=f"{user_id}@test.com",
                    roles=["viewer"],
                    permissions=[],
                    session_id=f"test-session-{user_id}",
                    token_expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
                )
        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    with patch.dict(os.environ, _TEST_ENV):
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


@pytest.fixture
async def isolation_client():
    """Client whose app includes :class:`_TestUserMiddleware` so that each
    request can impersonate a different user via the ``X-Test-User-Id``
    header.  Used exclusively by the isolation test suite.
    """
    with patch.dict(os.environ, _TEST_ENV):
        from flydek.api.conversations import get_conversation_repo
        from flydek.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        repo = ConversationRepository(session_factory)
        app.dependency_overrides[get_conversation_repo] = lambda: repo

        # Also store the repo in app.state so the chat ownership guard works
        app.state.conversation_repo = repo

        # Wrap the app with the test-user middleware (outermost layer)
        wrapped = _TestUserMiddleware(app)

        transport = ASGITransport(app=wrapped)
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


# ---------------------------------------------------------------------------
# Cross-user conversation isolation tests
# ---------------------------------------------------------------------------


class TestConversationIsolation:
    """Verify that users cannot access each other's conversations.

    Each request carries an ``X-Test-User-Id`` header that the
    :class:`_TestUserMiddleware` translates into a :class:`UserSession`.
    The API endpoints extract ``user_id`` from this session and the
    repository enforces ownership -- so User B should always receive a
    404 when attempting to interact with User A's conversation.
    """

    USER_A = {"x-test-user-id": "user-a"}
    USER_B = {"x-test-user-id": "user-b"}

    # -- helpers --

    async def _create_conversation(self, client, *, headers, title="Test conv"):
        """Create a conversation and return its id."""
        resp = await client.post(
            "/api/conversations",
            json={"title": title},
            headers=headers,
        )
        assert resp.status_code == 201
        return resp.json()["id"]

    # -- tests --

    async def test_get_conversation_returns_404_for_other_user(
        self, isolation_client
    ):
        """User A creates a conversation; User B gets 404 on GET."""
        conv_id = await self._create_conversation(
            isolation_client, headers=self.USER_A, title="A's private conv"
        )

        resp = await isolation_client.get(
            f"/api/conversations/{conv_id}", headers=self.USER_B
        )
        assert resp.status_code == 404

    async def test_update_conversation_returns_404_for_other_user(
        self, isolation_client
    ):
        """User A creates a conversation; User B gets 404 on PATCH."""
        conv_id = await self._create_conversation(
            isolation_client, headers=self.USER_A
        )

        resp = await isolation_client.patch(
            f"/api/conversations/{conv_id}",
            json={"title": "Hacked!"},
            headers=self.USER_B,
        )
        assert resp.status_code == 404

    async def test_delete_conversation_returns_404_for_other_user(
        self, isolation_client
    ):
        """User A creates a conversation; User B gets 404 on DELETE."""
        conv_id = await self._create_conversation(
            isolation_client, headers=self.USER_A
        )

        resp = await isolation_client.delete(
            f"/api/conversations/{conv_id}", headers=self.USER_B
        )
        assert resp.status_code == 404

    async def test_list_messages_returns_404_for_other_user(
        self, isolation_client
    ):
        """User A creates a conversation; User B gets 404 on GET messages."""
        conv_id = await self._create_conversation(
            isolation_client, headers=self.USER_A
        )

        resp = await isolation_client.get(
            f"/api/conversations/{conv_id}/messages", headers=self.USER_B
        )
        assert resp.status_code == 404

    async def test_send_message_returns_404_for_other_users_conversation(
        self, isolation_client
    ):
        """User A creates a conversation; User B gets 404 on chat send."""
        conv_id = await self._create_conversation(
            isolation_client, headers=self.USER_A
        )

        resp = await isolation_client.post(
            f"/api/chat/conversations/{conv_id}/send",
            json={"message": "Hello from B", "conversation_id": conv_id},
            headers=self.USER_B,
        )
        assert resp.status_code == 404

    async def test_list_conversations_only_returns_own(self, isolation_client):
        """User A and User B each create conversations; each only sees their own."""
        await self._create_conversation(
            isolation_client, headers=self.USER_A, title="A's conv 1"
        )
        await self._create_conversation(
            isolation_client, headers=self.USER_A, title="A's conv 2"
        )
        await self._create_conversation(
            isolation_client, headers=self.USER_B, title="B's conv"
        )

        # User A should see exactly 2 conversations
        resp_a = await isolation_client.get(
            "/api/conversations", headers=self.USER_A
        )
        assert resp_a.status_code == 200
        titles_a = {c["title"] for c in resp_a.json()}
        assert titles_a == {"A's conv 1", "A's conv 2"}

        # User B should see exactly 1 conversation
        resp_b = await isolation_client.get(
            "/api/conversations", headers=self.USER_B
        )
        assert resp_b.status_code == 200
        titles_b = {c["title"] for c in resp_b.json()}
        assert titles_b == {"B's conv"}
