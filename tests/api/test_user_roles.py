# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for user-role assignment API endpoints."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.conversation.models import Conversation
from flydesk.conversation.repository import ConversationRepository
from flydesk.models.base import Base
from flydesk.rbac.repository import RoleRepository
from flydesk.settings.repository import SettingsRepository


@pytest.fixture
async def client():
    """AsyncClient wired to in-memory SQLite with all needed dependency overrides."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDESK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydesk.api.roles import get_role_repo
        from flydesk.api.users import get_local_user_repo, get_session_factory, get_settings_repo
        from flydesk.auth.local_user_repository import LocalUserRepository
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        conversation_repo = ConversationRepository(session_factory)
        settings_repo = SettingsRepository(session_factory)
        role_repo = RoleRepository(session_factory)
        await role_repo.seed_builtin_roles()

        local_user_repo = LocalUserRepository(session_factory)

        app.dependency_overrides[get_session_factory] = lambda: session_factory
        app.dependency_overrides[get_settings_repo] = lambda: settings_repo
        app.dependency_overrides[get_role_repo] = lambda: role_repo
        app.dependency_overrides[get_local_user_repo] = lambda: local_user_repo

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, conversation_repo, role_repo

        await engine.dispose()


class TestGetUserRoles:
    async def test_get_roles_empty_for_unknown_user(self, client):
        """GET /api/admin/users/{user_id}/roles returns [] for unknown user."""
        ac, _, _ = client
        response = await ac.get("/api/admin/users/nonexistent/roles")
        assert response.status_code == 200
        assert response.json() == []

    async def test_get_roles_returns_assigned(self, client):
        """GET returns role IDs after they are assigned."""
        ac, _, _ = client

        # Get available roles to find an ID
        roles_resp = await ac.get("/api/admin/roles")
        roles = roles_resp.json()
        admin_role_id = next(r["id"] for r in roles if r["name"] == "admin")

        # Assign the role
        await ac.put(
            "/api/admin/users/user-x/roles",
            json={"role_ids": [admin_role_id]},
        )

        # Fetch and verify
        response = await ac.get("/api/admin/users/user-x/roles")
        assert response.status_code == 200
        assert admin_role_id in response.json()


class TestUpdateUserRoles:
    async def test_assign_roles(self, client):
        """PUT /api/admin/users/{user_id}/roles creates assignments."""
        ac, _, _ = client

        roles_resp = await ac.get("/api/admin/roles")
        roles = roles_resp.json()
        viewer_id = next(r["id"] for r in roles if r["name"] == "viewer")
        operator_id = next(r["id"] for r in roles if r["name"] == "operator")

        response = await ac.put(
            "/api/admin/users/user-a/roles",
            json={"role_ids": [viewer_id, operator_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert set(data) == {viewer_id, operator_id}

    async def test_replace_roles(self, client):
        """PUT replaces existing assignments entirely."""
        ac, _, _ = client

        roles_resp = await ac.get("/api/admin/roles")
        roles = roles_resp.json()
        admin_id = next(r["id"] for r in roles if r["name"] == "admin")
        viewer_id = next(r["id"] for r in roles if r["name"] == "viewer")

        # First assignment
        await ac.put(
            "/api/admin/users/user-b/roles",
            json={"role_ids": [admin_id, viewer_id]},
        )

        # Replace with only viewer
        response = await ac.put(
            "/api/admin/users/user-b/roles",
            json={"role_ids": [viewer_id]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data == [viewer_id]

    async def test_clear_roles(self, client):
        """PUT with empty role_ids removes all assignments."""
        ac, _, _ = client

        roles_resp = await ac.get("/api/admin/roles")
        roles = roles_resp.json()
        admin_id = next(r["id"] for r in roles if r["name"] == "admin")

        # Assign then clear
        await ac.put(
            "/api/admin/users/user-c/roles",
            json={"role_ids": [admin_id]},
        )
        response = await ac.put(
            "/api/admin/users/user-c/roles",
            json={"role_ids": []},
        )
        assert response.status_code == 200
        assert response.json() == []


class TestListUsersWithRoles:
    async def test_list_users_includes_role_assignments(self, client):
        """GET /api/admin/users includes assigned role IDs for each user."""
        ac, conversation_repo, _ = client

        # Create a conversation to discover the user
        await conversation_repo.create_conversation(
            Conversation(id="conv-1", user_id="user-role-test", title="Test")
        )

        # Get a role ID and assign it
        roles_resp = await ac.get("/api/admin/roles")
        roles = roles_resp.json()
        operator_id = next(r["id"] for r in roles if r["name"] == "operator")

        await ac.put(
            "/api/admin/users/user-role-test/roles",
            json={"role_ids": [operator_id]},
        )

        # List users and verify the role appears
        response = await ac.get("/api/admin/users")
        assert response.status_code == 200
        data = response.json()
        user = next(u for u in data if u["user_id"] == "user-role-test")
        assert operator_id in user["roles"]
