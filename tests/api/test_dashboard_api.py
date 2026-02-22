# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Admin Dashboard API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.audit.logger import AuditLogger
from flydek.audit.models import AuditEvent, AuditEventType
from flydek.catalog.repository import CatalogRepository
from flydek.conversation.repository import ConversationRepository
from flydek.conversation.models import Conversation
from flydek.llm.repository import LLMProviderRepository
from flydek.models.base import Base


@pytest.fixture
async def client():
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDEK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydek.api.dashboard import (
            get_audit_logger,
            get_catalog_repo,
            get_llm_repo,
            get_session_factory,
        )
        from flydek.server import create_app

        app = create_app()

        # Create an in-memory database and wire dependency overrides
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        catalog_repo = CatalogRepository(session_factory)
        audit_logger = AuditLogger(session_factory)
        llm_repo = LLMProviderRepository(session_factory)
        conversation_repo = ConversationRepository(session_factory)

        app.dependency_overrides[get_catalog_repo] = lambda: catalog_repo
        app.dependency_overrides[get_audit_logger] = lambda: audit_logger
        app.dependency_overrides[get_llm_repo] = lambda: llm_repo
        app.dependency_overrides[get_session_factory] = lambda: session_factory

        # Store started_at for health endpoint uptime
        app.state.started_at = datetime.now(timezone.utc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, conversation_repo, audit_logger

        await engine.dispose()


class TestDashboardStats:
    async def test_stats_empty_database(self, client):
        """GET /api/admin/dashboard/stats returns zeroes on empty DB."""
        ac, _, _ = client
        response = await ac.get("/api/admin/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_count"] == 0
        assert data["active_user_count"] == 0
        assert data["system_count"] == 0
        assert data["knowledge_doc_count"] == 0
        assert data["audit_event_count"] == 0

    async def test_stats_with_conversations(self, client):
        """Stats reflect conversation and user counts."""
        ac, conversation_repo, _ = client

        # Create some conversations
        await conversation_repo.create_conversation(
            Conversation(id="conv-1", user_id="user-a", title="Test 1")
        )
        await conversation_repo.create_conversation(
            Conversation(id="conv-2", user_id="user-b", title="Test 2")
        )
        await conversation_repo.create_conversation(
            Conversation(id="conv-3", user_id="user-a", title="Test 3")
        )

        response = await ac.get("/api/admin/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["conversation_count"] == 3
        assert data["active_user_count"] == 2

    async def test_stats_with_audit_events(self, client):
        """Stats reflect audit event counts."""
        ac, _, audit_logger = client

        await audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.TOOL_CALL,
                user_id="user-a",
                action="test_action",
                detail={"info": "test"},
            )
        )

        response = await ac.get("/api/admin/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["audit_event_count"] == 1


class TestDashboardHealth:
    async def test_health_returns_status(self, client):
        """GET /api/admin/dashboard/health returns overall status."""
        ac, _, _ = client
        response = await ac.get("/api/admin/dashboard/health")
        assert response.status_code == 200
        data = response.json()
        assert data["overall"] in ("healthy", "degraded", "unhealthy")
        assert "components" in data
        assert "uptime_seconds" in data

    async def test_health_includes_database(self, client):
        """Health check includes database component."""
        ac, _, _ = client
        response = await ac.get("/api/admin/dashboard/health")
        data = response.json()
        db_components = [c for c in data["components"] if c["name"] == "database"]
        assert len(db_components) == 1
        assert db_components[0]["status"] == "healthy"

    async def test_health_uptime_is_positive(self, client):
        """Uptime should be a positive number."""
        ac, _, _ = client
        response = await ac.get("/api/admin/dashboard/health")
        data = response.json()
        assert data["uptime_seconds"] >= 0


class TestRecentEvents:
    async def test_recent_events_empty(self, client):
        """GET /api/admin/dashboard/recent-events returns empty list."""
        ac, _, _ = client
        response = await ac.get("/api/admin/dashboard/recent-events")
        assert response.status_code == 200
        assert response.json() == []

    async def test_recent_events_with_data(self, client):
        """Recent events returns logged audit events."""
        ac, _, audit_logger = client

        await audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.CATALOG_CHANGE,
                user_id="user-a",
                action="created system",
                detail={"system": "test"},
            )
        )

        response = await ac.get("/api/admin/dashboard/recent-events")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "catalog_change"
        assert data[0]["action"] == "created system"
