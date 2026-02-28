# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Email domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EmailAttachment:
    filename: str
    content_type: str
    size: int
    content: bytes | None = None
    url: str | None = None


@dataclass
class OutboundEmail:
    from_address: str
    from_name: str
    to: list[str]
    subject: str
    html_body: str
    text_body: str = ""
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to: str | None = None
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class InboundEmail:
    from_address: str
    from_name: str | None
    to: list[str]
    cc: list[str]
    subject: str
    text_body: str
    html_body: str | None = None
    message_id: str = ""
    in_reply_to: str | None = None
    references: list[str] = field(default_factory=list)
    attachments: list[EmailAttachment] = field(default_factory=list)
    received_at: datetime | None = None


@dataclass
class SendResult:
    success: bool
    provider_message_id: str | None = None
    error: str | None = None
