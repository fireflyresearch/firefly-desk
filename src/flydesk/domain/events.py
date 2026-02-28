# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Domain event protocols.

AgentEventSink decouples the agent from the SSE presentation layer.
The API layer provides an SSE adapter; tests provide a fake.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AgentEventSink(Protocol):
    """Protocol for emitting agent events to any consumer."""

    async def emit(self, event_type: str, data: dict[str, Any]) -> None: ...
