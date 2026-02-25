# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for dashboard analytics and token-usage endpoints."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.catalog.repository import CatalogRepository
from flydesk.conversation.models import Conversation, Message, MessageRole
from flydesk.conversation.repository import ConversationRepository
from flydesk.llm.repository import LLMProviderRepository
from flydesk.models.audit import AuditEventRow
from flydesk.models.base import Base
from flydesk.models.conversation import MessageRow


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDESK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydesk.api.dashboard import (
            get_audit_logger,
            get_catalog_repo,
            get_llm_repo,
            get_session_factory,
        )
        from flydesk.server import create_app

        app = create_app()

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

        app.state.started_at = datetime.now(timezone.utc)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, conversation_repo, audit_logger, session_factory

        await engine.dispose()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uid() -> str:
    return str(uuid.uuid4())


async def _seed_messages(
    conversation_repo: ConversationRepository,
    session_factory: async_sessionmaker,
    *,
    conv_id: str = "conv-1",
    user_id: str = "user-a",
    count: int = 3,
    days_ago: int = 0,
):
    """Create a conversation and N messages, optionally backdated."""
    await conversation_repo.create_conversation(
        Conversation(id=conv_id, user_id=user_id, title=f"Conv {conv_id}")
    )
    for i in range(count):
        msg_id = f"{conv_id}-msg-{i}"
        await conversation_repo.add_message(
            Message(
                id=msg_id,
                conversation_id=conv_id,
                role=MessageRole.USER,
                content=f"message {i}",
            ),
            user_id=user_id,
        )
    # Backdate messages if needed
    if days_ago > 0:
        target = datetime.now(timezone.utc) - timedelta(days=days_ago)
        async with session_factory() as session:
            from sqlalchemy import update
            await session.execute(
                update(MessageRow)
                .where(MessageRow.conversation_id == conv_id)
                .values(created_at=target)
            )
            await session.commit()


async def _seed_audit_event(
    audit_logger: AuditLogger,
    session_factory: async_sessionmaker,
    *,
    event_type: AuditEventType,
    action: str = "test",
    detail: dict | None = None,
    days_ago: int = 0,
):
    """Log an audit event, optionally backdated."""
    evt = AuditEvent(
        event_type=event_type,
        user_id="user-a",
        action=action,
        detail=detail or {},
    )
    await audit_logger.log(evt)
    # Backdate if needed
    if days_ago > 0:
        target = datetime.now(timezone.utc) - timedelta(days=days_ago)
        async with session_factory() as session:
            from sqlalchemy import update
            # Update the most recently created event matching our action
            await session.execute(
                update(AuditEventRow)
                .where(AuditEventRow.action == action)
                .where(AuditEventRow.event_type == event_type.value)
                .values(created_at=target)
            )
            await session.commit()


# ---------------------------------------------------------------------------
# Analytics endpoint tests
# ---------------------------------------------------------------------------


class TestAnalyticsEndpoint:
    """Tests for GET /api/admin/dashboard/analytics."""

    async def test_analytics_empty_database(self, client):
        """Returns zeroed analytics on an empty database."""
        ac, _, _, _ = client
        response = await ac.get("/api/admin/dashboard/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["messages_per_day"] == []
        assert data["avg_conversation_length"] == 0.0
        assert data["tool_usage"] == []
        assert data["top_event_types"] == []

    async def test_analytics_messages_per_day(self, client):
        """Messages per day reflects seeded messages."""
        ac, conv_repo, _, sf = client
        await _seed_messages(conv_repo, sf, conv_id="c1", count=3)
        await _seed_messages(conv_repo, sf, conv_id="c2", user_id="user-b", count=2)

        response = await ac.get("/api/admin/dashboard/analytics")
        assert response.status_code == 200
        data = response.json()

        # All messages created today; should be 1 day entry with total = 5
        mpd = data["messages_per_day"]
        assert len(mpd) >= 1
        total = sum(d["count"] for d in mpd)
        assert total == 5

    async def test_analytics_avg_conversation_length(self, client):
        """Average conversation length computed correctly."""
        ac, conv_repo, _, sf = client
        # conv-1 has 4 messages, conv-2 has 2 messages => avg = 3.0
        await _seed_messages(conv_repo, sf, conv_id="c1", count=4)
        await _seed_messages(conv_repo, sf, conv_id="c2", user_id="user-b", count=2)

        response = await ac.get("/api/admin/dashboard/analytics")
        data = response.json()
        assert data["avg_conversation_length"] == 3.0

    async def test_analytics_tool_usage(self, client):
        """Tool usage aggregates tool_call events by action."""
        ac, _, audit, sf = client
        for _ in range(3):
            await _seed_audit_event(
                audit, sf,
                event_type=AuditEventType.TOOL_CALL,
                action="search_knowledge",
            )
        for _ in range(2):
            await _seed_audit_event(
                audit, sf,
                event_type=AuditEventType.TOOL_CALL,
                action="run_query",
            )
        # An agent_response should NOT appear in tool_usage
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="respond",
        )

        response = await ac.get("/api/admin/dashboard/analytics")
        data = response.json()

        tool_names = {t["tool_name"]: t["count"] for t in data["tool_usage"]}
        assert tool_names["search_knowledge"] == 3
        assert tool_names["run_query"] == 2
        assert "respond" not in tool_names

    async def test_analytics_top_event_types(self, client):
        """Top event types includes all event types, sorted by count."""
        ac, _, audit, sf = client
        for _ in range(5):
            await _seed_audit_event(
                audit, sf, event_type=AuditEventType.TOOL_CALL, action="a"
            )
        for _ in range(3):
            await _seed_audit_event(
                audit, sf, event_type=AuditEventType.AGENT_RESPONSE, action="b"
            )
        await _seed_audit_event(
            audit, sf, event_type=AuditEventType.AUTH_LOGIN, action="c"
        )

        response = await ac.get("/api/admin/dashboard/analytics")
        data = response.json()

        evt_map = {e["event_type"]: e["count"] for e in data["top_event_types"]}
        assert evt_map["tool_call"] == 5
        assert evt_map["agent_response"] == 3
        assert evt_map["auth_login"] == 1
        # Verify sorted descending
        counts = [e["count"] for e in data["top_event_types"]]
        assert counts == sorted(counts, reverse=True)

    async def test_analytics_days_filter(self, client):
        """The days parameter filters out old messages."""
        ac, conv_repo, _, sf = client
        # Messages from 60 days ago (outside default 30-day window)
        await _seed_messages(conv_repo, sf, conv_id="old", count=5, days_ago=60)
        # Messages from today
        await _seed_messages(
            conv_repo, sf, conv_id="new", user_id="user-b", count=2
        )

        response = await ac.get("/api/admin/dashboard/analytics?days=30")
        data = response.json()

        total = sum(d["count"] for d in data["messages_per_day"])
        assert total == 2  # Only today's messages

    async def test_analytics_custom_days(self, client):
        """Custom days=90 includes older data."""
        ac, conv_repo, _, sf = client
        await _seed_messages(conv_repo, sf, conv_id="old", count=3, days_ago=60)
        await _seed_messages(
            conv_repo, sf, conv_id="new", user_id="user-b", count=2
        )

        response = await ac.get("/api/admin/dashboard/analytics?days=90")
        data = response.json()

        total = sum(d["count"] for d in data["messages_per_day"])
        assert total == 5  # Both old and new


