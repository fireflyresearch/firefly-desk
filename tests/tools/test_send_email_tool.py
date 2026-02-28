# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the send_email built-in tool (definition, registry, handler)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.tools.builtin import BuiltinToolExecutor, BuiltinToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@dataclass
class _FakeEmailSettings:
    enabled: bool = True
    provider: str = "resend"
    provider_api_key: str = "re_test_key"
    from_address: str = "ember@flydesk.ai"
    from_display_name: str = "Ember"
    reply_to: str = ""
    signature_html: str = "<p>-- Ember</p>"


@dataclass
class _FakeSendResult:
    success: bool = True
    provider_message_id: str | None = "msg-123"
    error: str | None = None


@pytest.fixture
def settings_repo():
    repo = AsyncMock()
    repo.get_email_settings = AsyncMock(return_value=_FakeEmailSettings())
    return repo


@pytest.fixture
def email_port():
    port = AsyncMock()
    port.send = AsyncMock(return_value=_FakeSendResult())
    return port


@pytest.fixture
def executor(settings_repo, email_port):
    catalog_repo = MagicMock()
    audit_logger = MagicMock()
    ex = BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
        settings_repo=settings_repo,
    )
    ex.set_email_port(email_port)
    return ex


# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestSendEmailToolDefinition:
    def test_tool_present_with_email_send_permission(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["email:send"])
        names = {t.name for t in tools}
        assert "send_email" in names

    def test_tool_present_with_wildcard(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        names = {t.name for t in tools}
        assert "send_email" in names

    def test_tool_absent_without_permission(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["knowledge:read"])
        names = {t.name for t in tools}
        assert "send_email" not in names

    def test_tool_definition_fields(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["email:send"])
        tool = next(t for t in tools if t.name == "send_email")
        assert tool.endpoint_id == "__builtin__send_email"
        assert "to" in tool.parameters
        assert "subject" in tool.parameters
        assert "body" in tool.parameters
        assert tool.parameters["to"]["required"] is True


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestSendEmailHandler:
    @pytest.mark.asyncio
    async def test_success(self, executor, email_port):
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Q4 Report",
            "body": "Here is the Q4 report summary.",
        })
        assert result["success"] is True
        assert result["message_id"] == "msg-123"
        email_port.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_email_disabled(self, executor, settings_repo):
        settings_repo.get_email_settings.return_value = _FakeEmailSettings(enabled=False)
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_missing_to(self, executor):
        result = await executor.execute("send_email", {
            "subject": "Test",
            "body": "Hello",
        })
        assert result["success"] is False
        assert "'to'" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_subject(self, executor):
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "body": "Hello",
        })
        assert result["success"] is False
        assert "'subject'" in result["error"]

    @pytest.mark.asyncio
    async def test_missing_body(self, executor):
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
        })
        assert result["success"] is False
        assert "'body'" in result["error"]

    @pytest.mark.asyncio
    async def test_no_email_port(self, settings_repo):
        catalog_repo = MagicMock()
        audit_logger = MagicMock()
        ex = BuiltinToolExecutor(
            catalog_repo=catalog_repo,
            audit_logger=audit_logger,
            settings_repo=settings_repo,
        )
        # No email port set
        result = await ex.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert result["success"] is False
        assert "not configured" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_send_failure(self, executor, email_port):
        email_port.send.return_value = _FakeSendResult(
            success=False, error="Rate limited", provider_message_id=None,
        )
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert result["success"] is False
        assert "Rate limited" in result["error"]

    @pytest.mark.asyncio
    async def test_cc_parsed(self, executor, email_port):
        await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Hello",
            "cc": "a@example.com, b@example.com",
        })
        call_args = email_port.send.call_args[0][0]
        assert call_args.cc == ["a@example.com", "b@example.com"]

    @pytest.mark.asyncio
    async def test_default_signature_when_custom_empty(self, executor, settings_repo, email_port):
        """When signature_html is empty, falls back to build_default_signature."""
        settings_repo.get_email_settings.return_value = _FakeEmailSettings(signature_html="")
        result = await executor.execute("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "body": "Hello",
        })
        assert result["success"] is True
        # The outbound email should have HTML body with some signature
        call_args = email_port.send.call_args[0][0]
        assert "Ember" in call_args.html_body
