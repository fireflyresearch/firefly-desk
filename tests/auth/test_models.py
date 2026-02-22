# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for authentication models."""

from __future__ import annotations

from datetime import datetime, timezone

from flydesk.auth.models import UserSession


class TestUserSessionCreation:
    def test_user_session_creation(self):
        """Create a UserSession with all fields populated."""
        expires = datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        session = UserSession(
            user_id="user-123",
            email="alice@example.com",
            display_name="Alice Smith",
            roles=["admin", "operator"],
            permissions=["tickets:read", "tickets:write"],
            tenant_id="tenant-abc",
            session_id="sess-001",
            token_expires_at=expires,
            raw_claims={"sub": "user-123", "custom": "value"},
        )
        assert session.user_id == "user-123"
        assert session.email == "alice@example.com"
        assert session.display_name == "Alice Smith"
        assert session.roles == ["admin", "operator"]
        assert session.permissions == ["tickets:read", "tickets:write"]
        assert session.tenant_id == "tenant-abc"
        assert session.session_id == "sess-001"
        assert session.token_expires_at == expires
        assert session.raw_claims == {"sub": "user-123", "custom": "value"}

    def test_user_session_defaults(self):
        """Verify default empty lists for roles, permissions, and raw_claims."""
        session = UserSession(
            user_id="user-456",
            email="bob@example.com",
            display_name="Bob Jones",
            session_id="sess-002",
            token_expires_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
        )
        assert session.roles == []
        assert session.permissions == []
        assert session.tenant_id is None
        assert session.raw_claims == {}

    def test_user_session_with_tenant(self):
        """Verify tenant_id is optional and accepts None or a value."""
        session_no_tenant = UserSession(
            user_id="user-789",
            email="carol@example.com",
            display_name="Carol",
            session_id="sess-003",
            token_expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert session_no_tenant.tenant_id is None

        session_with_tenant = UserSession(
            user_id="user-789",
            email="carol@example.com",
            display_name="Carol",
            tenant_id="tenant-xyz",
            session_id="sess-004",
            token_expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert session_with_tenant.tenant_id == "tenant-xyz"
