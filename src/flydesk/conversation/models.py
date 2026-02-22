# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Pydantic domain models for Conversations and Messages."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """A single message within a conversation."""

    id: str
    conversation_id: str
    role: MessageRole
    content: str
    file_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class Conversation(BaseModel):
    """A conversation between a user and the assistant."""

    id: str
    title: str | None = None
    user_id: str
    model_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    message_count: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConversationWithMessages(Conversation):
    """A conversation with its full message history."""

    messages: list[Message] = Field(default_factory=list)
