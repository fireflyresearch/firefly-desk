# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the inbound email webhook endpoint (POST /api/email/inbound/{provider})."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.channels.models import AgentResponse, InboundMessage
from flydesk.settings.models import EmailSettings

# DeskAgent's response type (distinct from channels.models.AgentResponse)
from flydesk.agent.response import AgentResponse as DeskAgentResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_inbound_message(
    *,
    conversation_id: str = "conv-001",
    user_id: str = "user-1",
    content: str = "Hello, I need help with my account.",
) -> InboundMessage:
    """Build a minimal InboundMessage for testing."""
    return InboundMessage(
        channel="email",
        user_id=user_id,
        conversation_id=conversation_id,
        content=content,
        metadata={"subject": "Help request", "message_id": "<msg@example.com>"},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_adapter():
    """Return an AsyncMock that mimics EmailChannelAdapter."""
    adapter = AsyncMock()
    adapter.receive = AsyncMock(return_value=_make_inbound_message())
    adapter.send = AsyncMock(return_value=None)
    return adapter


@pytest.fixture
def mock_settings_repo():
    """Return an AsyncMock that mimics SettingsRepository."""
    repo = AsyncMock()
    # Default: email enabled with auto_reply on.
    repo.get_email_settings = AsyncMock(
        return_value=EmailSettings(enabled=True, auto_reply=True)
    )
    # Also mock methods that may be called by the app during startup.
    repo.get_all_app_settings = AsyncMock(return_value={})
    repo.get_app_setting = AsyncMock(return_value=None)
    repo.get_user_settings = AsyncMock()
    repo.update_user_settings = AsyncMock()
    return repo


@pytest.fixture
def mock_desk_agent():
    """Return an AsyncMock that mimics DeskAgent."""
    agent = AsyncMock()
    agent.run = AsyncMock(return_value=DeskAgentResponse(
        text="I can help you with that.",
        turn_id="turn-1",
        conversation_id="conv-001",
    ))
    return agent


@pytest.fixture
def mock_conversation_repo():
    """Return an AsyncMock that mimics ConversationRepository."""
    repo = AsyncMock()
    repo.get_conversation = AsyncMock(return_value=None)  # new conversation by default
    repo.create_conversation = AsyncMock()
    repo.add_message = AsyncMock()
    return repo


@pytest.fixture
async def client(mock_adapter, mock_settings_repo, mock_desk_agent, mock_conversation_repo):
    """AsyncClient with mocked adapter and settings repo dependencies.

    The inbound email webhook is intended for external providers, so we
    add the path to the public prefixes for testing (in production this
    would be done in the auth middleware configuration).
    """
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_email_channel_adapter, get_settings_repo
        from flydesk.server import create_app

        app = create_app()

        app.dependency_overrides[get_email_channel_adapter] = lambda: mock_adapter
        app.dependency_overrides[get_settings_repo] = lambda: mock_settings_repo

        # Set DeskAgent and ConversationRepository on app state
        app.state.desk_agent = mock_desk_agent
        app.state.conversation_repo = mock_conversation_repo

        # Bypass auth middleware by injecting a user session.
        from flydesk.auth.models import UserSession

        user_session = UserSession(
            user_id="webhook",
            email="webhook@system.internal",
            display_name="Webhook",
            roles=["admin"],
            permissions=["*"],
            tenant_id="system",
            session_id="webhook-sess",
            token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
            raw_claims={},
        )

        async def _set_user(request, call_next):
            request.state.user_session = user_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Invalid provider
# ---------------------------------------------------------------------------


class TestInvalidProvider:
    async def test_unknown_provider_returns_400(self, client):
        """POST /api/email/inbound/mailgun should return 400."""
        response = await client.post(
            "/api/email/inbound/mailgun",
            content=b'{"from": "user@example.com"}',
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert "Unknown email provider" in response.json()["detail"]

    async def test_invalid_json_returns_400(self, client):
        """POST with non-JSON body should return 400."""
        response = await client.post(
            "/api/email/inbound/resend",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Unknown sender (adapter.receive returns None)
# ---------------------------------------------------------------------------


class TestUnknownSender:
    async def test_unknown_sender_returns_skipped(self, client, mock_adapter):
        """When the adapter cannot resolve the sender, return 'skipped'."""
        mock_adapter.receive.return_value = None

        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "stranger@unknown.com", "subject": "Hello"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "skipped"
        assert data["reason"] == "unknown_sender"

        mock_adapter.receive.assert_awaited_once()
        mock_adapter.send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Auto-reply disabled
# ---------------------------------------------------------------------------


class TestAutoReplyDisabled:
    async def test_auto_reply_off_returns_stored(
        self, client, mock_adapter, mock_settings_repo
    ):
        """When auto_reply is disabled, store the message but don't reply."""
        mock_settings_repo.get_email_settings.return_value = EmailSettings(
            enabled=True, auto_reply=False
        )

        response = await client.post(
            "/api/email/inbound/ses",
            json={"from": "user@example.com", "subject": "Help"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "stored"
        assert data["conversation_id"] == "conv-001"

        # Adapter receive was called but send was not.
        mock_adapter.receive.assert_awaited_once()
        mock_adapter.send.assert_not_awaited()


# ---------------------------------------------------------------------------
# Successful processing (full pipeline)
# ---------------------------------------------------------------------------


class TestSuccessfulProcessing:
    async def test_full_pipeline_returns_processed(
        self, client, mock_adapter, mock_settings_repo, mock_desk_agent
    ):
        """Full pipeline: receive -> agent reply -> send -> 'processed'."""
        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com", "subject": "Help me"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "processed"
        assert data["conversation_id"] == "conv-001"

        # Adapter receive + send were both called.
        mock_adapter.receive.assert_awaited_once()
        mock_adapter.send.assert_awaited_once()

        # DeskAgent was invoked.
        mock_desk_agent.run.assert_awaited_once()

        # Verify send was called with the correct conversation_id and an AgentResponse.
        call_args = mock_adapter.send.call_args
        assert call_args[0][0] == "conv-001"
        agent_resp = call_args[0][1]
        assert isinstance(agent_resp, AgentResponse)
        assert agent_resp.content == "I can help you with that."

    async def test_ses_provider_accepted(self, client, mock_adapter):
        """SES provider should also work end-to-end."""
        response = await client.post(
            "/api/email/inbound/ses",
            json={"from": "user@example.com", "body": "Need help"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

    async def test_adapter_receive_called_with_provider(
        self, client, mock_adapter
    ):
        """The adapter should receive the provider name and parsed payload."""
        payload = {"from": "user@example.com", "subject": "Test"}
        await client.post("/api/email/inbound/resend", json=payload)

        call_args = mock_adapter.receive.call_args[0][0]
        assert call_args["provider"] == "resend"
        assert call_args["payload"] == payload

    async def test_agent_reply_response_metadata(
        self, client, mock_adapter, mock_settings_repo
    ):
        """The agent reply AgentResponse should have appropriate metadata."""
        await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com"},
        )

        agent_resp = mock_adapter.send.call_args[0][1]
        assert agent_resp.metadata.get("source") == "agent"
        assert agent_resp.metadata.get("channel") == "email"

    async def test_agent_creates_conversation_when_new(
        self, client, mock_adapter, mock_conversation_repo
    ):
        """When no existing conversation, the endpoint creates one and persists messages."""
        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com", "subject": "New request"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

        # Conversation was created since get_conversation returned None.
        mock_conversation_repo.create_conversation.assert_awaited_once()

        # Two messages persisted: user message + assistant reply.
        assert mock_conversation_repo.add_message.await_count == 2

    async def test_existing_conversation_not_recreated(
        self, client, mock_adapter, mock_conversation_repo
    ):
        """When a conversation already exists, it should not be recreated."""
        from flydesk.conversation.models import Conversation

        mock_conversation_repo.get_conversation.return_value = Conversation(
            id="conv-001",
            title="Existing conversation",
            user_id="user-1",
            metadata={"channel": "email"},
        )

        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com", "subject": "Follow-up"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "processed"

        # create_conversation should NOT have been called.
        mock_conversation_repo.create_conversation.assert_not_awaited()

        # Messages still persisted.
        assert mock_conversation_repo.add_message.await_count == 2

    async def test_agent_error_returns_error_status(
        self, client, mock_adapter, mock_desk_agent
    ):
        """When DeskAgent.run raises, return error status."""
        mock_desk_agent.run.side_effect = RuntimeError("LLM timeout")

        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com", "subject": "Help"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["reason"] == "agent_error"

        # Adapter send should NOT have been called since agent failed.
        mock_adapter.send.assert_not_awaited()

    async def test_agent_not_configured_returns_error(self, client, mock_adapter):
        """When desk_agent is not on app.state, return error."""
        # Remove desk_agent from app state
        transport = client._transport
        app = transport.app
        app.state.desk_agent = None

        response = await client.post(
            "/api/email/inbound/resend",
            json={"from": "user@example.com", "subject": "Help"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "error"
        assert data["reason"] == "agent_not_configured"

        mock_adapter.send.assert_not_awaited()
