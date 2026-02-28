# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SendGrid email adapter."""

from __future__ import annotations

import logging

import httpx

from flydesk.email.models import EmailAttachment, InboundEmail, OutboundEmail, SendResult

logger = logging.getLogger(__name__)


class SendGridEmailAdapter:
    """Email adapter using the SendGrid v3 API.

    The *api_base* parameter allows overriding the default SendGrid API
    endpoint, which is useful for testing or proxying through a gateway.
    """

    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.sendgrid.com",
    ) -> None:
        self._api_key = api_key
        self._api_base = api_base.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self._api_base,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------

    async def validate(self) -> SendResult:
        """Test the API key by hitting the scopes endpoint."""
        try:
            response = await self._client.get("/v3/scopes")
            response.raise_for_status()
            return SendResult(
                success=True,
                provider_message_id=None,
                error=None,
                metadata={"scopes": response.json().get("scopes", [])},
            )
        except Exception as exc:
            logger.exception("SendGrid validation failed")
            msg = str(exc)
            if "401" in msg or "403" in msg or "unauthorized" in msg.lower():
                return SendResult(success=False, error="Invalid API key")
            return SendResult(success=False, error=msg)

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    async def send(self, email: OutboundEmail) -> SendResult:
        """Send an outbound email via the SendGrid v3 Mail Send API."""
        try:
            personalizations: dict = {
                "to": [{"email": addr} for addr in email.to],
            }
            if email.cc:
                personalizations["cc"] = [{"email": addr} for addr in email.cc]
            if email.bcc:
                personalizations["bcc"] = [{"email": addr} for addr in email.bcc]

            content: list[dict] = [
                {"type": "text/html", "value": email.html_body},
            ]
            if email.text_body:
                content.insert(0, {"type": "text/plain", "value": email.text_body})

            payload: dict = {
                "personalizations": [personalizations],
                "from": {"email": email.from_address, "name": email.from_name},
                "subject": email.subject,
                "content": content,
            }

            if email.reply_to:
                payload["reply_to"] = {"email": email.reply_to}

            headers: dict[str, str] = {}
            if email.in_reply_to:
                headers["In-Reply-To"] = email.in_reply_to
            if email.references:
                headers["References"] = " ".join(email.references)
            if email.headers:
                headers.update(email.headers)
            if headers:
                payload["headers"] = headers

            response = await self._client.post("/v3/mail/send", json=payload)
            response.raise_for_status()

            message_id = response.headers.get("X-Message-Id")
            return SendResult(success=True, provider_message_id=message_id)

        except Exception as exc:
            logger.exception("SendGrid send failed")
            return SendResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Inbound parsing
    # ------------------------------------------------------------------

    async def parse_inbound(self, webhook_payload: dict) -> InboundEmail:
        """Parse a SendGrid Inbound Parse webhook payload."""
        attachments = []
        for att in webhook_payload.get("attachments", []):
            attachments.append(
                EmailAttachment(
                    filename=att.get("filename", ""),
                    content_type=att.get("content_type", att.get("type", "application/octet-stream")),
                    size=att.get("size", 0),
                    url=att.get("url"),
                )
            )

        from_field = webhook_payload.get("from", "")
        from_name: str | None = None
        from_address = from_field

        if "<" in from_field and ">" in from_field:
            from_name = from_field[: from_field.index("<")].strip().strip('"')
            from_address = from_field[from_field.index("<") + 1 : from_field.index(">")]

        to_raw = webhook_payload.get("to", "")
        to_list = [addr.strip() for addr in to_raw.split(",")] if isinstance(to_raw, str) else to_raw

        cc_raw = webhook_payload.get("cc", "")
        cc_list = [addr.strip() for addr in cc_raw.split(",") if addr.strip()] if isinstance(cc_raw, str) else cc_raw

        return InboundEmail(
            from_address=from_address,
            from_name=from_name,
            to=to_list,
            cc=cc_list,
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
        """Verify a SendGrid webhook signature.

        .. note::
            This is a simplified stub. A production implementation should
            validate the signature using the SendGrid Event Webhook
            verification key.
        """
        return True

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
