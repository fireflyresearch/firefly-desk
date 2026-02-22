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
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


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
        from flydek.server import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


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
    async def test_send_message_returns_sse_stream(self, client):
        """POST returns 200 with text/event-stream content type."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    async def test_sse_stream_contains_token_events(self, client):
        """Stream contains 'event: token' lines."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        events = parse_sse_events(response.text)
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1

    async def test_sse_stream_ends_with_done(self, client):
        """Last event is 'event: done'."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={"message": "Hello"},
        )
        events = parse_sse_events(response.text)
        assert len(events) > 0
        assert events[-1]["event"] == "done"
        assert events[-1]["data"]["conversation_id"] == "conv-1"

    async def test_sse_event_format(self, client):
        """Each event follows 'event: type\\ndata: json\\n\\n' format."""
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

    async def test_chat_message_validation(self, client):
        """Message body must have 'message' field."""
        response = await client.post(
            "/api/chat/conversations/conv-1/send",
            json={},
        )
        assert response.status_code == 422

    async def test_sse_stream_echoes_message(self, client):
        """Stream echoes the user message as a token event."""
        response = await client.post(
            "/api/chat/conversations/conv-2/send",
            json={"message": "world"},
        )
        events = parse_sse_events(response.text)
        token_events = [e for e in events if e["event"] == "token"]
        contents = [e["data"]["content"] for e in token_events]
        assert "world" in contents

    async def test_sse_headers(self, client):
        """Response includes expected SSE headers."""
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
