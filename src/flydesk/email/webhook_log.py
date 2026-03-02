# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Webhook log entry dataclass for inbound email processing."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class WebhookLogEntry:
    """A single recorded webhook event."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    provider: str = ""
    status: str = "received"  # received | processed | skipped | error
    from_address: str = ""
    subject: str = ""
    payload_preview: str = ""  # first 500 chars of JSON
    processing_time_ms: float = 0.0
    error: str | None = None
