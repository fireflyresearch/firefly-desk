# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SESEmailAdapter."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Build a mock boto3 module so SESEmailAdapter can import it without
# the real package being installed.
_mock_boto3_module = types.ModuleType("boto3")


def _fake_client(service: str, **kwargs):
    mock_client = MagicMock()
    mock_client.send_email.return_value = {"MessageId": "ses-mock-id-456"}
    return mock_client


_mock_boto3_module.client = _fake_client  # type: ignore[attr-defined]
sys.modules.setdefault("boto3", _mock_boto3_module)

from flydesk.email.adapters.ses_adapter import SESEmailAdapter
from flydesk.email.models import InboundEmail, OutboundEmail, SendResult


class TestSESEmailAdapter:
    """Tests for the AWS SES email adapter."""

    def test_instantiation(self):
        adapter = SESEmailAdapter(region="us-east-1")
        assert adapter._region == "us-east-1"

    def test_instantiation_with_credentials(self):
        adapter = SESEmailAdapter(
            region="eu-west-1",
            access_key_id="AKIA_TEST",
            secret_access_key="secret_test",
        )
        assert adapter._region == "eu-west-1"
        assert adapter._access_key_id == "AKIA_TEST"
        assert adapter._secret_access_key == "secret_test"

    def test_instantiation_defaults(self):
        adapter = SESEmailAdapter()
        assert adapter._region == "us-east-1"
        assert adapter._access_key_id is None
        assert adapter._secret_access_key is None

    async def test_send_success(self):
        adapter = SESEmailAdapter(region="us-east-1")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Test email",
            html_body="<p>Hello</p>",
            text_body="Hello",
        )
        with patch.object(adapter, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {"MessageId": "ses-id-789"}
            mock_get.return_value = mock_client

            result = await adapter.send(email)

        assert isinstance(result, SendResult)
        assert result.success is True
        assert result.provider_message_id == "ses-id-789"

    async def test_send_with_cc_bcc(self):
        adapter = SESEmailAdapter(region="us-east-1")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Test CC/BCC",
            html_body="<p>Hello</p>",
            cc=["cc@example.com"],
            bcc=["bcc@example.com"],
        )
        with patch.object(adapter, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {"MessageId": "ses-cc-id"}
            mock_get.return_value = mock_client

            result = await adapter.send(email)

        assert result.success is True
        call_kwargs = mock_client.send_email.call_args
        destination = call_kwargs[1]["Destination"] if call_kwargs[1] else call_kwargs.kwargs["Destination"]
        assert destination["CcAddresses"] == ["cc@example.com"]
        assert destination["BccAddresses"] == ["bcc@example.com"]

    async def test_send_failure(self):
        adapter = SESEmailAdapter(region="us-east-1")
        email = OutboundEmail(
            from_address="ember@flydesk.ai",
            from_name="Ember",
            to=["user@example.com"],
            subject="Will fail",
            html_body="<p>Fail</p>",
        )
        with patch.object(adapter, "_get_client") as mock_get:
            mock_client = MagicMock()
            mock_client.send_email.side_effect = Exception("SES rate limit exceeded")
            mock_get.return_value = mock_client

            result = await adapter.send(email)

        assert result.success is False
        assert "SES rate limit exceeded" in result.error

    async def test_parse_inbound_ses_notification(self):
        adapter = SESEmailAdapter(region="us-east-1")
        # SES inbound comes via SNS notification
        payload = {
            "notificationType": "Received",
            "mail": {
                "source": "user@example.com",
                "destination": ["ember@flydesk.ai"],
                "commonHeaders": {
                    "from": ["user@example.com"],
                    "to": ["ember@flydesk.ai"],
                    "cc": [],
                    "subject": "Hello Ember",
                    "messageId": "<ses-msg-123@mail.example.com>",
                },
            },
            "content": "From: user@example.com\nTo: ember@flydesk.ai\nSubject: Hello Ember\n\nCan you help?",
        }
        result = await adapter.parse_inbound(payload)
        assert isinstance(result, InboundEmail)
        assert result.from_address == "user@example.com"
        assert result.subject == "Hello Ember"
        assert result.to == ["ember@flydesk.ai"]
        assert result.cc == []
        assert result.message_id == "<ses-msg-123@mail.example.com>"
        assert "Can you help?" in result.text_body

    async def test_parse_inbound_fallback_to_source(self):
        """When commonHeaders.from is missing, fall back to mail.source."""
        adapter = SESEmailAdapter(region="us-east-1")
        payload = {
            "mail": {
                "source": "fallback@example.com",
                "destination": ["ember@flydesk.ai"],
                "commonHeaders": {
                    "to": ["ember@flydesk.ai"],
                    "subject": "Fallback test",
                },
            },
            "content": "Body text here",
        }
        result = await adapter.parse_inbound(payload)
        assert result.from_address == "fallback@example.com"
        assert result.subject == "Fallback test"

    async def test_parse_inbound_minimal_payload(self):
        """Handle minimal payload with missing fields gracefully."""
        adapter = SESEmailAdapter(region="us-east-1")
        payload = {"mail": {}, "content": ""}
        result = await adapter.parse_inbound(payload)
        assert isinstance(result, InboundEmail)
        assert result.from_address == ""
        assert result.subject == ""

    async def test_verify_webhook_signature(self):
        adapter = SESEmailAdapter(region="us-east-1")
        result = await adapter.verify_webhook_signature({}, b"body")
        # Simplified implementation always returns True
        assert result is True

    def test_get_client_with_credentials(self):
        adapter = SESEmailAdapter(
            region="us-west-2",
            access_key_id="AKIA_KEY",
            secret_access_key="SECRET",
        )
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            adapter._get_client()
            mock_boto3.client.assert_called_once_with(
                "ses",
                region_name="us-west-2",
                aws_access_key_id="AKIA_KEY",
                aws_secret_access_key="SECRET",
            )

    def test_get_client_without_credentials(self):
        adapter = SESEmailAdapter(region="us-east-1")
        mock_boto3 = MagicMock()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            adapter._get_client()
            mock_boto3.client.assert_called_once_with(
                "ses",
                region_name="us-east-1",
            )
