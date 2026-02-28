# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Verify AgentEventSink protocol."""
from typing import Any

import pytest

from flydesk.domain.events import AgentEventSink


class FakeEventSink:
    """Minimal implementation of AgentEventSink for testing."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self.events.append((event_type, data))


def test_fake_sink_satisfies_protocol():
    sink = FakeEventSink()
    assert isinstance(sink, AgentEventSink)


@pytest.mark.asyncio
async def test_emit_records_events():
    sink = FakeEventSink()
    await sink.emit("token", {"text": "hello"})
    assert sink.events == [("token", {"text": "hello"})]
