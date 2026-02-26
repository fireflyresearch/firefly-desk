# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the POST /api/memory endpoint."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.memory.models import UserMemory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_session() -> UserSession:
    return UserSession(
        user_id="user-1",
        email="tester@example.com",
        display_name="Test User",
        roles=[],
        permissions=[],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _fake_memory(**overrides) -> UserMemory:
    defaults = dict(
        id="mem-001",
        user_id="user-1",
        content="Remember this",
        category="general",
        source="user",
        metadata=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return UserMemory(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_memory_repo():
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_fake_memory())
    return repo


@pytest.fixture
async def client(mock_memory_repo):
    """AsyncClient with a user session and mocked MemoryRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_memory_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_memory_repo] = lambda: mock_memory_repo

        user_session = _make_user_session()

        async def _set_user(request, call_next):
            request.state.user_session = user_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def unauth_client():
    """AsyncClient with no user session (bare app, no auth middleware)."""
    from fastapi import FastAPI

    from flydesk.api.deps import get_memory_repo
    from flydesk.api.memory import router as memory_router

    app = FastAPI()
    app.include_router(memory_router)
    mock_repo = AsyncMock()
    app.dependency_overrides[get_memory_repo] = lambda: mock_repo

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateMemory:
    async def test_create_returns_201(self, client, mock_memory_repo):
        """POST with valid body returns 201 and the created memory."""
        response = await client.post(
            "/api/memory",
            json={"content": "Remember this", "category": "general"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "mem-001"
        assert data["content"] == "Remember this"
        assert data["source"] == "user"
        assert data["user_id"] == "user-1"

        # Verify repo.create was called with correct user_id
        mock_memory_repo.create.assert_awaited_once()
        call_args = mock_memory_repo.create.call_args
        assert call_args[0][0] == "user-1"

    async def test_create_without_auth_returns_401(self, unauth_client):
        """POST without a user session returns 401."""
        response = await unauth_client.post(
            "/api/memory",
            json={"content": "Should fail"},
        )
        assert response.status_code == 401

    async def test_source_forced_to_user(self, client, mock_memory_repo):
        """Even if the request body says source='agent', it is forced to 'user'."""
        response = await client.post(
            "/api/memory",
            json={"content": "Agent attempt", "source": "agent"},
        )
        assert response.status_code == 201

        # The CreateMemory body passed to repo.create must have source="user"
        call_args = mock_memory_repo.create.call_args
        create_body = call_args[0][1]
        assert create_body.source == "user"

    async def test_create_with_all_fields(self, client, mock_memory_repo):
        """POST with all optional fields works correctly."""
        mock_memory_repo.create.return_value = _fake_memory(
            content="Full memory",
            category="preference",
            metadata={"key": "value"},
        )
        response = await client.post(
            "/api/memory",
            json={
                "content": "Full memory",
                "category": "preference",
                "metadata": {"key": "value"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "preference"
        assert data["metadata"] == {"key": "value"}

    async def test_create_with_invalid_category_returns_422(self, client):
        """POST with an invalid category returns 422."""
        response = await client.post(
            "/api/memory",
            json={"content": "Bad category", "category": "invalid"},
        )
        assert response.status_code == 422

    async def test_create_with_empty_content_returns_422(self, client):
        """POST with empty content string returns 422."""
        response = await client.post(
            "/api/memory",
            json={"content": ""},
        )
        assert response.status_code == 422

    async def test_create_without_content_returns_422(self, client):
        """POST without content field returns 422."""
        response = await client.post(
            "/api/memory",
            json={},
        )
        assert response.status_code == 422
