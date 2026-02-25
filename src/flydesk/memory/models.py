# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Pydantic domain models for user memories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserMemory(BaseModel):
    """Domain model for a user memory."""

    id: str
    user_id: str
    content: str
    category: str = "general"
    source: str = "agent"
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateMemory(BaseModel):
    """Input model for creating a memory."""

    content: str = Field(..., min_length=1, max_length=5000)
    category: str = Field(default="general", pattern=r"^(general|preference|fact|workflow)$")
    source: str = Field(default="agent", pattern=r"^(agent|user)$")
    metadata: dict[str, Any] | None = None


class UpdateMemory(BaseModel):
    """Input model for updating a memory."""

    content: str | None = Field(default=None, min_length=1, max_length=5000)
    category: str | None = Field(default=None, pattern=r"^(general|preference|fact|workflow)$")
