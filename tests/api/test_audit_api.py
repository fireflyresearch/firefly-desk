# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Audit Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.auth.models import UserSession


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
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


def _sample_event() -> AuditEvent:
    return AuditEvent(
        event_type=AuditEventType.TOOL_CALL,
        user_id="user-1",
        conversation_id="conv-1",
        system_id="sys-1",
        endpoint_id="ep-1",
        action="list_users",
        detail={"args": {"page": 1}},
        risk_level="read",
    )


@pytest.fixture
def mock_audit_logger():
    """Return an AsyncMock that mimics AuditLogger."""
    logger = AsyncMock()
    logger.query = AsyncMock(return_value=[])
    return logger


@pytest.fixture
async def admin_client(mock_audit_logger):
    """AsyncClient with an admin user session and mocked AuditLogger."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.audit import get_audit_logger
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger

        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def non_admin_client(mock_audit_logger):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.audit import get_audit_logger
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger

        viewer_session = _make_user_session(roles=["viewer"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Query Audit Events
# ---------------------------------------------------------------------------


class TestQueryEvents:
    async def test_query_events_empty(self, admin_client, mock_audit_logger):
        mock_audit_logger.query.return_value = []
        response = await admin_client.get("/api/audit/events")
        assert response.status_code == 200
        assert response.json() == []

    async def test_query_events_returns_items(self, admin_client, mock_audit_logger):
        mock_audit_logger.query.return_value = [_sample_event()]
        response = await admin_client.get("/api/audit/events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "tool_call"
        assert data[0]["action"] == "list_users"

    async def test_query_events_with_user_id_filter(
        self, admin_client, mock_audit_logger
    ):
        mock_audit_logger.query.return_value = [_sample_event()]
        response = await admin_client.get("/api/audit/events?user_id=user-1")
        assert response.status_code == 200
        mock_audit_logger.query.assert_awaited_once_with(
            user_id="user-1",
            event_type=None,
            risk_level=None,
            date_from=None,
            date_to=None,
            conversation_id=None,
            offset=0,
            limit=50,
        )

    async def test_query_events_with_event_type_filter(
        self, admin_client, mock_audit_logger
    ):
        mock_audit_logger.query.return_value = []
        response = await admin_client.get("/api/audit/events?event_type=tool_call")
        assert response.status_code == 200
        mock_audit_logger.query.assert_awaited_once_with(
            user_id=None,
            event_type="tool_call",
            risk_level=None,
            date_from=None,
            date_to=None,
            conversation_id=None,
            offset=0,
            limit=50,
        )

    async def test_query_events_with_limit(self, admin_client, mock_audit_logger):
        mock_audit_logger.query.return_value = []
        response = await admin_client.get("/api/audit/events?limit=10")
        assert response.status_code == 200
        mock_audit_logger.query.assert_awaited_once_with(
            user_id=None,
            event_type=None,
            risk_level=None,
            date_from=None,
            date_to=None,
            conversation_id=None,
            offset=0,
            limit=10,
        )

    async def test_query_events_with_all_filters(
        self, admin_client, mock_audit_logger
    ):
        mock_audit_logger.query.return_value = []
        response = await admin_client.get(
            "/api/audit/events?user_id=user-1&event_type=tool_call&limit=25"
        )
        assert response.status_code == 200
        mock_audit_logger.query.assert_awaited_once_with(
            user_id="user-1",
            event_type="tool_call",
            risk_level=None,
            date_from=None,
            date_to=None,
            conversation_id=None,
            offset=0,
            limit=25,
        )


# ---------------------------------------------------------------------------
# Admin-only access
# ---------------------------------------------------------------------------


class TestAuditAdminGuard:
    async def test_non_admin_cannot_query_events(self, non_admin_client):
        response = await non_admin_client.get("/api/audit/events")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
