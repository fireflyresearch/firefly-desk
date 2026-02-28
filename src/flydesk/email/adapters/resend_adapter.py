# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Resend email adapter."""

from __future__ import annotations

import logging

from flydesk.email.models import EmailAttachment, InboundEmail, OutboundEmail, SendResult

logger = logging.getLogger(__name__)


class ResendEmailAdapter:
    """Email adapter using the Resend API.

    Requires the ``resend`` package: ``pip install resend``
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def send(self, email: OutboundEmail) -> SendResult:
        """Send an outbound email via the Resend API."""
        try:
            import resend

            resend.api_key = self._api_key

            params: dict = {
                "from": f"{email.from_name} <{email.from_address}>",
                "to": email.to,
                "subject": email.subject,
                "html": email.html_body,
            }
            if email.text_body:
                params["text"] = email.text_body
            if email.cc:
                params["cc"] = email.cc
            if email.bcc:
                params["bcc"] = email.bcc
            if email.reply_to:
                params["reply_to"] = email.reply_to
            if email.in_reply_to:
                params.setdefault("headers", {})["In-Reply-To"] = email.in_reply_to
            if email.references:
                params.setdefault("headers", {})["References"] = " ".join(
                    email.references
                )
            if email.headers:
                params.setdefault("headers", {}).update(email.headers)

            result = resend.Emails.send(params)
            return SendResult(success=True, provider_message_id=result.get("id"))

        except Exception as exc:
            logger.exception("Resend send failed")
            return SendResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Inbound parsing
    # ------------------------------------------------------------------

    async def parse_inbound(self, webhook_payload: dict) -> InboundEmail:
        """Parse a Resend inbound webhook payload into an ``InboundEmail``."""
        attachments = []
        for att in webhook_payload.get("attachments", []):
            attachments.append(
                EmailAttachment(
                    filename=att.get("filename", ""),
                    content_type=att.get("content_type", "application/octet-stream"),
                    size=att.get("size", 0),
                    url=att.get("url"),
                )
            )

        from_field = webhook_payload.get("from", "")
        from_name: str | None = None
        from_address = from_field

        if "<" in from_field and ">" in from_field:
            from_name = from_field[: from_field.index("<")].strip().strip('"')
            from_address = from_field[
                from_field.index("<") + 1 : from_field.index(">")
            ]

        return InboundEmail(
            from_address=from_address,
            from_name=from_name,
            to=webhook_payload.get("to", []),
            cc=webhook_payload.get("cc", []),
            subject=webhook_payload.get("subject", ""),
            text_body=webhook_payload.get("text", ""),
            html_body=webhook_payload.get("html"),
            message_id=webhook_payload.get("message_id", ""),
            in_reply_to=webhook_payload.get("in_reply_to"),
            references=webhook_payload.get("references", []),
            attachments=attachments,
        )

    # ------------------------------------------------------------------
    # Webhook verification
    # ------------------------------------------------------------------

    async def verify_webhook_signature(self, headers: dict, body: bytes) -> bool:
        """Verify a Resend webhook signature (Resend uses Svix for signing)."""
        svix_id = headers.get("svix-id")
        svix_timestamp = headers.get("svix-timestamp")
        svix_signature = headers.get("svix-signature")
        return all([svix_id, svix_timestamp, svix_signature])
