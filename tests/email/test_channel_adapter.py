# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for EmailChannelAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.channels.models import AgentResponse, InboundMessage, Notification
from flydesk.email.channel_adapter import EmailChannelAdapter


class TestReceive:
    async def test_converts_inbound_email_to_message(self):
        """EmailChannelAdapter.receive() parses raw webhook into InboundMessage."""
        email_port = AsyncMock()
        email_port.parse_inbound.return_value = MagicMock(
            from_address="user@example.com",
            from_name="Alice",
            to=["ember@flydesk.ai"],
            cc=["bob@example.com"],
            subject="Help with invoice",
            text_body="Please process invoice #42",
            html_body=None,
            message_id="<msg-1@example.com>",
            in_reply_to=None,
            references=[],
            attachments=[],
            received_at=None,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve.return_value = MagicMock(
            user_id="user-1", email="user@example.com", display_name="Alice"
        )
        thread_tracker = AsyncMock()
        thread_tracker.resolve_conversation.return_value = ("conv-1", True)

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=thread_tracker,
            settings_repo=AsyncMock(),
        )

        msg = await adapter.receive({"provider": "resend", "payload": {}})

        assert isinstance(msg, InboundMessage)
        assert msg.channel == "email"
        assert msg.user_id == "user-1"
        assert msg.conversation_id == "conv-1"
        assert msg.content == "Please process invoice #42"
        assert msg.metadata["subject"] == "Help with invoice"
        assert msg.metadata["cc"] == ["bob@example.com"]
        assert msg.metadata["from_name"] == "Alice"

    async def test_stores_reply_metadata_for_later_send(self):
        """receive() stores reply metadata so send() knows where to reply."""
        email_port = AsyncMock()
        email_port.parse_inbound.return_value = MagicMock(
            from_address="user@example.com",
            from_name="Alice",
            to=["ember@flydesk.ai"],
            cc=["bob@example.com"],
            subject="Help with invoice",
            text_body="body",
            html_body=None,
            message_id="<msg-1@example.com>",
            in_reply_to="<prev@example.com>",
            references=["<prev@example.com>"],
            attachments=[],
            received_at=None,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve.return_value = MagicMock(
            user_id="user-1", email="user@example.com", display_name="Alice"
        )
        thread_tracker = AsyncMock()
        thread_tracker.resolve_conversation.return_value = ("conv-1", False)

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=thread_tracker,
            settings_repo=AsyncMock(),
        )

        await adapter.receive({"provider": "resend", "payload": {}})

        assert "conv-1" in adapter._pending_replies
        reply_meta = adapter._pending_replies["conv-1"]
        assert reply_meta["to"] == ["user@example.com"]
        assert reply_meta["cc"] == ["bob@example.com"]
        assert reply_meta["subject"] == "Re: Help with invoice"
        assert reply_meta["in_reply_to"] == "<msg-1@example.com>"
        assert "<msg-1@example.com>" in reply_meta["references"]

    async def test_returns_none_for_unknown_sender(self):
        """receive() returns None when identity cannot be resolved."""
        email_port = AsyncMock()
        email_port.parse_inbound.return_value = MagicMock(
            from_address="stranger@example.com",
            from_name="Unknown",
            to=["ember@flydesk.ai"],
            cc=[],
            subject="Hello",
            text_body="Who am I?",
            html_body=None,
            message_id="<msg-2@example.com>",
            in_reply_to=None,
            references=[],
            attachments=[],
            received_at=None,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve.return_value = None

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=AsyncMock(),
            settings_repo=AsyncMock(),
        )

        result = await adapter.receive({"provider": "resend", "payload": {}})
        assert result is None

    async def test_subject_not_double_prefixed_with_re(self):
        """If subject already starts with Re: don't add another."""
        email_port = AsyncMock()
        email_port.parse_inbound.return_value = MagicMock(
            from_address="user@example.com",
            from_name="Alice",
            to=["ember@flydesk.ai"],
            cc=[],
            subject="Re: Original topic",
            text_body="reply",
            html_body=None,
            message_id="<msg-3@example.com>",
            in_reply_to=None,
            references=[],
            attachments=[],
            received_at=None,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve.return_value = MagicMock(
            user_id="user-1", email="user@example.com", display_name="Alice"
        )
        thread_tracker = AsyncMock()
        thread_tracker.resolve_conversation.return_value = ("conv-2", False)

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=thread_tracker,
            settings_repo=AsyncMock(),
        )

        await adapter.receive({"provider": "resend", "payload": {}})

        reply_meta = adapter._pending_replies["conv-2"]
        assert reply_meta["subject"] == "Re: Original topic"


