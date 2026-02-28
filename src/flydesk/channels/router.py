# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Channel router -- dispatches messages to the correct channel adapter."""

from __future__ import annotations

import logging

from flydesk.channels.models import AgentResponse, Notification
from flydesk.channels.port import ChannelPort

logger = logging.getLogger(__name__)


class ChannelRouter:
    """Routes outbound messages and notifications to the correct channel."""

    def __init__(self) -> None:
        self._adapters: dict[str, ChannelPort] = {}

    def register(self, channel_type: str, adapter: ChannelPort) -> None:
        self._adapters[channel_type] = adapter
        logger.info("Registered channel adapter: %s", channel_type)

    def get_adapter(self, channel_type: str) -> ChannelPort | None:
        return self._adapters.get(channel_type)

    async def send(
        self,
        conversation_id: str,
        channel_type: str,
        response: AgentResponse,
    ) -> None:
        adapter = self._adapters.get(channel_type)
        if adapter is None:
            logger.warning(
                "No adapter for channel %s; dropping message", channel_type
            )
            return
        await adapter.send(conversation_id, response)

    async def notify(
        self,
        user_id: str,
        channel_type: str,
        notification: Notification,
    ) -> None:
        adapter = self._adapters.get(channel_type)
        if adapter is None:
            logger.warning(
                "No adapter for channel %s; dropping notification", channel_type
            )
            return
        await adapter.send_notification(user_id, notification)
