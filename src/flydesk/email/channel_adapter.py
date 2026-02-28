# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Email channel adapter -- bridges EmailPort and ChannelPort."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from flydesk.channels.models import Attachment, InboundMessage
from flydesk.email.models import OutboundEmail

if TYPE_CHECKING:
    from flydesk.channels.models import AgentResponse, Notification
    from flydesk.email.identity import EmailIdentityResolver
    from flydesk.email.port import EmailPort
    from flydesk.email.threading import EmailThreadTracker
    from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

_RE_PREFIX = re.compile(r"^re:\s", re.IGNORECASE)


class EmailChannelAdapter:
    """Adapts the email transport to the unified :class:`ChannelPort` protocol.

    ``receive()`` converts provider webhook payloads into normalised
    :class:`InboundMessage` objects.  ``send()`` formats agent responses
    as HTML emails and delivers them via the configured :class:`EmailPort`.

    Note: ``receive()`` returns ``InboundMessage | None`` -- ``None`` is
    returned when the sender cannot be resolved to a known user.
    """

    channel_type: str = "email"

    def __init__(
        self,
        *,
        email_port: EmailPort,
        identity_resolver: EmailIdentityResolver,
        thread_tracker: EmailThreadTracker,
        settings_repo: SettingsRepository,
    ) -> None:
        self._email_port = email_port
        self._identity_resolver = identity_resolver
        self._thread_tracker = thread_tracker
        self._settings_repo = settings_repo

        # Maps conversation_id -> reply metadata (populated by receive(),
        # consumed by send()).
        self._pending_replies: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # ChannelPort.receive
    # ------------------------------------------------------------------

    async def receive(self, raw_event: dict) -> InboundMessage | None:
        """Parse a raw inbound webhook event into an :class:`InboundMessage`.

        Returns ``None`` if the sender's email address cannot be resolved
        to a known user (the caller should handle this gracefully).
        """
        payload = raw_event.get("payload", raw_event)
        inbound = await self._email_port.parse_inbound(payload)

        # Resolve the sender to a user account.
        identity = await self._identity_resolver.resolve(inbound.from_address)
        if identity is None:
            logger.warning(
                "Ignoring inbound email from unknown sender: %s",
                inbound.from_address,
            )
            return None

        # Resolve email thread -> conversation.
        conversation_id, _is_new = await self._thread_tracker.resolve_conversation(
            message_id=inbound.message_id,
            in_reply_to=inbound.in_reply_to,
            references=inbound.references,
            subject=inbound.subject,
            participants=[{"email": inbound.from_address, "name": inbound.from_name}],
        )

        # Build reply subject (add "Re: " if not already present).
        reply_subject = inbound.subject
        if not _RE_PREFIX.match(reply_subject):
            reply_subject = f"Re: {reply_subject}"

        # Build references chain for the reply.
        reply_references = list(inbound.references)
        if inbound.message_id and inbound.message_id not in reply_references:
            reply_references.append(inbound.message_id)

        # Store reply metadata for the subsequent send().
        self._pending_replies[conversation_id] = {
            "to": [inbound.from_address],
            "cc": list(inbound.cc),
            "subject": reply_subject,
            "in_reply_to": inbound.message_id,
            "references": reply_references,
        }

        # Convert email attachments to channel attachments.
        attachments = [
            Attachment(
                filename=att.filename,
                content_type=att.content_type,
                size=att.size,
                data=att.content,
                url=att.url,
            )
            for att in inbound.attachments
        ]

        return InboundMessage(
            channel="email",
            user_id=identity.user_id,
            conversation_id=conversation_id,
            content=inbound.text_body,
            attachments=attachments,
            metadata={
                "subject": inbound.subject,
                "cc": list(inbound.cc),
                "from_name": inbound.from_name,
                "message_id": inbound.message_id,
            },
            reply_to_message_id=inbound.in_reply_to,
            received_at=inbound.received_at,
        )

    # ------------------------------------------------------------------
    # ChannelPort.send
    # ------------------------------------------------------------------

    async def send(self, conversation_id: str, message: AgentResponse) -> None:
        """Format an agent response as an HTML email and send it.

        Raises :class:`KeyError` if no reply metadata has been stored for
        the given *conversation_id* (i.e. ``receive()`` was never called
        for this conversation).
        """
        reply_meta = self._pending_replies[conversation_id]
        settings = await self._settings_repo.get_email_settings()

        # Simple HTML wrapping (Task 2 replaces this with full markdown->HTML).
        html_body = f"<p>{message.content}</p>"

        # Append signature if configured.
        if settings.include_sign_off and settings.signature_html:
            html_body = f"{html_body}\n{settings.signature_html}"

        email = OutboundEmail(
            from_address=settings.from_address,
            from_name=settings.from_display_name,
            to=reply_meta["to"],
            cc=reply_meta.get("cc", []),
            subject=reply_meta["subject"],
            html_body=html_body,
            text_body=message.content,
            in_reply_to=reply_meta.get("in_reply_to"),
            references=reply_meta.get("references", []),
        )

        result = await self._email_port.send(email)

        if result.success and result.provider_message_id:
            await self._thread_tracker.record_outbound(
                conversation_id, result.provider_message_id
            )
        elif not result.success:
            logger.error(
                "Failed to send email for conversation %s: %s",
                conversation_id,
                result.error,
            )

    # ------------------------------------------------------------------
    # ChannelPort.send_notification
    # ------------------------------------------------------------------

    async def send_notification(
        self, user_id: str, notification: Notification
    ) -> None:
        """Build and send a simple notification email to the given user."""
        settings = await self._settings_repo.get_email_settings()

        # Resolve user_id -> email address.
        identity = await self._identity_resolver.resolve_by_user_id(user_id)
        if identity is None:
            logger.warning(
                "Cannot send notification: unable to resolve user_id %s", user_id
            )
            return

        html_body = f"<p>{notification.summary}</p>"
        if settings.include_sign_off and settings.signature_html:
            html_body = f"{html_body}\n{settings.signature_html}"

        email = OutboundEmail(
            from_address=settings.from_address,
            from_name=settings.from_display_name,
            to=[identity.email],
            subject=notification.title,
            html_body=html_body,
            text_body=notification.summary,
        )

        result = await self._email_port.send(email)
        if not result.success:
            logger.error(
                "Failed to send notification email to %s: %s",
                identity.email,
                result.error,
            )
