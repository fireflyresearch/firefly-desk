# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for file upload integration in the Chat API."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydek.api.chat import ChatMessage, _persist_messages
from flydek.conversation.models import Conversation, Message, MessageRole
from flydek.files.models import FileUpload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# ChatMessage model tests
# ---------------------------------------------------------------------------


class TestChatMessageFileIds:
    """Tests for the file_ids field on ChatMessage."""

    def test_chat_message_accepts_file_ids(self):
        """ChatMessage can be constructed with file_ids."""
        msg = ChatMessage(message="Hello", file_ids=["f-1", "f-2"])
        assert msg.file_ids == ["f-1", "f-2"]

    def test_chat_message_file_ids_defaults_to_empty(self):
        """ChatMessage.file_ids defaults to an empty list when omitted."""
        msg = ChatMessage(message="Hello")
        assert msg.file_ids == []

    def test_chat_message_file_ids_with_conversation_id(self):
        """file_ids coexists with conversation_id."""
        msg = ChatMessage(
            message="Please review",
            conversation_id="conv-42",
            file_ids=["f-abc"],
        )
        assert msg.conversation_id == "conv-42"
        assert msg.file_ids == ["f-abc"]
        assert msg.message == "Please review"

    def test_chat_message_empty_file_ids_list(self):
        """An explicitly empty file_ids list is accepted."""
        msg = ChatMessage(message="Hi", file_ids=[])
        assert msg.file_ids == []


# ---------------------------------------------------------------------------
# _persist_messages file_ids wiring tests
# ---------------------------------------------------------------------------


class TestPersistMessagesFileIds:
    """Tests that _persist_messages forwards file_ids to the repository."""

    async def test_persist_messages_passes_file_ids_to_user_message(self):
        """file_ids should be set on the user Message passed to repo.add_message."""
        mock_repo = AsyncMock()
        mock_repo.get_conversation = AsyncMock(
            return_value=Conversation(id="conv-1", user_id="user-1")
        )
        mock_repo.add_message = AsyncMock()

        mock_request = MagicMock()
        mock_request.app.state.conversation_repo = mock_repo
        mock_request.state.user_session = MagicMock(user_id="user-1")

        await _persist_messages(
            mock_request,
            "conv-1",
            "Hello",
            "Hi there",
            file_ids=["f-1", "f-2"],
        )

        # Two calls: user message and assistant message
        assert mock_repo.add_message.await_count == 2
        user_msg: Message = mock_repo.add_message.call_args_list[0][0][0]
        assert user_msg.file_ids == ["f-1", "f-2"]
        assert user_msg.role == MessageRole.USER

    async def test_persist_messages_no_file_ids_defaults_to_empty(self):
        """When file_ids is None, user Message.file_ids should be an empty list."""
        mock_repo = AsyncMock()
        mock_repo.get_conversation = AsyncMock(
            return_value=Conversation(id="conv-1", user_id="user-1")
        )
        mock_repo.add_message = AsyncMock()

        mock_request = MagicMock()
        mock_request.app.state.conversation_repo = mock_repo
        mock_request.state.user_session = MagicMock(user_id="user-1")

        await _persist_messages(mock_request, "conv-1", "Hello", "Reply")

        user_msg: Message = mock_repo.add_message.call_args_list[0][0][0]
        assert user_msg.file_ids == []

    async def test_persist_messages_assistant_has_no_file_ids(self):
        """Assistant messages should not carry file_ids."""
        mock_repo = AsyncMock()
        mock_repo.get_conversation = AsyncMock(
            return_value=Conversation(id="conv-1", user_id="user-1")
        )
        mock_repo.add_message = AsyncMock()

        mock_request = MagicMock()
        mock_request.app.state.conversation_repo = mock_repo
        mock_request.state.user_session = MagicMock(user_id="user-1")

        await _persist_messages(
            mock_request, "conv-1", "Q", "A", file_ids=["f-x"],
        )

        assistant_msg: Message = mock_repo.add_message.call_args_list[1][0][0]
        assert assistant_msg.file_ids == []
        assert assistant_msg.role == MessageRole.ASSISTANT


# ---------------------------------------------------------------------------
# DeskAgent._build_file_context unit tests
# ---------------------------------------------------------------------------


