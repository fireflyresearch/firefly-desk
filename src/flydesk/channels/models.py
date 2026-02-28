# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Normalized models for cross-channel communication."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Attachment:
    filename: str
    content_type: str
    size: int
    data: bytes | None = None
    url: str | None = None


@dataclass
class InboundMessage:
    channel: str
    user_id: str
    conversation_id: str | None = None
    content: str = ""
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    reply_to_message_id: str | None = None
    received_at: datetime | None = None


@dataclass
class AgentResponse:
    content: str
    metadata: dict = field(default_factory=dict)
    widgets: list[dict] = field(default_factory=list)


@dataclass
class Notification:
    title: str
    summary: str
    workflow_id: str | None = None
    metadata: dict = field(default_factory=dict)
