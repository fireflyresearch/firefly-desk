# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""In-memory webhook log for debugging inbound email processing."""

from __future__ import annotations

import uuid
from collections import deque
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


class WebhookLog:
    """In-memory ring buffer of recent webhook payloads (max 100 entries)."""

    def __init__(self, max_entries: int = 100) -> None:
        self._entries: deque[WebhookLogEntry] = deque(maxlen=max_entries)

    def record(self, entry: WebhookLogEntry) -> None:
        """Append an entry, evicting the oldest if over the limit."""
        self._entries.append(entry)

    def list(self, limit: int = 50) -> list[WebhookLogEntry]:
        """Return the most recent entries (newest first)."""
        entries = list(reversed(self._entries))
        return entries[:limit]

    def get(self, entry_id: str) -> WebhookLogEntry | None:
        """Look up a single entry by ID."""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def clear(self) -> None:
        """Remove all entries."""
        self._entries.clear()
