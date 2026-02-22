# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Widget type definitions."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class WidgetDisplay(StrEnum):
    INLINE = "inline"
    PANEL = "panel"


class WidgetDirective(BaseModel):
    """A parsed widget directive from agent output."""

    widget_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    props: dict[str, Any] = Field(default_factory=dict)
    display: WidgetDisplay = WidgetDisplay.INLINE
    blocking: bool = False
    action: str | None = None
