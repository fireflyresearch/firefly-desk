# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Slack channel adapter -- implements ChannelPort for the Slack Events API."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import datetime, timezone

import httpx

from flydesk.channels.models import AgentResponse, InboundMessage, Notification

logger = logging.getLogger(__name__)

_SLACK_API_BASE = "https://slack.com/api"


class SlackAdapter:
    """Channel adapter for Slack using the Events API and Web API.

    Implements the :class:`~flydesk.channels.port.ChannelPort` protocol so it
    can be registered with the :class:`~flydesk.channels.router.ChannelRouter`.
    """

    channel_type: str = "slack"

    def __init__(self, *, bot_token: str, signing_secret: str) -> None:
        self._bot_token = bot_token
        self._signing_secret = signing_secret
        self._client = httpx.AsyncClient(
            base_url=_SLACK_API_BASE,
            headers={"Authorization": f"Bearer {bot_token}"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # ChannelPort.receive
    # ------------------------------------------------------------------

    async def receive(self, raw_event: dict) -> InboundMessage | None:
        """Parse a Slack Events API payload into an InboundMessage.

        Returns ``None`` for events that should be silently ignored (bot
        messages, non-message event types, URL verification challenges, etc.).
        """
        event_type = raw_event.get("type")

        # Slack sends url_verification during app setup -- not a real message.
        if event_type == "url_verification":
            return None

        if event_type != "event_callback":
            return None

        inner = raw_event.get("event", {})

        # Only handle "message" events.
        if inner.get("type") != "message":
            return None

        # Ignore messages from bots to avoid echo loops.
        if inner.get("bot_id") or inner.get("subtype") == "bot_message":
            return None

        text = inner.get("text", "")
        user_id = inner.get("user", "")
        channel_id = inner.get("channel", "")
        ts = inner.get("ts", "")

        return InboundMessage(
            channel="slack",
            user_id=user_id,
            conversation_id=channel_id,
            content=text,
            metadata={"ts": ts, "team": raw_event.get("team_id", "")},
            received_at=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # ChannelPort.send
    # ------------------------------------------------------------------

    async def send(self, conversation_id: str, message: AgentResponse) -> None:
        """Post a message to a Slack channel via ``chat.postMessage``."""
        text = self._markdown_to_mrkdwn(message.content)

        resp = await self._client.post(
            "/chat.postMessage",
            json={"channel": conversation_id, "text": text},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            logger.error("Slack chat.postMessage failed: %s", data.get("error"))

    # ------------------------------------------------------------------
    # ChannelPort.send_notification
    # ------------------------------------------------------------------

    async def send_notification(
        self, user_id: str, notification: Notification
    ) -> None:
        """Send a DM notification to a Slack user.

        Opens a direct-message conversation via ``conversations.open`` and
        then posts the notification text with ``chat.postMessage``.
        """
        # Open (or retrieve) the DM channel for this user.
        open_resp = await self._client.post(
            "/conversations.open",
            json={"users": user_id},
        )
        open_resp.raise_for_status()
        dm_channel = open_resp.json()["channel"]["id"]

        text = f"*{notification.title}*\n{notification.summary}"

        msg_resp = await self._client.post(
            "/chat.postMessage",
            json={"channel": dm_channel, "text": text},
        )
        msg_resp.raise_for_status()
        data = msg_resp.json()
        if not data.get("ok"):
            logger.error("Slack DM notification failed: %s", data.get("error"))

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self, timestamp: str, body: bytes, signature: str
    ) -> bool:
        """Verify a Slack request signature using HMAC-SHA256.

        See https://api.slack.com/authentication/verifying-requests-from-slack
        """
        sig_basestring = f"v0:{timestamp}:{body.decode()}"
        expected = (
            "v0="
            + hmac.new(
                self._signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256,
            ).hexdigest()
        )
        return hmac.compare_digest(expected, signature)

    # ------------------------------------------------------------------
    # Markdown -> mrkdwn conversion
    # ------------------------------------------------------------------

    def _markdown_to_mrkdwn(self, text: str) -> str:
        """Convert standard Markdown formatting to Slack mrkdwn syntax.

        Handles:
        - ``**bold**`` -> ``*bold*``
        - ``~~strikethrough~~`` -> ``~strikethrough~``
        - ``[text](url)`` -> ``<url|text>``
        """
        # Bold: **text** -> *text*  (must be done before italic)
        text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)

        # Strikethrough: ~~text~~ -> ~text~
        text = re.sub(r"~~(.+?)~~", r"~\1~", text)

        # Links: [text](url) -> <url|text>
        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)

        return text
