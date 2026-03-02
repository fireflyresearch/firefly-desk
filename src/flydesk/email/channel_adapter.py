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
import uuid
from typing import TYPE_CHECKING

from flydesk.channels.models import Attachment, InboundMessage
from flydesk.email.models import EmailAttachment, OutboundEmail
from flydesk.files.models import FileUpload

if TYPE_CHECKING:
    from flydesk.callbacks.dispatcher import CallbackDispatcher
    from flydesk.channels.models import AgentResponse, Notification
    from flydesk.conversation.repository import ConversationRepository
    from flydesk.email.identity import EmailIdentityResolver
    from flydesk.email.port import EmailPort
    from flydesk.email.threading import EmailThreadTracker
    from flydesk.files.extractor import ContentExtractor
    from flydesk.files.repository import FileUploadRepository
    from flydesk.files.storage import FileStorageProvider
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
        file_repo: FileUploadRepository | None = None,
        file_storage: FileStorageProvider | None = None,
        content_extractor: ContentExtractor | None = None,
        conversation_repo: ConversationRepository | None = None,
        callback_dispatcher: CallbackDispatcher | None = None,
    ) -> None:
        self._email_port = email_port
        self._identity_resolver = identity_resolver
        self._thread_tracker = thread_tracker
        self._settings_repo = settings_repo
        self._file_repo = file_repo
        self._file_storage = file_storage
        self._content_extractor = content_extractor
        self._conversation_repo = conversation_repo
        self._callback_dispatcher = callback_dispatcher

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

        # If the provider's webhook didn't include the body, fetch it.
        _meta = getattr(inbound, "metadata", None) or {}
        if not inbound.text_body and _meta.get("needs_content_fetch"):
            email_id = _meta.get("email_id")
            if email_id:
                logger.info("Fetching email content for %s", email_id)
                inbound = await self._email_port.fetch_inbound_content(email_id)

        # Resolve the sender to a user account.
        identity = await self._identity_resolver.resolve(inbound.from_address)
        if identity is None:
            # Check dev authorized emails whitelist before rejecting.
            import hashlib

            from flydesk.email.identity import ResolvedIdentity

            settings = await self._settings_repo.get_email_settings()
            if inbound.from_address.lower() in {e.lower() for e in settings.dev_authorized_emails}:
                email_hash = hashlib.sha256(
                    inbound.from_address.encode()
                ).hexdigest()[:12]
                identity = ResolvedIdentity(
                    user_id=f"dev-{email_hash}",
                    email=inbound.from_address,
                    display_name=inbound.from_name or inbound.from_address,
                )
                logger.warning(
                    "Dev override: accepting inbound email from whitelisted address %s (user_id=%s)",
                    inbound.from_address,
                    identity.user_id,
                )
            else:
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
        reply_context = {
            "to": [inbound.from_address],
            "cc": list(inbound.cc),
            "subject": reply_subject,
            "in_reply_to": inbound.message_id,
            "references": reply_references,
        }
        if self._conversation_repo is not None:
            await self._conversation_repo.update_conversation_metadata(
                conversation_id, {"email_reply_context": reply_context}
            )
        else:
            self._pending_replies[conversation_id] = reply_context

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

        # Process attachments into FileUpload records when dependencies
        # are available.
        metadata: dict = {
            "subject": inbound.subject,
            "cc": list(inbound.cc),
            "from_name": inbound.from_name,
            "message_id": inbound.message_id,
        }

        if inbound.attachments and self._file_repo and self._file_storage:
            file_ids = await self._process_attachments(
                attachments=inbound.attachments,
                user_id=identity.user_id,
                conversation_id=conversation_id,
            )
            if file_ids:
                metadata["file_ids"] = file_ids

        return InboundMessage(
            channel="email",
            user_id=identity.user_id,
            conversation_id=conversation_id,
            content=inbound.text_body,
            attachments=attachments,
            metadata=metadata,
            reply_to_message_id=inbound.in_reply_to,
            received_at=inbound.received_at,
        )

    # ------------------------------------------------------------------
    # Attachment processing
    # ------------------------------------------------------------------

    async def _process_attachments(
        self,
        *,
        attachments: list[EmailAttachment],
        user_id: str,
        conversation_id: str | None,
    ) -> list[str]:
        """Store email attachments as :class:`FileUpload` records.

        For each attachment with inline content:
        1. Store bytes via :attr:`_file_storage`.
        2. Extract text for non-image types via :attr:`_content_extractor`.
        3. Persist a :class:`FileUpload` record via :attr:`_file_repo`.

        Attachments that have only a URL (no ``content``) are skipped --
        remote URL fetching is not implemented yet.

        Returns a list of generated file upload IDs.
        """
        file_ids: list[str] = []

        for att in attachments:
            # Skip attachments without inline content.
            if att.content is None:
                logger.debug(
                    "Skipping attachment %r: no inline content (url=%s)",
                    att.filename,
                    att.url,
                )
                continue

            # 1. Store the file bytes.
            storage_path = await self._file_storage.store(
                att.filename, att.content, att.content_type
            )

            # 2. Extract text for non-image types.
            extracted_text: str | None = None
            if self._content_extractor and not att.content_type.startswith("image/"):
                try:
                    extracted_text = await self._content_extractor.extract(
                        att.filename, att.content, att.content_type
                    )
                except Exception:
                    logger.warning(
                        "Text extraction failed for attachment %r",
                        att.filename,
                        exc_info=True,
                    )

            # 3. Persist the FileUpload record.
            file_id = str(uuid.uuid4())
            upload = FileUpload(
                id=file_id,
                conversation_id=conversation_id,
                user_id=user_id,
                filename=att.filename,
                content_type=att.content_type,
                file_size=len(att.content),
                storage_path=storage_path,
                extracted_text=extracted_text,
                metadata={"source": "email"},
            )
            await self._file_repo.create(upload)
            file_ids.append(file_id)

        return file_ids

    # ------------------------------------------------------------------
    # ChannelPort.send
    # ------------------------------------------------------------------

    async def send(self, conversation_id: str, message: AgentResponse) -> None:
        """Format an agent response as an HTML email and send it.

        Raises :class:`KeyError` if no reply metadata has been stored for
        the given *conversation_id* (i.e. ``receive()`` was never called
        for this conversation).
        """
        settings = await self._settings_repo.get_email_settings()

        # Bail out early if the email channel is disabled.
        if not settings.enabled:
            logger.info(
                "Email channel disabled; skipping send for conversation %s",
                conversation_id,
            )
            return

        if self._conversation_repo is not None:
            meta = await self._conversation_repo.get_conversation_metadata(conversation_id)
            if meta is None or "email_reply_context" not in meta:
                raise KeyError(f"No reply metadata for conversation {conversation_id}")
            reply_meta = meta["email_reply_context"]
        else:
            reply_meta = self._pending_replies.pop(conversation_id)

        # Handle cc_mode.
        if settings.cc_mode == "silent":
            logger.info(
                "cc_mode is 'silent'; skipping reply for conversation %s",
                conversation_id,
            )
            return

        cc = reply_meta.get("cc", []) if settings.cc_mode == "respond_all" else []

        # Simple HTML wrapping (Task 2 replaces this with full markdown->HTML).
        html_body = f"<p>{message.content}</p>"

        # Append signature if configured.
        if settings.include_sign_off and settings.signature_html:
            html_body = f"{html_body}\n{settings.signature_html}"

        email = OutboundEmail(
            from_address=settings.from_address,
            from_name=settings.from_display_name,
            to=reply_meta["to"],
            cc=cc,
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
            if self._callback_dispatcher is not None:
                await self._callback_dispatcher.dispatch("email.sent", {
                    "conversation_id": conversation_id,
                    "to": reply_meta["to"],
                    "subject": reply_meta["subject"],
                    "provider_message_id": result.provider_message_id,
                })
        elif not result.success:
            logger.error(
                "Failed to send email for conversation %s: %s",
                conversation_id,
                result.error,
            )
            if self._callback_dispatcher is not None:
                await self._callback_dispatcher.dispatch("email.failed", {
                    "conversation_id": conversation_id,
                    "to": reply_meta["to"],
                    "subject": reply_meta["subject"],
                    "error": result.error,
                })

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
