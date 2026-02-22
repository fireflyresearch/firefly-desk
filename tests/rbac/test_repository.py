# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for RoleRepository -- CRUD, permission resolution, and seeding."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.models.base import Base
from flydek.rbac.models import Role
from flydek.rbac.repository import RoleRepository


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


class TestRoleRepository:
    async def test_seed_builtin_roles_creates_three_roles(self, repo):
        """Seeding populates the three built-in roles."""
        await repo.seed_builtin_roles()
        roles = await repo.list_roles()
        assert len(roles) == 3
        names = {r.name for r in roles}
        assert names == {"admin", "operator", "viewer"}
        for r in roles:
            assert r.is_builtin is True

    async def test_seed_builtin_roles_is_idempotent(self, repo):
        """Running seed twice does not duplicate roles."""
        await repo.seed_builtin_roles()
        await repo.seed_builtin_roles()
        roles = await repo.list_roles()
        assert len(roles) == 3

    async def test_list_roles_returns_all(self, repo):
        """list_roles returns both built-in and custom roles."""
        await repo.seed_builtin_roles()
        custom = Role(
            id="role-custom",
            name="custom",
            display_name="Custom Role",
            permissions=["knowledge:read"],
        )
        await repo.create_role(custom)
        roles = await repo.list_roles()
        assert len(roles) == 4

    async def test_get_role_by_id(self, repo):
        """get_role returns a role by its ID."""
        await repo.seed_builtin_roles()
        role = await repo.get_role("role-admin")
        assert role is not None
        assert role.name == "admin"
        assert role.display_name == "Administrator"

    async def test_get_role_by_name(self, repo):
        """get_role_by_name returns a role by its unique name."""
        await repo.seed_builtin_roles()
        role = await repo.get_role_by_name("operator")
        assert role is not None
        assert role.id == "role-operator"
        assert "catalog:read" in role.permissions

    async def test_create_custom_role(self, repo):
        """Creating a custom role persists and returns it with timestamps."""
        custom = Role(
            id="role-analyst",
            name="analyst",
            display_name="Analyst",
            description="Data analysis access.",
            permissions=["knowledge:read", "exports:create", "exports:download"],
        )
        created = await repo.create_role(custom)
        assert created.id == "role-analyst"
        assert created.name == "analyst"
        assert created.is_builtin is False
        assert created.created_at is not None
        assert "exports:create" in created.permissions

    async def test_update_role_permissions(self, repo):
        """update_role modifies the specified fields."""
        custom = Role(
            id="role-editor",
            name="editor",
            display_name="Editor",
            permissions=["knowledge:read"],
        )
        await repo.create_role(custom)
        updated = await repo.update_role(
            "role-editor",
            permissions=["knowledge:read", "knowledge:write"],
        )
        assert updated is not None
        assert "knowledge:write" in updated.permissions

    async def test_delete_custom_role(self, repo):
        """Deleting a custom role removes it."""
        custom = Role(
            id="role-temp",
            name="temp",
            display_name="Temporary",
            permissions=[],
        )
        await repo.create_role(custom)
        deleted = await repo.delete_role("role-temp")
        assert deleted is True
        assert await repo.get_role("role-temp") is None

    async def test_delete_builtin_role_refused(self, repo):
        """Deleting a built-in role raises ValueError."""
        await repo.seed_builtin_roles()
        with pytest.raises(ValueError, match="Cannot delete built-in role"):
            await repo.delete_role("role-admin")

    async def test_get_permissions_for_roles_union(self, repo):
        """Permissions for multiple roles are unioned and deduplicated."""
        await repo.seed_builtin_roles()
        perms = await repo.get_permissions_for_roles(["operator", "viewer"])
        assert "knowledge:read" in perms
        assert "catalog:read" in perms
        assert "catalog:write" in perms
        assert "exports:create" in perms
        assert "chat:send" in perms
        # Viewer does not add anything beyond what operator has -- but union is correct
        assert len(perms) == len(set(perms))  # no duplicates

    async def test_get_permissions_for_roles_with_wildcard(self, repo):
        """If any role has wildcard, return ["*"]."""
        await repo.seed_builtin_roles()
        perms = await repo.get_permissions_for_roles(["admin", "viewer"])
        assert perms == ["*"]
