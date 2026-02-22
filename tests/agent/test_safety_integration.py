# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Integration tests for the safety confirmation flow.

These tests exercise the full confirmation lifecycle: risk-level
evaluation, confirmation creation, approval/rejection, expiry, and
admin bypass logic -- all wired together without mocks.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from flydek.agent.confirmation import ConfirmationService, PendingConfirmation
from flydek.catalog.enums import RiskLevel
from flydek.tools.executor import ToolCall
from flydek.tools.factory import ToolDefinition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tool_def(risk_level: RiskLevel, name: str = "test_tool") -> ToolDefinition:
    return ToolDefinition(
        endpoint_id=f"ep-{name}",
        name=name,
        description=f"A {risk_level.value} tool",
        risk_level=risk_level,
        system_id="sys-integ",
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
# Integration Tests
# ---------------------------------------------------------------------------


class TestSafetyIntegration:
    """End-to-end confirmation flow: create -> approve/reject -> consume."""

    def test_high_write_create_approve_consume(self):
        """Full lifecycle: create a HIGH_WRITE confirmation, approve it, verify consumed."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE, "update_account")
        tool_call = _make_tool_call("update_account")
        user_perms = ["accounts:write"]

        # 1. Verify HIGH_WRITE requires confirmation for non-admin
        assert svc.requires_confirmation(tool_def, user_perms) is True

        # 2. Create the confirmation
        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")
        assert isinstance(pc, PendingConfirmation)
        assert pc.risk_level == RiskLevel.HIGH_WRITE
        assert pc.user_id == "user-1"
        assert pc.conversation_id == "conv-1"

        # 3. Verify it appears in pending list
        pending = svc.get_pending("conv-1")
        assert len(pending) == 1
        assert pending[0].confirmation_id == pc.confirmation_id

        # 4. Approve the confirmation
        approved = svc.approve(pc.confirmation_id)
        assert approved is pc
        assert approved.tool_call is tool_call

        # 5. Verify it is consumed -- second approve returns None
        assert svc.approve(pc.confirmation_id) is None
        assert svc.get_pending("conv-1") == []

    def test_reject_confirmation_consumed(self):
        """Rejecting a confirmation removes it so it cannot be reused."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE, "cancel_order")
        tool_call = _make_tool_call("cancel_order")

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")
        assert len(svc.get_pending("conv-1")) == 1

        # Reject the confirmation
        rejected = svc.reject(pc.confirmation_id)
        assert rejected is pc
        assert rejected.risk_level == RiskLevel.HIGH_WRITE

        # Verify consumed: cannot reject or approve again
        assert svc.reject(pc.confirmation_id) is None
        assert svc.approve(pc.confirmation_id) is None
        assert svc.get_pending("conv-1") == []

    def test_expired_confirmation_rejected(self):
        """An expired confirmation cannot be approved."""
        svc = ConfirmationService(timeout_seconds=1)
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE, "delete_account")
        tool_call = _make_tool_call("delete_account")

        pc = svc.create_confirmation(tool_call, tool_def, "user-1", "conv-1")
        assert pc.confirmation_id  # non-empty

        # Simulate time passing beyond the timeout
        with patch("flydek.agent.confirmation.time") as mock_time:
            mock_time.monotonic.return_value = pc.expires_at + 10

            # Approval should fail because the entry expired
            assert svc.approve(pc.confirmation_id) is None

            # Pending list should be empty too
            assert svc.get_pending("conv-1") == []

    def test_admin_bypasses_high_write(self):
        """A user with wildcard '*' permission bypasses HIGH_WRITE confirmation."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.HIGH_WRITE, "update_config")
        admin_perms = ["*"]

        # Admin does not need confirmation for HIGH_WRITE
        assert svc.requires_confirmation(tool_def, admin_perms) is False

        # Verify READ and LOW_WRITE also do not require confirmation
        read_tool = _make_tool_def(RiskLevel.READ, "get_config")
        low_tool = _make_tool_def(RiskLevel.LOW_WRITE, "patch_label")
        assert svc.requires_confirmation(read_tool, admin_perms) is False
        assert svc.requires_confirmation(low_tool, admin_perms) is False

    def test_destructive_always_requires_confirmation_even_for_admin(self):
        """DESTRUCTIVE operations always require confirmation, even for admins."""
        svc = ConfirmationService()
        tool_def = _make_tool_def(RiskLevel.DESTRUCTIVE, "purge_database")
        admin_perms = ["*"]

        # Admin still needs confirmation for DESTRUCTIVE
        assert svc.requires_confirmation(tool_def, admin_perms) is True

        # Full lifecycle: create, approve, consume
        tool_call = _make_tool_call("purge_database")
        pc = svc.create_confirmation(tool_call, tool_def, "admin-1", "conv-admin")
        assert pc.risk_level == RiskLevel.DESTRUCTIVE

        pending = svc.get_pending("conv-admin")
        assert len(pending) == 1

        approved = svc.approve(pc.confirmation_id)
        assert approved is not None
        assert approved.tool_call.tool_name == "purge_database"
        assert svc.get_pending("conv-admin") == []

    def test_multiple_confirmations_independent_lifecycle(self):
        """Multiple confirmations in the same conversation are independent."""
        svc = ConfirmationService()
        tool_def_hw = _make_tool_def(RiskLevel.HIGH_WRITE, "transfer_funds")
        tool_def_d = _make_tool_def(RiskLevel.DESTRUCTIVE, "close_account")

        pc1 = svc.create_confirmation(
            _make_tool_call("transfer_funds"), tool_def_hw, "user-1", "conv-1",
        )
        pc2 = svc.create_confirmation(
            _make_tool_call("close_account"), tool_def_d, "user-1", "conv-1",
        )

        # Both should be pending
        pending = svc.get_pending("conv-1")
        assert len(pending) == 2
        ids = {p.confirmation_id for p in pending}
        assert pc1.confirmation_id in ids
        assert pc2.confirmation_id in ids

        # Approve pc1 -- pc2 should still be pending
        svc.approve(pc1.confirmation_id)
        pending = svc.get_pending("conv-1")
        assert len(pending) == 1
        assert pending[0].confirmation_id == pc2.confirmation_id

        # Reject pc2 -- nothing left
        svc.reject(pc2.confirmation_id)
        assert svc.get_pending("conv-1") == []

        # Both are consumed
        assert svc.approve(pc1.confirmation_id) is None
        assert svc.reject(pc2.confirmation_id) is None
