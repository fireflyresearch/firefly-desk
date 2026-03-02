# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the POST /api/catalog/import/curl endpoint."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession


# ---------------------------------------------------------------------------
# Fixtures (mirrors test_catalog_api.py pattern)
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics CatalogRepository."""
    return AsyncMock()


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked CatalogRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.catalog import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        from flydesk.api.deps import get_audit_logger

        app.dependency_overrides[get_audit_logger] = lambda: AsyncMock()

        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCurlImport:
    """Tests for POST /api/catalog/import/curl."""

    async def test_valid_curl_returns_200(self, admin_client):
        response = await admin_client.post(
            "/api/catalog/import/curl",
            json={"command": "curl -X POST https://api.example.com/users -H 'Content-Type: application/json' -d '{\"name\": \"Alice\"}'"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "POST"
        assert data["url"] == "https://api.example.com/users"
        assert data["headers"] == {"Content-Type": "application/json"}
        assert data["body"] == '{"name": "Alice"}'
        assert data["query_params"] == {}

    async def test_empty_command_returns_400(self, admin_client):
        response = await admin_client.post(
            "/api/catalog/import/curl",
            json={"command": ""},
        )
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    async def test_no_url_returns_400(self, admin_client):
        response = await admin_client.post(
            "/api/catalog/import/curl",
            json={"command": "curl -X GET"},
        )
        assert response.status_code == 400
        assert "no url" in response.json()["detail"].lower()
