# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Feedback REST API."""

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
        email="tester@example.com",
        display_name="Test User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


@pytest.fixture
def mock_audit_logger():
    """Return an AsyncMock that mimics AuditLogger."""
    logger = AsyncMock()
    logger.log = AsyncMock(return_value="evt-001")
    return logger


@pytest.fixture
async def client(mock_audit_logger):
    """AsyncClient with a user session and mocked AuditLogger."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.feedback import get_audit_logger
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_audit_logger] = lambda: mock_audit_logger

        user_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = user_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Submit Feedback
# ---------------------------------------------------------------------------


class TestSubmitFeedback:
    async def test_thumbs_up(self, client, mock_audit_logger):
        response = await client.post(
            "/api/chat/messages/msg-123/feedback",
            json={"rating": "up"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message_id"] == "msg-123"
        assert data["status"] == "recorded"

        # Verify audit logger was called with the correct event
        mock_audit_logger.log.assert_awaited_once()
        event: AuditEvent = mock_audit_logger.log.call_args[0][0]
        assert event.event_type == AuditEventType.MESSAGE_FEEDBACK
        assert event.user_id == "user-1"
        assert event.action == "message_feedback"
        assert event.detail["message_id"] == "msg-123"
        assert event.detail["rating"] == "up"
        assert "comment" not in event.detail

    async def test_thumbs_down(self, client, mock_audit_logger):
        response = await client.post(
            "/api/chat/messages/msg-456/feedback",
            json={"rating": "down"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["message_id"] == "msg-456"
        assert data["status"] == "recorded"

        event: AuditEvent = mock_audit_logger.log.call_args[0][0]
        assert event.detail["rating"] == "down"

    async def test_with_comment(self, client, mock_audit_logger):
        response = await client.post(
            "/api/chat/messages/msg-789/feedback",
            json={"rating": "up", "comment": "Very helpful answer!"},
        )
        assert response.status_code == 201

        event: AuditEvent = mock_audit_logger.log.call_args[0][0]
        assert event.detail["comment"] == "Very helpful answer!"

    async def test_invalid_rating(self, client):
        response = await client.post(
            "/api/chat/messages/msg-123/feedback",
            json={"rating": "neutral"},
        )
        assert response.status_code == 422

    async def test_missing_rating(self, client):
        response = await client.post(
            "/api/chat/messages/msg-123/feedback",
            json={},
        )
        assert response.status_code == 422

    async def test_empty_comment_is_fine(self, client, mock_audit_logger):
        response = await client.post(
            "/api/chat/messages/msg-abc/feedback",
            json={"rating": "down", "comment": None},
        )
        assert response.status_code == 201

        event: AuditEvent = mock_audit_logger.log.call_args[0][0]
        assert "comment" not in event.detail

    async def test_different_message_ids(self, client, mock_audit_logger):
        """Verify the message_id from the URL path is used correctly."""
        response = await client.post(
            "/api/chat/messages/some-unique-id-xyz/feedback",
            json={"rating": "up"},
        )
        assert response.status_code == 201
        assert response.json()["message_id"] == "some-unique-id-xyz"

        event: AuditEvent = mock_audit_logger.log.call_args[0][0]
        assert event.detail["message_id"] == "some-unique-id-xyz"
