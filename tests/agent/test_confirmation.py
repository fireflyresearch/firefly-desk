# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the ConfirmationService safety gate."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from flydesk.agent.confirmation import ConfirmationService, PendingConfirmation
from flydesk.catalog.enums import RiskLevel
from flydesk.tools.executor import ToolCall
from flydesk.tools.factory import ToolDefinition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_def(risk_level: RiskLevel, name: str = "test_tool") -> ToolDefinition:
    return ToolDefinition(
        endpoint_id=f"ep-{name}",
        name=name,
        description=f"A {risk_level} tool",
        risk_level=risk_level,
        system_id="sys-1",
        method="POST",
        path=f"/{name}",
    )


def _make_tool_call(name: str = "test_tool") -> ToolCall:
    return ToolCall(
        call_id=f"call-{name}",
        tool_name=name,
        endpoint_id=f"ep-{name}",
        arguments={"body": {"id": "123"}},
    )


# ---------------------------------------------------------------------------
# requires_confirmation tests
# ---------------------------------------------------------------------------

class TestRequiresConfirmation:
    """Tests for ConfirmationService.requires_confirmation."""

    def test_read_does_not_require_confirmation(self):
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.READ)
        assert svc.requires_confirmation(tool_def, ["orders:read"]) is False

    def test_low_write_does_not_require_confirmation(self):
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.LOW_WRITE)
        assert svc.requires_confirmation(tool_def, ["orders:write"]) is False

    def test_high_write_requires_confirmation(self):
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)
        assert svc.requires_confirmation(tool_def, ["orders:write"]) is True

    def test_destructive_requires_confirmation(self):
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE)
        assert svc.requires_confirmation(tool_def, ["orders:write"]) is True

    def test_admin_wildcard_bypasses_high_write(self):
        """A user with '*' permission should bypass HIGH_WRITE confirmation."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)
        assert svc.requires_confirmation(tool_def, ["*"]) is False

    def test_admin_wildcard_cannot_bypass_destructive(self):
        """Even an admin with '*' must confirm DESTRUCTIVE operations."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE)
        assert svc.requires_confirmation(tool_def, ["*"]) is True


# ---------------------------------------------------------------------------
# create_confirmation tests
# ---------------------------------------------------------------------------

class TestCreateConfirmation:
    """Tests for ConfirmationService.create_confirmation."""

    def test_creates_pending_entry(self):
        svc = ConfirmationService()
        tool_call = _make_tool_call()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")

        assert isinstance(pc, PendingConfirmation)
        assert pc.tool_call is tool_call
        assert pc.risk_level == RiskLevel.HIGH_WRITE
        assert pc.user_id == "user-1"
        assert pc.conversation_id == "conv-1"
        assert pc.confirmation_id  # non-empty
        assert pc.expires_at > pc.created_at

    def test_max_pending_evicts_oldest(self):
        """When max_pending is reached, the oldest entry is evicted."""
        svc = ConfirmationService(max_pending=2)
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)

        pc1 = svc.create_confirmation(
            _make_tool_call("t1"), tool_def, "user-1", "conv-1",
        )
        _pc2 = svc.create_confirmation(
            _make_tool_call("t2"), tool_def, "user-1", "conv-1",
        )
        _pc3 = svc.create_confirmation(
            _make_tool_call("t3"), tool_def, "user-1", "conv-1",
        )

        # pc1 should have been evicted
        assert svc.approve(pc1.confirmation_id) is None
        # We should have exactly 2 entries
        assert len(svc.get_pending("conv-1")) == 2


# ---------------------------------------------------------------------------
# approve / reject tests
# ---------------------------------------------------------------------------

class TestApproveReject:
    """Tests for approve() and reject()."""

    def test_approve_returns_and_removes(self):
        svc = ConfirmationService()
        tool_call = _make_tool_call()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE)

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")
        result = svc.approve(pc.confirmation_id)

        assert result is pc
        # Should be gone now.
        assert svc.approve(pc.confirmation_id) is None

    def test_reject_returns_and_removes(self):
        svc = ConfirmationService()
        tool_call = _make_tool_call()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE)

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")
        result = svc.reject(pc.confirmation_id)

        assert result is pc
        assert svc.reject(pc.confirmation_id) is None

    def test_approve_returns_none_for_unknown_id(self):
        svc = ConfirmationService()
        assert svc.approve("nonexistent-id") is None

    def test_approve_returns_none_for_expired_entry(self):
        """An entry that has expired should be evicted and return None."""
        svc = ConfirmationService(timeout_seconds=1)
        tool_call = _make_tool_call()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE)

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")

        # Simulate time passing beyond the timeout.
        with patch("flydesk.agent.confirmation.time") as mock_time:
            mock_time.monotonic.return_value = pc.expires_at + 1
            assert svc.approve(pc.confirmation_id) is None


# ---------------------------------------------------------------------------
# get_pending tests
# ---------------------------------------------------------------------------

class TestGetPending:
    """Tests for get_pending() filtering by conversation."""

    def test_filters_by_conversation_id(self):
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)

        svc.create_confirmation(
            _make_tool_call("t1"), tool_def, "user-1", "conv-A",
        )
        svc.create_confirmation(
            _make_tool_call("t2"), tool_def, "user-1", "conv-B",
        )
        svc.create_confirmation(
            _make_tool_call("t3"), tool_def, "user-1", "conv-A",
        )

        conv_a = svc.get_pending("conv-A")
        conv_b = svc.get_pending("conv-B")

        assert len(conv_a) == 2
        assert len(conv_b) == 1
        assert all(pc.conversation_id == "conv-A" for pc in conv_a)

    def test_expired_entries_evicted_on_get_pending(self):
        """Expired entries are cleaned up when get_pending is called."""
        svc = ConfirmationService(timeout_seconds=1)
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE)

        pc = svc.create_confirmation(
            _make_tool_call("t1"), tool_def, "user-1", "conv-1",
        )

        with patch("flydesk.agent.confirmation.time") as mock_time:
            mock_time.monotonic.return_value = pc.expires_at + 1
            assert svc.get_pending("conv-1") == []
