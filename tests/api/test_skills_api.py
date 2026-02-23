# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Skills admin REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.models.base import Base
from flydesk.skills.repository import SkillRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_session(*, permissions: list[str]) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="test-user-1",
        email="test@example.com",
        display_name="Test User",
        roles=["admin"] if "*" in permissions else ["viewer"],
        permissions=permissions,
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def admin_client():
    """AsyncClient backed by a real SQLite database with admin permissions."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.skills import get_skill_repo
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        skill_repo = SkillRepository(session_factory)
        app.dependency_overrides[get_skill_repo] = lambda: skill_repo

        admin_session = _make_user_session(permissions=["*"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


@pytest.fixture
async def non_admin_client():
    """AsyncClient with a non-admin user session (no admin:settings permission)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.skills import get_skill_repo
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        skill_repo = SkillRepository(session_factory)
        app.dependency_overrides[get_skill_repo] = lambda: skill_repo

        viewer_session = _make_user_session(permissions=["knowledge:read"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


# ---------------------------------------------------------------------------
# Tests -- CRUD
# ---------------------------------------------------------------------------


class TestListSkills:
    async def test_list_skills_empty(self, admin_client):
        """GET /api/admin/skills returns empty list initially."""
        response = await admin_client.get("/api/admin/skills")
        assert response.status_code == 200
        assert response.json() == []


class TestCreateSkill:
    async def test_create_skill(self, admin_client):
        """POST /api/admin/skills creates a skill."""
        response = await admin_client.post(
            "/api/admin/skills",
            json={
                "name": "summarize-ticket",
                "description": "Summarizes support tickets",
                "content": "You are a summarization assistant...",
                "tags": ["support", "triage"],
                "active": True,
            },
        )
        assert response.status_code == 201
        skill = response.json()
        assert skill["name"] == "summarize-ticket"
        assert skill["description"] == "Summarizes support tickets"
        assert skill["content"] == "You are a summarization assistant..."
        assert skill["tags"] == ["support", "triage"]
        assert skill["active"] is True
        assert skill["id"].startswith("skill-")


class TestGetSkill:
    async def test_get_skill_by_id(self, admin_client):
        """GET /api/admin/skills/{id} returns skill details."""
        create_resp = await admin_client.post(
            "/api/admin/skills",
            json={"name": "test-skill", "description": "A test skill"},
        )
        skill_id = create_resp.json()["id"]

        response = await admin_client.get(f"/api/admin/skills/{skill_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "test-skill"

    async def test_get_skill_not_found(self, admin_client):
        """GET /api/admin/skills/{id} returns 404 for unknown skill."""
        response = await admin_client.get("/api/admin/skills/nonexistent")
        assert response.status_code == 404


class TestUpdateSkill:
    async def test_update_skill(self, admin_client):
        """PUT /api/admin/skills/{id} updates skill fields."""
        create_resp = await admin_client.post(
            "/api/admin/skills",
            json={"name": "updatable", "description": "old"},
        )
        skill_id = create_resp.json()["id"]

        update_resp = await admin_client.put(
            f"/api/admin/skills/{skill_id}",
            json={"description": "new description", "active": False},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["description"] == "new description"
        assert updated["active"] is False

    async def test_update_skill_not_found(self, admin_client):
        """PUT /api/admin/skills/{id} returns 404 for unknown skill."""
        response = await admin_client.put(
            "/api/admin/skills/nonexistent",
            json={"description": "foo"},
        )
        assert response.status_code == 404

    async def test_update_skill_no_fields(self, admin_client):
        """PUT /api/admin/skills/{id} returns 400 when no fields provided."""
        create_resp = await admin_client.post(
            "/api/admin/skills",
            json={"name": "no-update"},
        )
        skill_id = create_resp.json()["id"]

        response = await admin_client.put(
            f"/api/admin/skills/{skill_id}",
            json={},
        )
        assert response.status_code == 400


class TestDeleteSkill:
    async def test_delete_skill(self, admin_client):
        """DELETE /api/admin/skills/{id} deletes a skill."""
        create_resp = await admin_client.post(
            "/api/admin/skills",
            json={"name": "deletable"},
        )
        skill_id = create_resp.json()["id"]

        delete_resp = await admin_client.delete(f"/api/admin/skills/{skill_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await admin_client.get(f"/api/admin/skills/{skill_id}")
        assert get_resp.status_code == 404

    async def test_delete_skill_not_found(self, admin_client):
        """DELETE /api/admin/skills/{id} returns 404 for unknown skill."""
        response = await admin_client.delete("/api/admin/skills/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Permission guard enforcement
# ---------------------------------------------------------------------------


class TestPermissionGuard:
    async def test_non_admin_gets_403(self, non_admin_client):
        """Non-admin users receive 403 on admin skill endpoints."""
        response = await non_admin_client.get("/api/admin/skills")
        assert response.status_code == 403

    async def test_non_admin_cannot_create_skill(self, non_admin_client):
        """Non-admin users cannot create skills."""
        response = await non_admin_client.post(
            "/api/admin/skills",
            json={"name": "hacker-skill"},
        )
        assert response.status_code == 403
