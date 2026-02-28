# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SendGridEmailAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.email.adapters.sendgrid_adapter import SendGridEmailAdapter
from flydesk.email.models import InboundEmail, OutboundEmail


class TestSendGridEmailAdapter:
    def test_instantiation_default_api_base(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        assert adapter._api_key == "SG.test_key"
        assert adapter._api_base == "https://api.sendgrid.com"

    def test_instantiation_custom_api_base(self):
        adapter = SendGridEmailAdapter(
            api_key="SG.test_key",
            api_base="https://sendgrid.proxy.internal/",
        )
        assert adapter._api_base == "https://sendgrid.proxy.internal"

    def test_api_base_trailing_slash_stripped(self):
        adapter = SendGridEmailAdapter(
            api_key="SG.test_key",
            api_base="https://api.sendgrid.com/",
        )
        assert adapter._api_base == "https://api.sendgrid.com"

    @pytest.mark.asyncio
    async def test_send_success(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Re: Hello",
            html_body="<p>Hi there!</p>",
            text_body="Hi there!",
        )

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {"X-Message-Id": "sg_msg_abc123"}
        mock_response.raise_for_status.return_value = None

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            result = await adapter.send(email)

        assert result.success is True
        assert result.provider_message_id == "sg_msg_abc123"

    @pytest.mark.asyncio
    async def test_send_with_headers(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
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

        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.headers = {}
        mock_response.raise_for_status.return_value = None

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(return_value=mock_response)
            result = await adapter.send(email)

        assert result.success is True
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs["json"] if "json" in call_kwargs.kwargs else call_kwargs[1]["json"]
        assert payload["headers"]["In-Reply-To"] == "<orig@mail.example.com>"
        assert payload["headers"]["References"] == "<orig@mail.example.com>"
        assert payload["headers"]["X-Custom"] == "value"

    @pytest.mark.asyncio
    async def test_send_failure(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Test",
            html_body="<p>Test</p>",
        )

        with patch.object(adapter, "_client") as mock_client:
            mock_client.post = AsyncMock(side_effect=Exception("API rate limit exceeded"))
            result = await adapter.send(email)

        assert result.success is False
        assert "API rate limit exceeded" in result.error

    @pytest.mark.asyncio
    async def test_validate_success(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"scopes": ["mail.send"]}
        mock_response.raise_for_status.return_value = None

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(return_value=mock_response)
            result = await adapter.validate()

        assert result.success is True
        assert result.metadata == {"scopes": ["mail.send"]}

    @pytest.mark.asyncio
    async def test_validate_failure(self):
        adapter = SendGridEmailAdapter(api_key="SG.bad_key")

        with patch.object(adapter, "_client") as mock_client:
            mock_client.get = AsyncMock(side_effect=Exception("401 Unauthorized"))
            result = await adapter.validate()

        assert result.success is False
        assert result.error == "Invalid API key"

    @pytest.mark.asyncio
    async def test_parse_inbound_email(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        payload = {
            "from": "user@example.com",
            "to": "ember@flydesk.ai",
            "cc": "",
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

    @pytest.mark.asyncio
    async def test_parse_inbound_with_display_name(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        payload = {
            "from": '"Jane Doe" <jane@example.com>',
            "to": "ember@flydesk.ai",
            "cc": "boss@example.com",
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
        assert "boss@example.com" in result.cc

    @pytest.mark.asyncio
    async def test_verify_webhook_signature(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        result = await adapter.verify_webhook_signature({}, b'{"test": true}')
        assert result is True

    @pytest.mark.asyncio
    async def test_aclose(self):
        adapter = SendGridEmailAdapter(api_key="SG.test_key")
        with patch.object(adapter, "_client") as mock_client:
            mock_client.aclose = AsyncMock()
            await adapter.aclose()
            mock_client.aclose.assert_called_once()
