# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Slack channel adapter."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_channel_type():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    assert adapter.channel_type == "slack"


@pytest.mark.asyncio
async def test_receive_parses_message_event():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")

    raw_event = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "text": "Hello bot",
            "user": "U12345",
            "channel": "C67890",
            "ts": "1234567890.123456",
        },
    }
    message = await adapter.receive(raw_event)
    assert message is not None
    assert message.content == "Hello bot"
    assert message.user_id == "U12345"
    assert message.channel == "slack"
    assert message.conversation_id == "C67890"
    assert message.metadata["ts"] == "1234567890.123456"


@pytest.mark.asyncio
async def test_receive_ignores_bot_messages():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")

    raw_event = {
        "type": "event_callback",
        "event": {
            "type": "message",
            "text": "Bot reply",
            "bot_id": "B12345",
            "channel": "C67890",
        },
    }
    message = await adapter.receive(raw_event)
    assert message is None


@pytest.mark.asyncio
async def test_receive_ignores_non_message():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")

    raw_event = {"type": "url_verification", "challenge": "abc123"}
    message = await adapter.receive(raw_event)
    assert message is None


def test_markdown_to_mrkdwn_bold():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    result = adapter._markdown_to_mrkdwn("**bold text**")
    assert "*bold text*" in result


def test_markdown_to_mrkdwn_links():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    result = adapter._markdown_to_mrkdwn("[Click here](https://example.com)")
    assert "<https://example.com|Click here>" in result


def test_markdown_to_mrkdwn_strikethrough():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    result = adapter._markdown_to_mrkdwn("~~deleted~~")
    assert "~deleted~" in result


def test_verify_signature_valid():
    import hashlib
    import hmac
    import time

    from flydesk.channels.slack import SlackAdapter

    signing_secret = "my_secret"
    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret=signing_secret)

    timestamp = str(int(time.time()))
    body = b'{"type":"event_callback"}'
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    expected_sig = (
        "v0="
        + hmac.new(
            signing_secret.encode(), sig_basestring.encode(), hashlib.sha256
        ).hexdigest()
    )

    assert adapter.verify_signature(timestamp, body, expected_sig) is True


def test_verify_signature_invalid():
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    assert adapter.verify_signature("123456", b"body", "v0=invalid") is False


@pytest.mark.asyncio
async def test_send_posts_message():
    from flydesk.channels.models import AgentResponse
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    response = AgentResponse(content="Hello from bot!")

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_resp.raise_for_status = MagicMock()

    with patch.object(adapter._client, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        await adapter.send("C67890", response)
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["channel"] == "C67890"
        assert "Hello from bot!" in call_kwargs[1]["json"]["text"]


@pytest.mark.asyncio
async def test_send_notification_opens_dm():
    from flydesk.channels.models import Notification
    from flydesk.channels.slack import SlackAdapter

    adapter = SlackAdapter(bot_token="xoxb-test", signing_secret="secret")
    notification = Notification(title="Alert", summary="Something happened")

    open_resp = MagicMock()
    open_resp.status_code = 200
    open_resp.json.return_value = {"ok": True, "channel": {"id": "D99999"}}
    open_resp.raise_for_status = MagicMock()

    msg_resp = MagicMock()
    msg_resp.status_code = 200
    msg_resp.json.return_value = {"ok": True}
    msg_resp.raise_for_status = MagicMock()

    with patch.object(
        adapter._client, "post", new_callable=AsyncMock
    ) as mock_post:
        mock_post.side_effect = [open_resp, msg_resp]
        await adapter.send_notification("U12345", notification)
        assert mock_post.call_count == 2
