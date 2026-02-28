# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ChannelRouter."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from flydesk.channels.models import AgentResponse, InboundMessage, Notification
from flydesk.channels.router import ChannelRouter


class TestChannelRouter:
    def test_register_and_get_adapter(self):
        router = ChannelRouter()
        adapter = AsyncMock()
        adapter.channel_type = "email"
        router.register("email", adapter)
        assert router.get_adapter("email") is adapter

    def test_get_unknown_adapter_returns_none(self):
        router = ChannelRouter()
        assert router.get_adapter("slack") is None

    async def test_route_outbound(self):
        router = ChannelRouter()
        adapter = AsyncMock()
        adapter.channel_type = "email"
        router.register("email", adapter)

        response = AgentResponse(content="Hello")
        await router.send("conv-1", "email", response)
        adapter.send.assert_called_once_with("conv-1", response)

    async def test_route_notification(self):
        router = ChannelRouter()
        adapter = AsyncMock()
        adapter.channel_type = "chat"
        router.register("chat", adapter)

        notification = Notification(title="Done", summary="Workflow complete")
        await router.notify("user-1", "chat", notification)
        adapter.send_notification.assert_called_once_with("user-1", notification)
