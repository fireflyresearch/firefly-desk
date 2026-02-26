# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Chat API with SSE streaming."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.api.events import SSEEvent, SSEEventType


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.server import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


def _make_mock_desk_agent(events: list[SSEEvent] | None = None):
    """Create a mock DeskAgent with stream() and run_with_reasoning() methods.

    Both methods return async generators that yield the given events.
    When no events are provided, default token + done events are used.
    """
    if events is None:
        events = [
            SSEEvent(event=SSEEventType.TOKEN, data={"content": "Hello!"}),
            SSEEvent(event=SSEEventType.DONE, data={"conversation_id": "conv-1"}),
        ]

    async def _gen(*args, **kwargs):
        for e in events:
            yield e

    agent = MagicMock()
    agent.stream = MagicMock(side_effect=_gen)
    agent.run_with_reasoning = MagicMock(side_effect=_gen)
    return agent


def _make_mock_user_session():
    """Create a minimal mock UserSession."""
    session = MagicMock()
    session.user_id = "test-user"
    session.display_name = "Test User"
    session.roles = ["user"]
    session.permissions = []
    session.department = None
    session.title = None
    return session


@pytest.fixture
async def client_with_agent():
    """Client with a mock DeskAgent and UserSession attached to app.state."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.server import create_app

        app = create_app()

        mock_agent = _make_mock_desk_agent()
        mock_session = _make_mock_user_session()
        app.state.desk_agent = mock_agent

        # Middleware that injects user_session into request.state
        from starlette.middleware.base import BaseHTTPMiddleware

        class InjectSessionMiddleware(BaseHTTPMiddleware):
            async def dispatch(self, request, call_next):
                request.state.user_session = mock_session
                return await call_next(request)

        app.add_middleware(InjectSessionMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, mock_agent


def parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into a list of event dicts with 'event' and 'data' keys."""
    events = []
    for block in text.strip().split("\n\n"):
        event = {}
        for line in block.strip().split("\n"):
            if line.startswith("event: "):
                event["event"] = line[len("event: "):]
            elif line.startswith("data: "):
                event["data"] = json.loads(line[len("data: "):])
        if event:
            events.append(event)
    return events


class TestSendMessage:
    async def test_no_agent_returns_503(self, client):
        """POST without a configured DeskAgent returns 503."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]

    async def test_chat_message_validation(self, client):
        """Message body must have 'message' field."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={},
        )
        assert response.status_code == 422

    async def test_send_message_returns_sse_stream(self, client_with_agent):
        """POST returns 200 with text/event-stream content type."""
        client, _ = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    async def test_sse_stream_contains_token_events(self, client_with_agent):
        """Stream contains 'event: token' lines."""
        client, _ = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        events = parse_sse_events(response.text)
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1

    async def test_sse_stream_ends_with_done(self, client_with_agent):
        """Last event is 'event: done'."""
        client, _ = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        events = parse_sse_events(response.text)
        assert len(events) > 0
        assert events[-1]["event"] == "done"
        assert events[-1]["data"]["conversation_id"] == "conv-1"

    async def test_sse_event_format(self, client_with_agent):
        """Each event follows 'event: type\\ndata: json\\n\\n' format."""
        client, _ = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        raw = response.text
        # Each event block is separated by double newlines
        blocks = raw.strip().split("\n\n")
        assert len(blocks) >= 2  # At least a token and a done event

        for block in blocks:
            lines = block.strip().split("\n")
            assert len(lines) == 2, f"Expected 2 lines per event block, got {len(lines)}: {block!r}"
            assert lines[0].startswith("event: "), f"First line must start with 'event: ': {lines[0]!r}"
            assert lines[1].startswith("data: "), f"Second line must start with 'data: ': {lines[1]!r}"
            # Data must be valid JSON
            json.loads(lines[1][len("data: "):])

    async def test_sse_headers(self, client_with_agent):
        """Response includes expected SSE headers."""
        client, _ = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"


class TestGetSuggestions:
    async def test_suggestions_returns_list(self, client):
        """GET /api/chat/suggestions returns a suggestions list."""
        response = await client.get("/api/chat/suggestions")
        assert response.status_code == 200
        data = response.json()
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)
        assert len(data["suggestions"]) >= 1

    async def test_suggestion_items_have_required_fields(self, client):
        """Each suggestion item has icon, title, description, and text."""
        response = await client.get("/api/chat/suggestions")
        data = response.json()
        for item in data["suggestions"]:
            assert "icon" in item
            assert "title" in item
            assert "description" in item
            assert "text" in item
            assert isinstance(item["icon"], str)
            assert isinstance(item["title"], str)
            assert isinstance(item["text"], str)


