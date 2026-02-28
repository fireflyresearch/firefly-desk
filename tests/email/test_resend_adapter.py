# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ResendEmailAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.email.adapters.resend_adapter import ResendEmailAdapter
from flydesk.email.models import OutboundEmail, InboundEmail


class TestResendEmailAdapter:
    def test_instantiation(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        assert adapter._api_key == "re_test_123"

    async def test_parse_inbound_email(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        payload = {
            "from": "user@example.com",
            "to": ["ember@flydesk.ai"],
            "cc": [],
            "subject": "Hello Ember",
            "text": "Can you help me?",
            "html": "<p>Can you help me?</p>",
            "message_id": "<abc123@mail.example.com>",
            "in_reply_to": None,
            "references": [],
            "attachments": [],
        }
        result = await adapter.parse_inbound(payload)
        assert isinstance(result, InboundEmail)
        assert result.from_address == "user@example.com"
        assert result.subject == "Hello Ember"
        assert result.text_body == "Can you help me?"
        assert result.message_id == "<abc123@mail.example.com>"

    async def test_parse_inbound_email_with_display_name(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        payload = {
            "from": '"Jane Doe" <jane@example.com>',
            "to": ["ember@flydesk.ai"],
            "cc": ["boss@example.com"],
            "subject": "Question",
            "text": "Hi there",
            "html": None,
            "message_id": "<def456@mail.example.com>",
            "in_reply_to": "<abc123@mail.example.com>",
            "references": ["<abc123@mail.example.com>"],
            "attachments": [],
        }
        result = await adapter.parse_inbound(payload)
        assert result.from_address == "jane@example.com"
        assert result.from_name == "Jane Doe"
        assert result.cc == ["boss@example.com"]
        assert result.in_reply_to == "<abc123@mail.example.com>"
        assert result.references == ["<abc123@mail.example.com>"]

    async def test_parse_inbound_email_with_attachments(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        payload = {
            "from": "user@example.com",
            "to": ["ember@flydesk.ai"],
            "cc": [],
            "subject": "With attachment",
            "text": "See attached",
            "html": None,
            "message_id": "<att789@mail.example.com>",
            "in_reply_to": None,
            "references": [],
            "attachments": [
                {
                    "filename": "report.pdf",
                    "content_type": "application/pdf",
                    "size": 12345,
                    "url": "https://attachments.resend.com/report.pdf",
                }
            ],
        }
        result = await adapter.parse_inbound(payload)
        assert len(result.attachments) == 1
        assert result.attachments[0].filename == "report.pdf"
        assert result.attachments[0].content_type == "application/pdf"
        assert result.attachments[0].size == 12345
        assert result.attachments[0].url == "https://attachments.resend.com/report.pdf"

    async def test_send_success(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Re: Hello",
            html_body="<p>Hi there!</p>",
            text_body="Hi there!",
        )

        mock_resend = MagicMock()
        mock_resend.api_key = None
        mock_resend.Emails.send.return_value = {"id": "msg_abc123"}

        with patch.dict("sys.modules", {"resend": mock_resend}):
            result = await adapter.send(email)

        assert result.success is True
        assert result.provider_message_id == "msg_abc123"

    async def test_send_with_headers(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Re: Thread",
            html_body="<p>Reply</p>",
            in_reply_to="<orig@mail.example.com>",
            references=["<orig@mail.example.com>"],
            headers={"X-Custom": "value"},
        )

        mock_resend = MagicMock()
        mock_resend.api_key = None
        mock_resend.Emails.send.return_value = {"id": "msg_def456"}

        with patch.dict("sys.modules", {"resend": mock_resend}):
            result = await adapter.send(email)

        assert result.success is True
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["headers"]["In-Reply-To"] == "<orig@mail.example.com>"
        assert call_args["headers"]["References"] == "<orig@mail.example.com>"
        assert call_args["headers"]["X-Custom"] == "value"

    async def test_send_failure(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Test",
            html_body="<p>Test</p>",
        )

        mock_resend = MagicMock()
        mock_resend.api_key = None
        mock_resend.Emails.send.side_effect = Exception("API rate limit exceeded")

        with patch.dict("sys.modules", {"resend": mock_resend}):
            result = await adapter.send(email)

        assert result.success is False
        assert "API rate limit exceeded" in result.error

    async def test_verify_webhook_signature_valid(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        headers = {
            "svix-id": "msg_abc123",
            "svix-timestamp": "1234567890",
            "svix-signature": "v1,K5oZfzN95Z3P7+KBb0PNuG2tMgHBzFMgJedoLlSaKnQ=",
        }
        result = await adapter.verify_webhook_signature(headers, b'{"test": true}')
        assert result is True

    async def test_verify_webhook_signature_missing_headers(self):
        adapter = ResendEmailAdapter(api_key="re_test_123")
        headers = {"svix-id": "msg_abc123"}
        result = await adapter.verify_webhook_signature(headers, b'{"test": true}')
        assert result is False

    def test_satisfies_email_port_protocol(self):
        from flydesk.email.port import EmailPort

        adapter = ResendEmailAdapter(api_key="re_test_123")
        assert isinstance(adapter, EmailPort)
