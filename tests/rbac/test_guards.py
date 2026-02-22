# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for RBAC permission guards."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from flydek.auth.models import UserSession
from flydek.rbac.guards import require_permission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(*, user_session: UserSession | None = None) -> MagicMock:
    """Build a mock Starlette ``Request`` with an optional ``user_session``."""
    request = MagicMock()
    request.state = MagicMock()
    if user_session is not None:
        request.state.user_session = user_session
    else:
        # Simulate missing attribute
        del request.state.user_session
        request.state.user_session = None
    return request


def _make_user(
    *,
    permissions: list[str] | None = None,
    roles: list[str] | None = None,
) -> UserSession:
    return UserSession(
        user_id="u-1",
        email="test@example.com",
        display_name="Test User",
        roles=roles or [],
        permissions=permissions or [],
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _extract_guard(permission: str):
    """Extract the raw async guard function from ``require_permission``.

    ``require_permission`` returns a ``Depends(...)`` object.  The inner
    function is stored in ``dependency``.
    """
    dep = require_permission(permission)
    return dep.dependency


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRequirePermission:
    """Unit tests for the ``require_permission`` guard."""

    @pytest.mark.anyio
    async def test_wildcard_permission_allows_access(self):
        """A user with the wildcard ``*`` permission passes any guard."""
        guard = _extract_guard("knowledge:read")
        request = _make_request(user_session=_make_user(permissions=["*"]))
        # Should not raise
        await guard(request)

    @pytest.mark.anyio
    async def test_matching_permission_allows_access(self):
        """A user with the exact required permission passes the guard."""
        guard = _extract_guard("catalog:write")
        request = _make_request(
            user_session=_make_user(permissions=["catalog:read", "catalog:write"])
        )
        await guard(request)

    @pytest.mark.anyio
    async def test_missing_permission_denies_access(self):
        """A user without the required permission gets 403."""
        guard = _extract_guard("admin:settings")
        request = _make_request(
            user_session=_make_user(permissions=["catalog:read"])
        )
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403
        assert "admin:settings" in exc_info.value.detail

    @pytest.mark.anyio
    async def test_no_user_session_returns_401(self):
        """A request with no user_session gets 401."""
        guard = _extract_guard("knowledge:read")
        request = _make_request(user_session=None)
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 401
        assert "authentication" in exc_info.value.detail.lower()

    @pytest.mark.anyio
    async def test_empty_permissions_denies_access(self):
        """A user with an empty permission list gets 403."""
        guard = _extract_guard("exports:create")
        request = _make_request(user_session=_make_user(permissions=[]))
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.anyio
    async def test_multiple_permissions_on_user(self):
        """A user with many permissions passes when the required one is present."""
        guard = _extract_guard("audit:read")
        request = _make_request(
            user_session=_make_user(
                permissions=[
                    "knowledge:read",
                    "catalog:read",
                    "audit:read",
                    "exports:create",
                ]
            )
        )
        await guard(request)

    @pytest.mark.anyio
    async def test_similar_permission_does_not_match(self):
        """A permission like ``knowledge:write`` does NOT satisfy ``knowledge:read``."""
        guard = _extract_guard("knowledge:read")
        request = _make_request(
            user_session=_make_user(permissions=["knowledge:write"])
        )
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403

    @pytest.mark.anyio
    async def test_wildcard_among_other_permissions(self):
        """Wildcard wins even if mixed with other permissions."""
        guard = _extract_guard("admin:llm")
        request = _make_request(
            user_session=_make_user(
                permissions=["knowledge:read", "*", "catalog:write"]
            )
        )
        await guard(request)
