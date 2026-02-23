# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for resource-level access scopes (AccessScopes model, merge logic, and repository)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.rbac.models import AccessScopes, Role
from flydesk.rbac.permissions import is_admin, merge_access_scopes
from flydesk.rbac.repository import RoleRepository


# ---------------------------------------------------------------------------
# AccessScopes model tests
# ---------------------------------------------------------------------------


class TestAccessScopes:
    """Unit tests for the AccessScopes Pydantic model."""

    def test_empty_scopes_allow_everything(self):
        """Empty lists (default) mean unrestricted access."""
        scopes = AccessScopes()
        assert scopes.can_access_system("any-system") is True
        assert scopes.can_access_knowledge(["hr", "finance"]) is True
        assert scopes.can_access_skill(["billing"]) is True

    def test_system_scope_allows_listed_system(self):
        scopes = AccessScopes(systems=["sys-a", "sys-b"])
        assert scopes.can_access_system("sys-a") is True
        assert scopes.can_access_system("sys-b") is True
        assert scopes.can_access_system("sys-c") is False

    def test_knowledge_scope_allows_overlapping_tags(self):
        scopes = AccessScopes(knowledge_tags=["hr", "onboarding"])
        assert scopes.can_access_knowledge(["hr"]) is True
        assert scopes.can_access_knowledge(["hr", "finance"]) is True
        assert scopes.can_access_knowledge(["finance"]) is False

    def test_knowledge_scope_empty_doc_tags_denied(self):
        """A document with no tags is denied when knowledge_tags are set."""
        scopes = AccessScopes(knowledge_tags=["hr"])
        assert scopes.can_access_knowledge([]) is False

    def test_skill_scope_allows_overlapping_tags(self):
        scopes = AccessScopes(skill_tags=["billing", "crm"])
        assert scopes.can_access_skill(["billing"]) is True
        assert scopes.can_access_skill(["analytics"]) is False
        assert scopes.can_access_skill(["crm", "analytics"]) is True

    def test_skill_scope_empty_skill_tags_denied(self):
        scopes = AccessScopes(skill_tags=["billing"])
        assert scopes.can_access_skill([]) is False

    def test_serialization_roundtrip(self):
        scopes = AccessScopes(systems=["s1"], knowledge_tags=["hr"], skill_tags=["x"])
        data = scopes.model_dump()
        restored = AccessScopes(**data)
        assert restored == scopes


# ---------------------------------------------------------------------------
# merge_access_scopes tests
# ---------------------------------------------------------------------------


class TestMergeAccessScopes:
    def test_empty_input_returns_unrestricted(self):
        merged = merge_access_scopes([])
        assert merged == AccessScopes()

    def test_single_scope_returned_as_is(self):
        s = AccessScopes(systems=["sys-a"], knowledge_tags=["hr"])
        merged = merge_access_scopes([s])
        assert merged.systems == ["sys-a"]
        assert merged.knowledge_tags == ["hr"]

    def test_union_of_restricted_scopes(self):
        s1 = AccessScopes(systems=["sys-a"], knowledge_tags=["hr"])
        s2 = AccessScopes(systems=["sys-b"], knowledge_tags=["finance"])
        merged = merge_access_scopes([s1, s2])
        assert sorted(merged.systems) == ["sys-a", "sys-b"]
        assert sorted(merged.knowledge_tags) == ["finance", "hr"]

    def test_unrestricted_role_dominates(self):
        """If any role has empty (unrestricted) scopes, merged result is also unrestricted."""
        s1 = AccessScopes(systems=["sys-a"], knowledge_tags=["hr"])
        s2 = AccessScopes()  # unrestricted
        merged = merge_access_scopes([s1, s2])
        assert merged.systems == []
        assert merged.knowledge_tags == []
        assert merged.skill_tags == []

    def test_partial_unrestricted(self):
        """One dimension unrestricted, another restricted."""
        s1 = AccessScopes(systems=["sys-a"], knowledge_tags=[])  # knowledge unrestricted
        s2 = AccessScopes(systems=["sys-b"], knowledge_tags=["hr"])
        merged = merge_access_scopes([s1, s2])
        assert sorted(merged.systems) == ["sys-a", "sys-b"]
        assert merged.knowledge_tags == []  # unrestricted wins

    def test_deduplication(self):
        s1 = AccessScopes(systems=["sys-a", "sys-b"])
        s2 = AccessScopes(systems=["sys-b", "sys-c"])
        merged = merge_access_scopes([s1, s2])
        assert sorted(merged.systems) == ["sys-a", "sys-b", "sys-c"]


