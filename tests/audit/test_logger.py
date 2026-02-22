# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the audit logger and audit event models."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.models.base import Base


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


def _make_event(**overrides) -> AuditEvent:
    """Helper to create a default AuditEvent with optional overrides."""
    defaults = {
        "event_type": AuditEventType.TOOL_CALL,
        "user_id": "user-1",
        "conversation_id": "conv-1",
        "action": "called get_customer",
    }
    defaults.update(overrides)
    return AuditEvent(**defaults)


class TestAuditEventModel:
    def test_audit_event_creation(self):
        event = AuditEvent(
            event_type=AuditEventType.TOOL_CALL,
            user_id="user-1",
            conversation_id="conv-1",
            action="called get_customer",
            detail={"tool": "get_customer", "args": {"id": "123"}},
            risk_level="read",
            ip_address="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        assert event.event_type == AuditEventType.TOOL_CALL
        assert event.user_id == "user-1"
        assert event.conversation_id == "conv-1"
        assert event.action == "called get_customer"
        assert event.detail == {"tool": "get_customer", "args": {"id": "123"}}
        assert event.risk_level == "read"
        assert event.ip_address == "10.0.0.1"
        assert event.user_agent == "Mozilla/5.0"

    def test_audit_event_defaults(self):
        event = AuditEvent(
            event_type=AuditEventType.TOOL_CALL,
            user_id="user-1",
            action="test",
        )
        assert event.conversation_id is None
        assert event.system_id is None
        assert event.endpoint_id is None
        assert event.detail == {}
        assert event.risk_level is None
        assert event.ip_address is None
        assert event.user_agent is None

    def test_audit_event_types(self):
        expected = {
            "tool_call",
            "tool_result",
            "confirmation_requested",
            "confirmation_response",
            "agent_response",
            "auth_login",
            "auth_logout",
            "catalog_change",
            "knowledge_update",
        }
        actual = {e.value for e in AuditEventType}
        assert actual == expected


class TestAuditLogger:
    async def test_log_and_query(self, logger):
        event = _make_event(detail={"tool": "get_customer"})
        event_id = await logger.log(event)

        assert event_id is not None
        assert isinstance(event_id, str)
        assert len(event_id) == 36  # UUID format

        events = await logger.query()
        assert len(events) == 1
        assert events[0].event_type == AuditEventType.TOOL_CALL
        assert events[0].user_id == "user-1"
        assert events[0].action == "called get_customer"
        assert events[0].detail == {"tool": "get_customer"}

    async def test_pii_sanitization_email(self, logger):
        event = _make_event(
            detail={"message": "Contact john.doe@example.com for details"},
        )
        await logger.log(event)

        events = await logger.query()
        assert events[0].detail["message"] == "Contact [EMAIL] for details"

    async def test_pii_sanitization_phone(self, logger):
        event = _make_event(
            detail={"message": "Call me at 555-123-4567 or 5551234567"},
        )
        await logger.log(event)

        events = await logger.query()
        assert events[0].detail["message"] == "Call me at [PHONE] or [PHONE]"

    async def test_pii_sanitization_ssn(self, logger):
        event = _make_event(
            detail={"message": "SSN is 123-45-6789"},
        )
        await logger.log(event)

        events = await logger.query()
        assert events[0].detail["message"] == "SSN is [SSN]"

    async def test_pii_sanitization_nested(self, logger):
        event = _make_event(
            detail={
                "outer": {
                    "email": "test@example.com",
                    "list_field": ["hello@world.com", "normal text"],
                }
            },
        )
        await logger.log(event)

        events = await logger.query()
        assert events[0].detail["outer"]["email"] == "[EMAIL]"
        assert events[0].detail["outer"]["list_field"] == ["[EMAIL]", "normal text"]

    async def test_query_by_user(self, logger):
        await logger.log(_make_event(user_id="alice", action="action-1"))
        await logger.log(_make_event(user_id="bob", action="action-2"))
        await logger.log(_make_event(user_id="alice", action="action-3"))

        alice_events = await logger.query(user_id="alice")
        assert len(alice_events) == 2
        assert all(e.user_id == "alice" for e in alice_events)

        bob_events = await logger.query(user_id="bob")
        assert len(bob_events) == 1
        assert bob_events[0].user_id == "bob"

    async def test_query_by_event_type(self, logger):
        await logger.log(
            _make_event(event_type=AuditEventType.TOOL_CALL, action="tool call")
        )
        await logger.log(
            _make_event(event_type=AuditEventType.AUTH_LOGIN, action="login")
        )
        await logger.log(
            _make_event(event_type=AuditEventType.TOOL_CALL, action="another tool call")
        )

        tool_events = await logger.query(event_type="tool_call")
        assert len(tool_events) == 2
        assert all(e.event_type == AuditEventType.TOOL_CALL for e in tool_events)

        auth_events = await logger.query(event_type="auth_login")
        assert len(auth_events) == 1
        assert auth_events[0].event_type == AuditEventType.AUTH_LOGIN

    async def test_query_limit(self, logger):
        for i in range(10):
            await logger.log(_make_event(action=f"action-{i}"))

        events = await logger.query(limit=3)
        assert len(events) == 3

    async def test_log_preserves_optional_fields(self, logger):
        event = _make_event(
            system_id="sys-1",
            endpoint_id="ep-1",
            risk_level="write",
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )
        await logger.log(event)

        events = await logger.query()
        assert len(events) == 1
        result = events[0]
        assert result.system_id == "sys-1"
        assert result.endpoint_id == "ep-1"
        assert result.risk_level == "write"
        assert result.ip_address == "192.168.1.1"
        assert result.user_agent == "TestAgent/1.0"
