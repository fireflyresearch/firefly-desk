# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Pydantic domain models for custom tools."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ToolSource(StrEnum):
    """How a custom tool was created."""

    MANUAL = "manual"
    BUILTIN = "builtin"
    IMPORTED = "imported"


class CustomTool(BaseModel):
    """A user-defined or built-in tool with executable Python code."""

    id: str
    name: str
    description: str
    python_code: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    source: ToolSource = ToolSource.MANUAL
    timeout_seconds: int = 30
    max_memory_mb: int = 256
    created_by: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