class TestBuildFileContext:
    """Unit tests for DeskAgent._build_file_context."""

    def _make_agent(self, file_repo=None):
        """Create a DeskAgent with minimal mocked dependencies."""
        from flydek.agent.desk_agent import DeskAgent

        return DeskAgent(
            context_enricher=MagicMock(enrich=AsyncMock()),
            prompt_builder=MagicMock(),
            tool_factory=MagicMock(),
            widget_parser=MagicMock(),
            audit_logger=MagicMock(log=AsyncMock()),
            file_repo=file_repo,
        )

    async def test_build_file_context_returns_formatted_text(self):
        """Fetched files are formatted as '- [filename]: text' lines."""
        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(
            side_effect=lambda fid: FileUpload(
                id=fid,
                user_id="u-1",
                filename=f"doc-{fid}.pdf",
                content_type="application/pdf",
                file_size=1024,
                storage_path=f"/tmp/{fid}",
                extracted_text=f"Content of {fid}",
            )
        )
        agent = self._make_agent(file_repo=mock_repo)

        result = await agent._build_file_context(["f-1", "f-2"])

        assert "- [doc-f-1.pdf]: Content of f-1" in result
        assert "- [doc-f-2.pdf]: Content of f-2" in result

    async def test_build_file_context_skips_missing_files(self):
        """Files that return None are silently skipped."""
        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(
            side_effect=lambda fid: None if fid == "f-missing" else FileUpload(
                id=fid,
                user_id="u-1",
                filename="found.txt",
                content_type="text/plain",
                file_size=100,
                storage_path="/tmp/found",
                extracted_text="Found content",
            )
        )
        agent = self._make_agent(file_repo=mock_repo)

        result = await agent._build_file_context(["f-missing", "f-ok"])

        assert "found.txt" in result
        assert "f-missing" not in result

    async def test_build_file_context_skips_empty_extracted_text(self):
        """Files with no extracted_text are skipped."""
        mock_repo = AsyncMock()
        mock_repo.get = AsyncMock(
            return_value=FileUpload(
                id="f-1",
                user_id="u-1",
                filename="image.png",
                content_type="image/png",
                file_size=2048,
                storage_path="/tmp/image.png",
                extracted_text="",
            )
        )
        agent = self._make_agent(file_repo=mock_repo)

        result = await agent._build_file_context(["f-1"])

        assert result == ""

    async def test_build_file_context_empty_when_no_file_ids(self):
        """Returns empty string when file_ids is None."""
        mock_repo = AsyncMock()
        agent = self._make_agent(file_repo=mock_repo)

        result = await agent._build_file_context(None)

        assert result == ""
        mock_repo.get.assert_not_awaited()

    async def test_build_file_context_empty_when_no_repo(self):
        """Returns empty string when file_repo is not configured."""
        agent = self._make_agent(file_repo=None)

        result = await agent._build_file_context(["f-1"])

        assert result == ""


# ---------------------------------------------------------------------------
# System prompt file context section tests
# ---------------------------------------------------------------------------


class TestFileContextInPrompt:
    """Tests that file_context flows into the system prompt."""

    def test_file_context_section_included_when_set(self):
        """File context section appears in the prompt when file_context is non-empty."""
        from flydek.agent.prompt import PromptContext, SystemPromptBuilder

        builder = SystemPromptBuilder()
        ctx = PromptContext(
            file_context="- [report.pdf]: Q1 revenue was $10M",
        )
        prompt = builder.build(ctx)

        assert "# Attached Files" in prompt
        assert "The user has attached the following files:" in prompt
        assert "- [report.pdf]: Q1 revenue was $10M" in prompt

    def test_file_context_section_excluded_when_empty(self):
        """File context section is omitted when file_context is empty."""
        from flydek.agent.prompt import PromptContext, SystemPromptBuilder

        builder = SystemPromptBuilder()
        ctx = PromptContext(file_context="")
        prompt = builder.build(ctx)

        assert "# Attached Files" not in prompt


# ---------------------------------------------------------------------------
# SSE streaming with file_ids (integration-level)
# ---------------------------------------------------------------------------


class TestSSEStreamWithFileIds:
    """Tests that SSE streaming works normally when file_ids are present."""

    async def test_send_message_with_file_ids_returns_sse_stream(self, client):
        """POST with file_ids returns 200 with SSE content type."""
        response = await client.post(
            "/api/chat/conversations/conv-files-1/send",
            json={"message": "Analyze the report", "file_ids": ["f-1"]},
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    async def test_sse_stream_with_file_ids_ends_with_done(self, client):
        """SSE stream with file_ids ends with a done event."""
        response = await client.post(
            "/api/chat/conversations/conv-files-2/send",
            json={"message": "Summarize", "file_ids": ["f-1", "f-2"]},
        )
        events = parse_sse_events(response.text)
        assert len(events) > 0
        assert events[-1]["event"] == "done"
        assert events[-1]["data"]["conversation_id"] == "conv-files-2"

    async def test_sse_stream_with_empty_file_ids(self, client):
        """An empty file_ids list behaves the same as no file_ids."""
        response = await client.post(
            "/api/chat/conversations/conv-files-3/send",
            json={"message": "Hello", "file_ids": []},
        )
        events = parse_sse_events(response.text)
        token_events = [e for e in events if e["event"] == "token"]
        assert len(token_events) >= 1
        assert events[-1]["event"] == "done"
