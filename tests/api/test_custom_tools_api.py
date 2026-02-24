# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Custom Tools admin REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.auth.models import UserSession
from flydesk.models.base import Base
from flydesk.tools.custom_models import CustomTool, ToolSource
from flydesk.tools.custom_repository import CustomToolRepository
from flydesk.tools.sandbox import SandboxExecutor, SandboxResult


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
        from flydesk.api.custom_tools import get_custom_tool_repo, get_sandbox_executor
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        custom_tool_repo = CustomToolRepository(session_factory)
        sandbox_executor = SandboxExecutor()
        app.dependency_overrides[get_custom_tool_repo] = lambda: custom_tool_repo
        app.dependency_overrides[get_sandbox_executor] = lambda: sandbox_executor

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
async def admin_client_mock_sandbox():
    """AsyncClient with a mock SandboxExecutor for test-execute tests."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.custom_tools import get_custom_tool_repo, get_sandbox_executor
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        custom_tool_repo = CustomToolRepository(session_factory)

        class MockSandboxExecutor:
            """Controllable sandbox for test assertions."""

            def __init__(self):
                self.next_result: SandboxResult = SandboxResult(
                    success=True, data={"result": "ok"}
                )

            async def execute(self, code, params, *, timeout=30):
                return self.next_result

        mock_sandbox = MockSandboxExecutor()

        app.dependency_overrides[get_custom_tool_repo] = lambda: custom_tool_repo
        app.dependency_overrides[get_sandbox_executor] = lambda: mock_sandbox

        admin_session = _make_user_session(permissions=["*"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, mock_sandbox

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
        from flydesk.api.custom_tools import get_custom_tool_repo, get_sandbox_executor
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        custom_tool_repo = CustomToolRepository(session_factory)
        sandbox_executor = SandboxExecutor()
        app.dependency_overrides[get_custom_tool_repo] = lambda: custom_tool_repo
        app.dependency_overrides[get_sandbox_executor] = lambda: sandbox_executor

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


class TestListCustomTools:
    async def test_list_empty(self, admin_client):
        """GET /api/admin/custom-tools returns empty list initially."""
        response = await admin_client.get("/api/admin/custom-tools")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_with_source_filter(self, admin_client):
        """GET /api/admin/custom-tools?source=manual filters by source."""
        # Create a manual tool
        await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "manual-tool", "source": "manual"},
        )
        # Create a builtin tool
        await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "builtin-tool", "source": "builtin"},
        )

        # Filter by manual
        response = await admin_client.get("/api/admin/custom-tools?source=manual")
        assert response.status_code == 200
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["name"] == "manual-tool"

        # Filter by builtin
        response = await admin_client.get("/api/admin/custom-tools?source=builtin")
        assert response.status_code == 200
        tools = response.json()
        assert len(tools) == 1
        assert tools[0]["name"] == "builtin-tool"


class TestCreateCustomTool:
    async def test_create_tool(self, admin_client):
        """POST /api/admin/custom-tools creates a custom tool."""
        response = await admin_client.post(
            "/api/admin/custom-tools",
            json={
                "name": "email-parser",
                "description": "Parses email headers",
                "python_code": "import json, sys; print(json.dumps({'parsed': True}))",
                "parameters": {"raw_email": {"type": "str", "description": "Raw email text"}},
                "output_schema": {"parsed": {"type": "bool"}},
                "active": True,
                "timeout_seconds": 15,
                "max_memory_mb": 128,
            },
        )
        assert response.status_code == 201
        tool = response.json()
        assert tool["name"] == "email-parser"
        assert tool["description"] == "Parses email headers"
        assert tool["python_code"] == "import json, sys; print(json.dumps({'parsed': True}))"
        assert tool["parameters"] == {"raw_email": {"type": "str", "description": "Raw email text"}}
        assert tool["active"] is True
        assert tool["source"] == "manual"
        assert tool["timeout_seconds"] == 15
        assert tool["max_memory_mb"] == 128
        assert tool["id"].startswith("ctool-")

    async def test_create_tool_defaults(self, admin_client):
        """POST /api/admin/custom-tools uses sensible defaults."""
        response = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "minimal-tool"},
        )
        assert response.status_code == 201
        tool = response.json()
        assert tool["name"] == "minimal-tool"
        assert tool["description"] == ""
        assert tool["python_code"] == ""
        assert tool["active"] is True
        assert tool["source"] == "manual"
        assert tool["timeout_seconds"] == 30
        assert tool["max_memory_mb"] == 256

    async def test_create_tool_missing_name(self, admin_client):
        """POST /api/admin/custom-tools returns 422 when name is missing."""
        response = await admin_client.post(
            "/api/admin/custom-tools",
            json={"description": "No name provided"},
        )
        assert response.status_code == 422


class TestGetCustomTool:
    async def test_get_tool_by_id(self, admin_client):
        """GET /api/admin/custom-tools/{id} returns tool details."""
        create_resp = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "test-tool", "description": "A test tool"},
        )
        tool_id = create_resp.json()["id"]

        response = await admin_client.get(f"/api/admin/custom-tools/{tool_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "test-tool"

    async def test_get_tool_not_found(self, admin_client):
        """GET /api/admin/custom-tools/{id} returns 404 for unknown tool."""
        response = await admin_client.get("/api/admin/custom-tools/nonexistent")
        assert response.status_code == 404


class TestUpdateCustomTool:
    async def test_update_tool(self, admin_client):
        """PUT /api/admin/custom-tools/{id} updates tool fields."""
        create_resp = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "updatable", "description": "old"},
        )
        tool_id = create_resp.json()["id"]

        update_resp = await admin_client.put(
            f"/api/admin/custom-tools/{tool_id}",
            json={"description": "new description", "active": False},
        )
        assert update_resp.status_code == 200
        updated = update_resp.json()
        assert updated["description"] == "new description"
        assert updated["active"] is False

    async def test_update_tool_not_found(self, admin_client):
        """PUT /api/admin/custom-tools/{id} returns 404 for unknown tool."""
        response = await admin_client.put(
            "/api/admin/custom-tools/nonexistent",
            json={"description": "foo"},
        )
        assert response.status_code == 404

    async def test_update_tool_no_fields(self, admin_client):
        """PUT /api/admin/custom-tools/{id} returns 400 when no fields provided."""
        create_resp = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "no-update"},
        )
        tool_id = create_resp.json()["id"]

        response = await admin_client.put(
            f"/api/admin/custom-tools/{tool_id}",
            json={},
        )
        assert response.status_code == 400


class TestDeleteCustomTool:
    async def test_delete_tool(self, admin_client):
        """DELETE /api/admin/custom-tools/{id} deletes a tool."""
        create_resp = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "deletable"},
        )
        tool_id = create_resp.json()["id"]

        delete_resp = await admin_client.delete(f"/api/admin/custom-tools/{tool_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await admin_client.get(f"/api/admin/custom-tools/{tool_id}")
        assert get_resp.status_code == 404

    async def test_delete_tool_not_found(self, admin_client):
        """DELETE /api/admin/custom-tools/{id} returns 404 for unknown tool."""
        response = await admin_client.delete("/api/admin/custom-tools/nonexistent")
        assert response.status_code == 404

    async def test_delete_builtin_tool_rejected(self, admin_client):
        """DELETE /api/admin/custom-tools/{id} returns 403 for builtin tools."""
        create_resp = await admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "builtin-protected", "source": "builtin"},
        )
        tool_id = create_resp.json()["id"]

        response = await admin_client.delete(f"/api/admin/custom-tools/{tool_id}")
        assert response.status_code == 403
        assert "Built-in" in response.json()["detail"]


class TestTestExecute:
    async def test_execute_success(self, admin_client_mock_sandbox):
        """POST /api/admin/custom-tools/{id}/test returns sandbox result on success."""
        client, mock_sandbox = admin_client_mock_sandbox
        mock_sandbox.next_result = SandboxResult(
            success=True, data={"answer": 42},
        )

        create_resp = await client.post(
            "/api/admin/custom-tools",
            json={
                "name": "calculator",
                "python_code": "import json, sys; print(json.dumps({'answer': 42}))",
            },
        )
        tool_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/admin/custom-tools/{tool_id}/test",
            json={"params": {"x": 1, "y": 2}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == {"answer": 42}
        assert body["error"] is None

    async def test_execute_failure(self, admin_client_mock_sandbox):
        """POST /api/admin/custom-tools/{id}/test returns error on sandbox failure."""
        client, mock_sandbox = admin_client_mock_sandbox
        mock_sandbox.next_result = SandboxResult(
            success=False, error="SyntaxError: invalid syntax",
        )

        create_resp = await client.post(
            "/api/admin/custom-tools",
            json={"name": "broken-tool", "python_code": "invalid code("},
        )
        tool_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/admin/custom-tools/{tool_id}/test",
            json={"params": {}},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert "SyntaxError" in body["error"]
        assert body["data"] is None

    async def test_execute_tool_not_found(self, admin_client_mock_sandbox):
        """POST /api/admin/custom-tools/{id}/test returns 404 for unknown tool."""
        client, _ = admin_client_mock_sandbox
        response = await client.post(
            "/api/admin/custom-tools/nonexistent/test",
            json={"params": {}},
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests -- Permission guard enforcement
# ---------------------------------------------------------------------------


class TestPermissionGuard:
    async def test_non_admin_gets_403(self, non_admin_client):
        """Non-admin users receive 403 on admin custom-tools endpoints."""
        response = await non_admin_client.get("/api/admin/custom-tools")
        assert response.status_code == 403

    async def test_non_admin_cannot_create_tool(self, non_admin_client):
        """Non-admin users cannot create custom tools."""
        response = await non_admin_client.post(
            "/api/admin/custom-tools",
            json={"name": "hacker-tool"},
        )
        assert response.status_code == 403
