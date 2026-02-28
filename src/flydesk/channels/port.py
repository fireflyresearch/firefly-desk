# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Channel port protocol -- abstraction for communication channels."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flydesk.channels.models import AgentResponse, InboundMessage, Notification


@runtime_checkable
class ChannelPort(Protocol):
    """Protocol that all channel implementations must satisfy.

    Each channel adapter (e.g. web-chat, email, Slack) implements this
    protocol to normalise inbound messages and deliver agent responses
    and notifications through the appropriate transport.
    """

    channel_type: str

    async def receive(self, raw_event: dict) -> InboundMessage: ...

    async def send(self, conversation_id: str, message: AgentResponse) -> None: ...

    async def send_notification(self, user_id: str, notification: Notification) -> None: ...
