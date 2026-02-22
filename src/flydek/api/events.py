# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSE event types for the chat stream."""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class SSEEventType(StrEnum):
    TOKEN = "token"
    WIDGET = "widget"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    CONFIRMATION = "confirmation"
    ERROR = "error"
    DONE = "done"


class SSEEvent(BaseModel):
    """A typed SSE event for the chat stream."""

    event: SSEEventType
    data: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Format as an SSE message."""
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"