# ---------------------------------------------------------------------------
# Token usage endpoint tests
# ---------------------------------------------------------------------------


class TestTokenUsageEndpoint:
    """Tests for GET /api/admin/dashboard/token-usage."""

    async def test_token_usage_empty_database(self, client):
        """Returns zero tokens on empty database."""
        ac, _, _, _ = client
        response = await ac.get("/api/admin/dashboard/token-usage")
        assert response.status_code == 200
        data = response.json()
        assert data["total_input_tokens"] == 0
        assert data["total_output_tokens"] == 0
        assert data["estimated_cost_usd"] == 0.0
        assert data["period_days"] == 30

    async def test_token_usage_sums_tokens(self, client):
        """Token counts are summed from agent_response events."""
        ac, _, audit, sf = client
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="response-1",
            detail={"input_tokens": 1000, "output_tokens": 500, "model": "gpt-4"},
        )
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="response-2",
            detail={"input_tokens": 2000, "output_tokens": 1500, "model": "gpt-4"},
        )

        response = await ac.get("/api/admin/dashboard/token-usage")
        data = response.json()
        assert data["total_input_tokens"] == 3000
        assert data["total_output_tokens"] == 2000

    async def test_token_usage_cost_estimate(self, client):
        """Cost estimate uses $3/M input, $15/M output pricing."""
        ac, _, audit, sf = client
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="response",
            detail={"input_tokens": 1_000_000, "output_tokens": 1_000_000},
        )

        response = await ac.get("/api/admin/dashboard/token-usage")
        data = response.json()
        # $3/M input + $15/M output = $18
        assert data["estimated_cost_usd"] == 18.0

    async def test_token_usage_ignores_non_agent_events(self, client):
        """Only agent_response events contribute to token counts."""
        ac, _, audit, sf = client
        # tool_call with tokens should be ignored
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.TOOL_CALL,
            action="tool-with-tokens",
            detail={"input_tokens": 9999, "output_tokens": 9999},
        )
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="real-response",
            detail={"input_tokens": 100, "output_tokens": 50},
        )

        response = await ac.get("/api/admin/dashboard/token-usage")
        data = response.json()
        assert data["total_input_tokens"] == 100
        assert data["total_output_tokens"] == 50

    async def test_token_usage_handles_missing_token_fields(self, client):
        """Events without token fields in detail are safely skipped."""
        ac, _, audit, sf = client
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="no-tokens",
            detail={"model": "gpt-4"},  # no token fields
        )
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="with-tokens",
            detail={"input_tokens": 200, "output_tokens": 100},
        )

        response = await ac.get("/api/admin/dashboard/token-usage")
        data = response.json()
        assert data["total_input_tokens"] == 200
        assert data["total_output_tokens"] == 100

    async def test_token_usage_custom_period(self, client):
        """The days parameter is passed through to the response."""
        ac, _, _, _ = client
        response = await ac.get("/api/admin/dashboard/token-usage?days=7")
        data = response.json()
        assert data["period_days"] == 7

    async def test_token_usage_days_filter_excludes_old(self, client):
        """Old events outside the period are excluded."""
        ac, _, audit, sf = client
        # Event from 60 days ago
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="old-response",
            detail={"input_tokens": 5000, "output_tokens": 3000},
            days_ago=60,
        )
        # Event from today
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="new-response",
            detail={"input_tokens": 100, "output_tokens": 50},
        )

        response = await ac.get("/api/admin/dashboard/token-usage?days=30")
        data = response.json()
        assert data["total_input_tokens"] == 100
        assert data["total_output_tokens"] == 50

    async def test_token_usage_handles_empty_detail(self, client):
        """Events with empty detail dict are handled gracefully."""
        ac, _, audit, sf = client
        await _seed_audit_event(
            audit, sf,
            event_type=AuditEventType.AGENT_RESPONSE,
            action="empty-detail",
            detail={},
        )

        response = await ac.get("/api/admin/dashboard/token-usage")
        data = response.json()
        assert data["total_input_tokens"] == 0
        assert data["total_output_tokens"] == 0
