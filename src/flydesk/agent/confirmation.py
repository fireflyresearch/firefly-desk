# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Safety confirmation service for high-risk tool execution."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from flydesk.catalog.enums import RiskLevel

if TYPE_CHECKING:
    from flydesk.tools.executor import ToolCall
    from flydesk.tools.factory import ToolDefinition


@dataclass
class PendingConfirmation:
    """A tool call awaiting user confirmation before execution."""

    confirmation_id: str
    tool_call: ToolCall
    risk_level: RiskLevel
    user_id: str
    conversation_id: str
    created_at: float
    expires_at: float


class ConfirmationService:
    """Gate high-risk tool calls behind explicit user confirmation.

    Confirmation rules:
    - ``READ`` and ``LOW_WRITE`` tools never require confirmation.
    - ``HIGH_WRITE`` tools require confirmation *unless* the user holds the
      wildcard ``*`` permission (admin bypass).
    - ``DESTRUCTIVE`` tools always require confirmation, regardless of
      permissions.
    """

    def __init__(
        self,
        timeout_seconds: int = 300,
        max_pending: int = 10,
    ) -> None:
        self._pending: dict[str, PendingConfirmation] = {}
        self._timeout = timeout_seconds
        self._max_pending = max_pending

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def requires_confirmation(
        self,
        tool_def: ToolDefinition,
        user_permissions: list[str],
    ) -> bool:
        """Check if a tool requires confirmation based on risk level and user role.

        Returns ``True`` when the tool call must be explicitly approved by the
        user before execution.
        """
        if tool_def.risk_level in (RiskLevel.READ, RiskLevel.LOW_WRITE):
            return False

        if tool_def.risk_level == RiskLevel.DESTRUCTIVE:
            return True

        # HIGH_WRITE: admin with wildcard bypasses confirmation.
        if tool_def.risk_level == RiskLevel.HIGH_WRITE:
            return "*" not in user_permissions

        return True  # pragma: no cover -- defensive fallback

    def create_confirmation(
        self,
        tool_call: ToolCall,
        tool_def: ToolDefinition,
        user_id: str,
        conversation_id: str,
    ) -> PendingConfirmation:
        """Create a pending confirmation entry for a tool call.

        Expired entries are evicted first. If the number of pending entries
        would exceed ``max_pending``, the oldest entry is evicted.
        """
        self._evict_expired()

        if len(self._pending) >= self._max_pending:
            oldest_key = min(
                self._pending, key=lambda k: self._pending[k].created_at,
            )
            del self._pending[oldest_key]

        now = time.monotonic()
        confirmation = PendingConfirmation(
            confirmation_id=str(uuid.uuid4()),
            tool_call=tool_call,
            risk_level=tool_def.risk_level,
            user_id=user_id,
            conversation_id=conversation_id,
            created_at=now,
            expires_at=now + self._timeout,
        )
        self._pending[confirmation.confirmation_id] = confirmation
        return confirmation

    def approve(self, confirmation_id: str) -> PendingConfirmation | None:
        """Approve and remove a pending confirmation.

        Returns the confirmation if it exists and has not expired, otherwise
        ``None``.
        """
        self._evict_expired()
        return self._pending.pop(confirmation_id, None)

    def reject(self, confirmation_id: str) -> PendingConfirmation | None:
        """Reject and remove a pending confirmation.

        Returns the confirmation so callers can reference it, or ``None`` if
        it was not found (already expired or never existed).
        """
        self._evict_expired()
        return self._pending.pop(confirmation_id, None)

    def get_pending(self, conversation_id: str) -> list[PendingConfirmation]:
        """List all pending confirmations for a given conversation."""
        self._evict_expired()
        return [
            pc
            for pc in self._pending.values()
            if pc.conversation_id == conversation_id
        ]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _evict_expired(self) -> None:
        """Remove entries whose ``expires_at`` has passed."""
        now = time.monotonic()
        expired = [
            cid
            for cid, pc in self._pending.items()
            if pc.expires_at <= now
        ]
        for cid in expired:
            del self._pending[cid]
