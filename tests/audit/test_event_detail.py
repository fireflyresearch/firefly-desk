# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the single audit event detail endpoint and logger method."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.auth.models import UserSession
from flydesk.models.base import Base


# ---------------------------------------------------------------------------
# Helpers
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


def _sample_event(**overrides) -> AuditEvent:
    defaults = dict(
        event_type=AuditEventType.TOOL_CALL,
        user_id="user-1",
        conversation_id="conv-1",
        system_id="sys-1",
        endpoint_id="ep-1",
        action="list_users",
        detail={"args": {"page": 1}},
        risk_level="read",
        ip_address="10.0.0.1",
        user_agent="TestAgent/1.0",
    )
    defaults.update(overrides)
    return AuditEvent(**defaults)


# ---------------------------------------------------------------------------
# Logger-level tests (real SQLite)
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
def logger(session_factory):
    return AuditLogger(session_factory)


class TestGetEventLogger:
    """Tests for AuditLogger.get_event() method."""

    async def test_get_event_returns_event(self, logger):
        """Log an event, then retrieve it by ID."""
        event = _sample_event()
        event_id = await logger.log(event)

        result = await logger.get_event(event_id)
        assert result is not None
        assert result.id == event_id
        assert result.event_type == AuditEventType.TOOL_CALL
        assert result.user_id == "user-1"
        assert result.action == "list_users"

    async def test_get_event_not_found(self, logger):
        """Non-existent ID returns None."""
        result = await logger.get_event("does-not-exist")
        assert result is None

    async def test_get_event_all_fields_populated(self, logger):
        """Verify all optional fields survive the round-trip."""
        event = _sample_event()
        event_id = await logger.log(event)

        result = await logger.get_event(event_id)
        assert result is not None
        assert result.id == event_id
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)
        assert result.event_type == AuditEventType.TOOL_CALL
        assert result.user_id == "user-1"
        assert result.conversation_id == "conv-1"
        assert result.system_id == "sys-1"
        assert result.endpoint_id == "ep-1"
        assert result.action == "list_users"
        assert result.detail == {"args": {"page": 1}}
        assert result.risk_level == "read"
        assert result.ip_address == "10.0.0.1"
        assert result.user_agent == "TestAgent/1.0"


# ---------------------------------------------------------------------------
# API-level tests (mocked logger)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_audit_logger():
    mock = AsyncMock()
    mock.query = AsyncMock(return_value=[])
    mock.get_event = AsyncMock(return_value=None)
    return mock


@pytest.fixture
async def admin_client(mock_audit_logger):
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


class TestGetEventDetailAPI:
    """Tests for GET /api/audit/events/{event_id}."""

    async def test_get_existing_event(self, admin_client, mock_audit_logger):
        """Existing event ID returns full AuditEvent JSON."""
        mock_audit_logger.get_event.return_value = _sample_event(id="evt-123")
        response = await admin_client.get("/api/audit/events/evt-123")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "evt-123"
        assert data["event_type"] == "tool_call"
        assert data["user_id"] == "user-1"
        assert data["action"] == "list_users"
        assert data["conversation_id"] == "conv-1"
        assert data["system_id"] == "sys-1"
        assert data["endpoint_id"] == "ep-1"
        assert data["detail"] == {"args": {"page": 1}}
        assert data["risk_level"] == "read"
        assert data["ip_address"] == "10.0.0.1"
        assert data["user_agent"] == "TestAgent/1.0"
        mock_audit_logger.get_event.assert_awaited_once_with("evt-123")

    async def test_get_nonexistent_event_returns_404(
        self, admin_client, mock_audit_logger
    ):
        """Non-existent event ID returns 404."""
        mock_audit_logger.get_event.return_value = None
        response = await admin_client.get("/api/audit/events/no-such-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_non_admin_cannot_get_event_detail(self, non_admin_client):
        """Non-admin user gets 403 on event detail endpoint."""
        response = await non_admin_client.get("/api/audit/events/evt-123")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
