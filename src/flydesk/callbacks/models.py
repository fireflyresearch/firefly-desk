# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Outbound callback (webhook) models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class CallbackEvent(str, Enum):
    """Events that can trigger an outbound callback."""

    EMAIL_SENT = "email.sent"
    EMAIL_RECEIVED = "email.received"
    EMAIL_FAILED = "email.failed"
    CONVERSATION_CREATED = "conversation.created"
    CONVERSATION_UPDATED = "conversation.updated"
    AGENT_ERROR = "agent.error"


class CallbackConfig(BaseModel):
    """Configuration for a single outbound callback endpoint."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    url: str = ""
    secret: str = Field(default_factory=lambda: uuid.uuid4().hex)
    events: list[str] = Field(default_factory=list)
    enabled: bool = True
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class CallbackPayload(BaseModel):
    """Payload sent to callback endpoints."""

    event: str
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    data: dict = Field(default_factory=dict)
