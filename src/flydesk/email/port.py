# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Email port protocol -- abstraction for email send/receive."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flydesk.email.models import InboundEmail, OutboundEmail, SendResult


@runtime_checkable
class EmailPort(Protocol):
    """Port for email operations."""

    async def send(self, email: OutboundEmail) -> SendResult:
        """Send an email. Returns result with provider message ID."""
        ...

    async def parse_inbound(self, webhook_payload: dict) -> InboundEmail:
        """Parse a provider-specific inbound webhook into a normalized email."""
        ...

    async def verify_webhook_signature(self, headers: dict, body: bytes) -> bool:
        """Verify the webhook signature from the provider."""
        ...
