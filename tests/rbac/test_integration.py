# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Integration tests for the RBAC system.

These tests exercise the full flow: role creation in the repository,
permission resolution, and guard enforcement -- all wired together
against an in-memory SQLite database.  No mocks are used for the
domain layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.auth.models import UserSession
from flydek.models.base import Base
from flydek.rbac.guards import require_permission
from flydek.rbac.models import Role
from flydek.rbac.repository import RoleRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(*, user_session: UserSession | None = None) -> MagicMock:
    """Build a mock Starlette ``Request`` carrying an optional ``user_session``."""
    request = MagicMock()
    request.state = MagicMock()
    if user_session is not None:
        request.state.user_session = user_session
    else:
        request.state.user_session = None
    return request


def _make_user(permissions: list[str], roles: list[str] | None = None) -> UserSession:
    return UserSession(
        user_id="u-integ",
        email="integ@example.com",
        display_name="Integration User",
        roles=roles or [],
        permissions=permissions,
        session_id="sess-integ",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _extract_guard(permission: str):
    """Unwrap the inner async function from ``require_permission``."""
    dep = require_permission(permission)
    return dep.dependency


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return RoleRepository(session_factory)


# ---------------------------------------------------------------------------
# Integration Tests
# ---------------------------------------------------------------------------


class TestRBACIntegration:
    """End-to-end RBAC: role creation -> permission resolution -> guard enforcement."""

    async def test_custom_role_grants_access_to_permitted_endpoint(self, repo):
        """Create a custom role, resolve its permissions, and verify the guard allows access."""
        # 1. Create a custom role with specific permissions
        custom = Role(
            id="role-analyst",
            name="analyst",
            display_name="Analyst",
            description="Data analysis access only.",
            permissions=["knowledge:read", "exports:create", "exports:download"],
        )
        created = await repo.create_role(custom)
        assert created.id == "role-analyst"
        assert created.is_builtin is False

        # 2. Resolve permissions for that role
        perms = await repo.get_permissions_for_roles(["analyst"])
        assert "knowledge:read" in perms
        assert "exports:create" in perms
        assert "exports:download" in perms

        # 3. Build a user with those resolved permissions and verify guard passes
        user = _make_user(permissions=perms, roles=["analyst"])
        request = _make_request(user_session=user)

        guard = _extract_guard("knowledge:read")
        await guard(request)  # should not raise

        guard2 = _extract_guard("exports:create")
        await guard2(request)  # should not raise

    async def test_custom_role_denies_access_to_non_permitted_endpoint(self, repo):
        """A custom role without a permission should be denied (403)."""
        custom = Role(
            id="role-readonly",
            name="readonly",
            display_name="Read Only",
            permissions=["knowledge:read", "catalog:read"],
        )
        await repo.create_role(custom)

        perms = await repo.get_permissions_for_roles(["readonly"])
        user = _make_user(permissions=perms, roles=["readonly"])
        request = _make_request(user_session=user)

        # Should be denied access to admin:settings
        guard = _extract_guard("admin:settings")
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403
        assert "admin:settings" in exc_info.value.detail

    async def test_admin_wildcard_permits_everything(self, repo):
        """The admin role with wildcard '*' should pass every guard."""
        await repo.seed_builtin_roles()

        perms = await repo.get_permissions_for_roles(["admin"])
        assert perms == ["*"]

        user = _make_user(permissions=perms, roles=["admin"])
        request = _make_request(user_session=user)

        # Test against several different permission guards
        for perm in [
            "knowledge:read",
            "admin:settings",
            "catalog:delete",
            "credentials:write",
            "exports:templates",
        ]:
            guard = _extract_guard(perm)
            await guard(request)  # should never raise

    async def test_role_deletion_removes_permissions(self, repo):
        """After deleting a role, resolving its permissions yields nothing."""
        custom = Role(
            id="role-temp",
            name="temp",
            display_name="Temporary",
            permissions=["knowledge:read", "audit:read"],
        )
        await repo.create_role(custom)

        # Verify permissions resolve before deletion
        perms_before = await repo.get_permissions_for_roles(["temp"])
        assert "knowledge:read" in perms_before
        assert "audit:read" in perms_before

        # Delete the role
        deleted = await repo.delete_role("role-temp")
        assert deleted is True

        # Permissions should now be empty
        perms_after = await repo.get_permissions_for_roles(["temp"])
        assert perms_after == []

        # A user with the now-deleted role's permissions (empty) gets denied
        user = _make_user(permissions=perms_after, roles=["temp"])
        request = _make_request(user_session=user)
        guard = _extract_guard("knowledge:read")
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403

    async def test_multiple_roles_union_permissions(self, repo):
        """A user with multiple roles gets the union of all permissions."""
        await repo.seed_builtin_roles()

        # Create a custom role with a permission that operator does not have
        custom = Role(
            id="role-credentials-viewer",
            name="credentials-viewer",
            display_name="Credentials Viewer",
            permissions=["credentials:read"],
        )
        await repo.create_role(custom)

        # Resolve permissions for operator + credentials-viewer
        perms = await repo.get_permissions_for_roles(["operator", "credentials-viewer"])
        assert "knowledge:read" in perms  # from operator
        assert "catalog:write" in perms  # from operator
        assert "credentials:read" in perms  # from custom role
        assert len(perms) == len(set(perms))  # no duplicates

        # Build a user and verify access to both role domains
        user = _make_user(permissions=perms, roles=["operator", "credentials-viewer"])
        request = _make_request(user_session=user)

        for perm in ["knowledge:read", "catalog:write", "credentials:read"]:
            guard = _extract_guard(perm)
            await guard(request)  # should not raise

        # But should still be denied admin-only permissions
        guard = _extract_guard("admin:users")
        with pytest.raises(HTTPException) as exc_info:
            await guard(request)
        assert exc_info.value.status_code == 403

    async def test_updated_role_permissions_take_effect(self, repo):
        """Updating a role's permissions changes what the guard allows."""
        custom = Role(
            id="role-editor",
            name="editor",
            display_name="Editor",
            permissions=["knowledge:read"],
        )
        await repo.create_role(custom)

        # Before update: can read knowledge, cannot write
        perms = await repo.get_permissions_for_roles(["editor"])
        user = _make_user(permissions=perms, roles=["editor"])
        request = _make_request(user_session=user)

        guard_read = _extract_guard("knowledge:read")
        await guard_read(request)  # passes

        guard_write = _extract_guard("knowledge:write")
        with pytest.raises(HTTPException):
            await guard_write(request)  # denied

        # Update the role to add write permission
        updated = await repo.update_role(
            "role-editor",
            permissions=["knowledge:read", "knowledge:write"],
        )
        assert updated is not None
        assert "knowledge:write" in updated.permissions

        # After update: re-resolve permissions
        perms = await repo.get_permissions_for_roles(["editor"])
        assert "knowledge:write" in perms

        user = _make_user(permissions=perms, roles=["editor"])
        request = _make_request(user_session=user)
        await guard_write(request)  # now passes
