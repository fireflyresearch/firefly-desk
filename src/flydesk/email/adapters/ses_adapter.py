# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""AWS SES email adapter."""

from __future__ import annotations

import logging

from flydesk.email.models import InboundEmail, OutboundEmail, SendResult

logger = logging.getLogger(__name__)


class SESEmailAdapter:
    """Email adapter using AWS SES.

    Requires boto3: ``pip install boto3``

    When *access_key_id* and *secret_access_key* are omitted the adapter
    falls back to the default boto3 credential chain (env vars, instance
    profile, etc.).
    """

    def __init__(
        self,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._region = region
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key

    def _get_client(self):
        """Create a boto3 SES client.

        ``boto3`` is imported lazily so the adapter module can be loaded
        even when the dependency is not installed.
        """
        import boto3  # noqa: WPS433 (nested import)

        kwargs: dict[str, str] = {"region_name": self._region}
        if self._access_key_id and self._secret_access_key:
            kwargs["aws_access_key_id"] = self._access_key_id
            kwargs["aws_secret_access_key"] = self._secret_access_key
        return boto3.client("ses", **kwargs)

    # ------------------------------------------------------------------
    # EmailPort interface
    # ------------------------------------------------------------------

    async def send(self, email: OutboundEmail) -> SendResult:
        """Send an email via AWS SES."""
        try:
            import asyncio

            client = self._get_client()

            destination: dict[str, list[str]] = {"ToAddresses": email.to}
            if email.cc:
                destination["CcAddresses"] = email.cc
            if email.bcc:
                destination["BccAddresses"] = email.bcc

            message: dict = {
                "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": email.html_body, "Charset": "UTF-8"},
                },
            }
            if email.text_body:
                message["Body"]["Text"] = {
                    "Data": email.text_body,
                    "Charset": "UTF-8",
                }

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: client.send_email(
                    Source=f"{email.from_name} <{email.from_address}>",
                    Destination=destination,
                    Message=message,
                ),
            )
            return SendResult(
                success=True,
                provider_message_id=result.get("MessageId"),
            )

        except Exception as exc:
            logger.exception("SES send failed")
            return SendResult(success=False, error=str(exc))

    async def parse_inbound(self, webhook_payload: dict) -> InboundEmail:
        """Parse an SES inbound notification (delivered via SNS).

        The expected payload shape mirrors what SES publishes to an SNS
        topic when a receiving rule is configured.
        """
        mail = webhook_payload.get("mail", {})
        headers = mail.get("commonHeaders", {})

        from_list = headers.get("from", [])
        from_address = from_list[0] if from_list else mail.get("source", "")

        return InboundEmail(
            from_address=from_address,
            from_name=None,
            to=headers.get("to", mail.get("destination", [])),
            cc=headers.get("cc", []),
            subject=headers.get("subject", ""),
            text_body=webhook_payload.get("content", ""),
            message_id=headers.get("messageId", ""),
            in_reply_to=None,
            references=[],
        )

    async def verify_webhook_signature(
        self,
        headers: dict,
        body: bytes,
    ) -> bool:
        """Verify an SNS notification signature.

        .. note::
            This is a simplified stub. A production implementation should
            validate the SNS message signature using the certificate URL
            provided in the notification.
        """
        return True