class TestChatMessageModel:
    """Tests for the ChatMessage Pydantic model."""

    def test_default_reasoning_fields(self):
        """ChatMessage defaults reasoning=False and pattern=None."""
        from flydesk.api.chat import ChatMessage

        msg = ChatMessage(message="Hello")
        assert msg.reasoning is False
        assert msg.pattern is None

    def test_reasoning_flag_accepted(self):
        """ChatMessage accepts reasoning=True."""
        from flydesk.api.chat import ChatMessage

        msg = ChatMessage(message="Hello", reasoning=True)
        assert msg.reasoning is True

    def test_pattern_field_accepted(self):
        """ChatMessage accepts pattern string."""
        from flydesk.api.chat import ChatMessage

        msg = ChatMessage(message="Hello", pattern="react")
        assert msg.pattern == "react"

    def test_reasoning_and_pattern_together(self):
        """ChatMessage accepts both reasoning and pattern."""
        from flydesk.api.chat import ChatMessage

        msg = ChatMessage(message="Hello", reasoning=True, pattern="plan_and_execute")
        assert msg.reasoning is True
        assert msg.pattern == "plan_and_execute"


class TestReasoningApiPath:
    """Tests for the reasoning code path in the send_message endpoint."""

    async def test_standard_message_calls_stream(self, client_with_agent):
        """Without reasoning flag, agent.stream() is called, not run_with_reasoning()."""
        client, mock_agent = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        mock_agent.stream.assert_called_once()
        mock_agent.run_with_reasoning.assert_not_called()

    async def test_reasoning_true_calls_run_with_reasoning(self, client_with_agent):
        """With reasoning=true, agent.run_with_reasoning() is called."""
        client, mock_agent = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Analyze this", "reasoning": True},
        )
        assert response.status_code == 200
        mock_agent.run_with_reasoning.assert_called_once()
        mock_agent.stream.assert_not_called()

    async def test_pattern_field_calls_run_with_reasoning(self, client_with_agent):
        """With pattern specified, agent.run_with_reasoning() is called."""
        client, mock_agent = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Plan this", "pattern": "plan_and_execute"},
        )
        assert response.status_code == 200
        mock_agent.run_with_reasoning.assert_called_once()
        # Verify the pattern is passed through
        call_kwargs = mock_agent.run_with_reasoning.call_args
        assert call_kwargs.kwargs.get("pattern") == "plan_and_execute"

    async def test_reasoning_with_auto_pattern(self, client_with_agent):
        """With reasoning=true and no pattern, default pattern is 'auto'."""
        client, mock_agent = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Think about this", "reasoning": True},
        )
        assert response.status_code == 200
        call_kwargs = mock_agent.run_with_reasoning.call_args
        assert call_kwargs.kwargs.get("pattern") == "auto"

    async def test_reasoning_stream_yields_sse_events(self, client_with_agent):
        """Reasoning path should yield SSE events in the response body."""
        client, mock_agent = client_with_agent

        # Set up reasoning events
        reasoning_events = [
            SSEEvent(event=SSEEventType.REASONING_STEP, data={
                "step_number": 1, "step_type": "thought",
                "description": "Analyzing", "status": "completed",
            }),
            SSEEvent(event=SSEEventType.TOKEN, data={"content": "Result"}),
            SSEEvent(event=SSEEventType.DONE, data={"conversation_id": "conv-1"}),
        ]

        async def _reasoning_gen(*args, **kwargs):
            for e in reasoning_events:
                yield e

        mock_agent.run_with_reasoning = MagicMock(side_effect=_reasoning_gen)

        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Think", "reasoning": True},
        )
        events = parse_sse_events(response.text)
        event_types = [e["event"] for e in events]
        assert "reasoning_step" in event_types
        assert "token" in event_types
        assert "done" in event_types

    async def test_reasoning_false_does_not_trigger_reasoning(self, client_with_agent):
        """Explicitly setting reasoning=false should use standard stream."""
        client, mock_agent = client_with_agent
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello", "reasoning": False},
        )
        assert response.status_code == 200
        mock_agent.stream.assert_called_once()
        mock_agent.run_with_reasoning.assert_not_called()