class TestSend:
    async def test_formats_html_and_sends_email(self):
        """send() formats agent response as HTML email and calls email_port.send()."""
        email_port = AsyncMock()
        email_port.send.return_value = MagicMock(
            success=True, provider_message_id="msg-123"
        )
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            enabled=True,
            cc_mode="respond_all",
            from_address="ember@flydesk.ai",
            from_display_name="Ember",
            signature_html="<p>-- Ember</p>",
            include_sign_off=True,
        )

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=AsyncMock(),
            thread_tracker=AsyncMock(),
            settings_repo=settings_repo,
        )
        adapter._pending_replies = {
            "conv-1": {
                "to": ["user@example.com"],
                "cc": ["bob@example.com"],
                "subject": "Re: Help with invoice",
                "in_reply_to": "<msg-1@example.com>",
                "references": ["<msg-1@example.com>"],
            }
        }

        response = AgentResponse(content="Invoice #42 has been processed.")
        await adapter.send("conv-1", response)

        email_port.send.assert_called_once()
        sent = email_port.send.call_args[0][0]
        assert "Invoice #42" in sent.html_body
        assert sent.to == ["user@example.com"]
        assert sent.cc == ["bob@example.com"]
        assert sent.subject == "Re: Help with invoice"
        assert sent.in_reply_to == "<msg-1@example.com>"
        assert sent.from_address == "ember@flydesk.ai"
        assert sent.from_name == "Ember"

    async def test_send_appends_signature(self):
        """send() appends the configured HTML signature to the email body."""
        email_port = AsyncMock()
        email_port.send.return_value = MagicMock(
            success=True, provider_message_id="msg-456"
        )
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            enabled=True,
            cc_mode="respond_all",
            from_address="ember@flydesk.ai",
            from_display_name="Ember",
            signature_html="<p>-- Ember, your assistant</p>",
            include_sign_off=True,
        )

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=AsyncMock(),
            thread_tracker=AsyncMock(),
            settings_repo=settings_repo,
        )
        adapter._pending_replies = {
            "conv-1": {
                "to": ["user@example.com"],
                "cc": [],
                "subject": "Re: Test",
                "in_reply_to": "<msg@example.com>",
                "references": ["<msg@example.com>"],
            }
        }

        await adapter.send("conv-1", AgentResponse(content="Done."))

        sent = email_port.send.call_args[0][0]
        assert "-- Ember, your assistant" in sent.html_body

    async def test_send_without_reply_metadata_raises(self):
        """send() raises KeyError when no reply metadata exists for the conversation."""
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            enabled=True,
            cc_mode="respond_all",
        )

        adapter = EmailChannelAdapter(
            email_port=AsyncMock(),
            identity_resolver=AsyncMock(),
            thread_tracker=AsyncMock(),
            settings_repo=settings_repo,
        )

        with pytest.raises(KeyError):
            await adapter.send("unknown-conv", AgentResponse(content="Hi"))

    async def test_send_records_outbound_message_id(self):
        """send() records the provider message ID in the thread tracker."""
        email_port = AsyncMock()
        email_port.send.return_value = MagicMock(
            success=True, provider_message_id="<outbound-123@provider>"
        )
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            enabled=True,
            cc_mode="respond_all",
            from_address="ember@flydesk.ai",
            from_display_name="Ember",
            signature_html="",
            include_sign_off=False,
        )
        thread_tracker = AsyncMock()

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=AsyncMock(),
            thread_tracker=thread_tracker,
            settings_repo=settings_repo,
        )
        adapter._pending_replies = {
            "conv-1": {
                "to": ["user@example.com"],
                "cc": [],
                "subject": "Re: Test",
                "in_reply_to": "<msg@example.com>",
                "references": ["<msg@example.com>"],
            }
        }

        await adapter.send("conv-1", AgentResponse(content="Done."))

        thread_tracker.record_outbound.assert_called_once_with(
            "conv-1", "<outbound-123@provider>"
        )


class TestSendNotification:
    async def test_sends_notification_email(self):
        """send_notification() builds and sends a notification email."""
        email_port = AsyncMock()
        email_port.send.return_value = MagicMock(success=True, provider_message_id="n-1")
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            from_address="ember@flydesk.ai",
            from_display_name="Ember",
            signature_html="",
            include_sign_off=False,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve_by_user_id = AsyncMock(
            return_value=MagicMock(email="user@example.com", display_name="Alice")
        )

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=AsyncMock(),
            settings_repo=settings_repo,
        )

        notification = Notification(
            title="Workflow completed",
            summary="Your export is ready to download.",
        )
        await adapter.send_notification("user-1", notification)

        email_port.send.assert_called_once()
        sent = email_port.send.call_args[0][0]
        assert sent.to == ["user@example.com"]
        assert sent.subject == "Workflow completed"
        assert "export is ready" in sent.html_body


    async def test_send_notification_unresolvable_user_does_not_send(self):
        """send_notification() gracefully no-ops when user_id cannot be resolved."""
        email_port = AsyncMock()
        settings_repo = AsyncMock()
        settings_repo.get_email_settings.return_value = MagicMock(
            from_address="ember@flydesk.ai",
            from_display_name="Ember",
            signature_html="",
            include_sign_off=False,
        )
        identity_resolver = AsyncMock()
        identity_resolver.resolve_by_user_id = AsyncMock(return_value=None)

        adapter = EmailChannelAdapter(
            email_port=email_port,
            identity_resolver=identity_resolver,
            thread_tracker=AsyncMock(),
            settings_repo=settings_repo,
        )

        notification = Notification(
            title="Test",
            summary="This should not be sent.",
        )
        # Should not raise
        await adapter.send_notification("nonexistent-user", notification)

        # Should not have attempted to send an email
        email_port.send.assert_not_called()


class TestChannelType:
    def test_channel_type_is_email(self):
        """Adapter has channel_type = 'email'."""
        adapter = EmailChannelAdapter(
            email_port=AsyncMock(),
            identity_resolver=AsyncMock(),
            thread_tracker=AsyncMock(),
            settings_repo=AsyncMock(),
        )
        assert adapter.channel_type == "email"
