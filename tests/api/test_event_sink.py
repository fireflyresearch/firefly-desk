# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SSEAgentEventSink."""
from __future__ import annotations

import pytest

from flydesk.api.event_sink import SSEAgentEventSink
from flydesk.domain.events import AgentEventSink


def test_satisfies_protocol():
    sink = SSEAgentEventSink()
    assert isinstance(sink, AgentEventSink)


@pytest.mark.asyncio
async def test_emit_produces_sse_event():
    sink = SSEAgentEventSink()
    await sink.emit("token", {"text": "hello"})
    events = sink.drain()
    assert len(events) == 1
    assert events[0].event == "token"
    assert events[0].data["text"] == "hello"


@pytest.mark.asyncio
async def test_drain_clears_events():
    sink = SSEAgentEventSink()
    await sink.emit("token", {"text": "a"})
    await sink.emit("done", {})
    events = sink.drain()
    assert len(events) == 2
    assert sink.drain() == []