# ---------------------------------------------------------------------------
# is_admin helper tests
# ---------------------------------------------------------------------------


class TestIsAdmin:
    def test_wildcard_is_admin(self):
        assert is_admin(["*"]) is True

    def test_wildcard_among_others_is_admin(self):
        assert is_admin(["knowledge:read", "*"]) is True

    def test_no_wildcard_is_not_admin(self):
        assert is_admin(["knowledge:read", "catalog:read"]) is False

    def test_empty_is_not_admin(self):
        assert is_admin([]) is False


# ---------------------------------------------------------------------------
# Role model with access_scopes
# ---------------------------------------------------------------------------


class TestRoleModel:
    def test_role_default_access_scopes(self):
        role = Role(id="r1", name="test", display_name="Test")
        assert role.access_scopes == AccessScopes()

    def test_role_with_access_scopes(self):
        scopes = AccessScopes(systems=["sys-a"])
        role = Role(id="r1", name="test", display_name="Test", access_scopes=scopes)
        assert role.access_scopes.systems == ["sys-a"]


# ---------------------------------------------------------------------------
# Repository tests for access scopes
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


class TestRoleRepositoryAccessScopes:
    async def test_create_role_with_scopes(self, repo):
        """Creating a role with access scopes persists and returns them."""
        scopes = AccessScopes(systems=["sys-x"], knowledge_tags=["hr"])
        role = Role(
            id="role-scoped",
            name="scoped",
            display_name="Scoped Role",
            permissions=["knowledge:read"],
            access_scopes=scopes,
        )
        created = await repo.create_role(role)
        assert created.access_scopes.systems == ["sys-x"]
        assert created.access_scopes.knowledge_tags == ["hr"]

    async def test_create_role_without_scopes_defaults(self, repo):
        """Roles without explicit scopes get empty (unrestricted) defaults."""
        role = Role(
            id="role-noscope",
            name="noscope",
            display_name="No Scope",
            permissions=["knowledge:read"],
        )
        created = await repo.create_role(role)
        assert created.access_scopes == AccessScopes()

    async def test_update_role_access_scopes(self, repo):
        """Updating access_scopes on a role persists the change."""
        role = Role(
            id="role-upd",
            name="updatable",
            display_name="Updatable",
            permissions=["knowledge:read"],
        )
        await repo.create_role(role)
        updated = await repo.update_role(
            "role-upd",
            access_scopes={"systems": ["sys-new"], "knowledge_tags": ["finance"]},
        )
        assert updated is not None
        assert updated.access_scopes.systems == ["sys-new"]
        assert updated.access_scopes.knowledge_tags == ["finance"]

    async def test_get_access_scopes_for_roles_single(self, repo):
        """get_access_scopes_for_roles returns scopes for a single role."""
        scopes = AccessScopes(systems=["sys-a"], knowledge_tags=["hr"])
        role = Role(
            id="role-s1",
            name="scoped1",
            display_name="Scoped 1",
            permissions=["knowledge:read"],
            access_scopes=scopes,
        )
        await repo.create_role(role)
        result = await repo.get_access_scopes_for_roles(["scoped1"])
        assert result.systems == ["sys-a"]
        assert result.knowledge_tags == ["hr"]

    async def test_get_access_scopes_for_roles_merge(self, repo):
        """Scopes from multiple roles are merged (union)."""
        await repo.create_role(Role(
            id="role-m1",
            name="merge1",
            display_name="Merge 1",
            permissions=["knowledge:read"],
            access_scopes=AccessScopes(systems=["sys-a"], knowledge_tags=["hr"]),
        ))
        await repo.create_role(Role(
            id="role-m2",
            name="merge2",
            display_name="Merge 2",
            permissions=["knowledge:read"],
            access_scopes=AccessScopes(systems=["sys-b"], knowledge_tags=["finance"]),
        ))
        result = await repo.get_access_scopes_for_roles(["merge1", "merge2"])
        assert sorted(result.systems) == ["sys-a", "sys-b"]
        assert sorted(result.knowledge_tags) == ["finance", "hr"]

    async def test_get_access_scopes_for_roles_no_match(self, repo):
        """When no roles match, returns unrestricted scopes."""
        result = await repo.get_access_scopes_for_roles(["nonexistent"])
        assert result == AccessScopes()

    async def test_builtin_roles_have_empty_scopes(self, repo):
        """Built-in roles default to empty (unrestricted) access scopes."""
        await repo.seed_builtin_roles()
        admin = await repo.get_role("role-admin")
        assert admin is not None
        assert admin.access_scopes == AccessScopes()
