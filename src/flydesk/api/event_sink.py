# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSE adapter for the domain AgentEventSink protocol."""
from __future__ import annotations

from typing import Any

from flydesk.api.events import SSEEvent


class SSEAgentEventSink:
    """Collects domain events and maps them to SSEEvent objects."""

    def __init__(self) -> None:
        self._events: list[SSEEvent] = []

    async def emit(self, event_type: str, data: dict[str, Any]) -> None:
        self._events.append(SSEEvent(event=event_type, data=data))

    def drain(self) -> list[SSEEvent]:
        """Return and clear collected events."""
        events = list(self._events)
        self._events.clear()
        return events
