# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin Dashboard REST API -- system stats and detailed health."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.audit.logger import AuditLogger
from flydesk.catalog.repository import CatalogRepository
from flydesk.llm.health import LLMHealthChecker
from flydesk.llm.repository import LLMProviderRepository
from flydesk.models.audit import AuditEventRow
from flydesk.models.conversation import ConversationRow, MessageRow
from flydesk.rbac.guards import AdminDashboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/dashboard", tags=["dashboard"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_catalog_repo() -> CatalogRepository:
    """Provide a CatalogRepository instance."""
    raise NotImplementedError(
        "get_catalog_repo must be overridden via app.dependency_overrides"
    )


def get_audit_logger() -> AuditLogger:
    """Provide an AuditLogger instance."""
    raise NotImplementedError(
        "get_audit_logger must be overridden via app.dependency_overrides"
    )


def get_llm_repo() -> LLMProviderRepository:
    """Provide an LLMProviderRepository instance."""
    raise NotImplementedError(
        "get_llm_repo must be overridden via app.dependency_overrides"
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide the database session factory."""
    raise NotImplementedError(
        "get_session_factory must be overridden via app.dependency_overrides"
    )


CatalogRepo = Annotated[CatalogRepository, Depends(get_catalog_repo)]
Audit = Annotated[AuditLogger, Depends(get_audit_logger)]
LLMRepo = Annotated[LLMProviderRepository, Depends(get_llm_repo)]
SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class SystemStats(BaseModel):
    """Aggregated system statistics for the dashboard."""

    conversation_count: int = 0
    message_count: int = 0
    active_user_count: int = 0
    system_count: int = 0
    knowledge_doc_count: int = 0
    audit_event_count: int = 0
    llm_provider_count: int = 0


class ComponentHealth(BaseModel):
    """Health status of a single component."""

    name: str
    status: str  # "healthy", "degraded", "unhealthy"
    detail: str | None = None
    latency_ms: float | None = None


class DetailedHealth(BaseModel):
    """Detailed health status of all system components."""

    overall: str  # "healthy", "degraded", "unhealthy"
    uptime_seconds: float = 0.0
    started_at: str | None = None
    components: list[ComponentHealth] = Field(default_factory=list)


class AuditEventSummary(BaseModel):
    """Compact audit event for dashboard display."""

    event_type: str
    user_id: str
    action: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None


class DailyCount(BaseModel):
    """A single day's count for time-series data."""

    date: str  # ISO date string (YYYY-MM-DD)
    count: int


class ToolUsageCount(BaseModel):
    """Usage count for a single tool."""

    tool_name: str
    count: int


class EventTypeCount(BaseModel):
    """Count for a single event type."""

    event_type: str
    count: int


class ConversationAnalytics(BaseModel):
    """Aggregated analytics for dashboard charts."""

    messages_per_day: list[DailyCount]
    avg_conversation_length: float
    tool_usage: list[ToolUsageCount]
    top_event_types: list[EventTypeCount]


class TokenUsageStats(BaseModel):
    """Token usage statistics with cost estimates."""

    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    period_days: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/stats", dependencies=[AdminDashboard])
async def get_stats(
    catalog_repo: CatalogRepo,
    audit: Audit,
    llm_repo: LLMRepo,
    session_factory: SessionFactory,
) -> SystemStats:
    """Return aggregated system statistics."""
    # Catalog counts
    systems = await catalog_repo.list_systems()
    knowledge_docs = await catalog_repo.list_knowledge_documents()

    # LLM provider count
    providers = await llm_repo.list_providers()

    # Conversation and user counts from the database directly
    conversation_count = 0
    message_count = 0
    active_user_count = 0
    audit_event_count = 0

    try:
        async with session_factory() as session:
            # Conversation count (exclude soft-deleted)
            result = await session.execute(
                select(func.count())
                .select_from(ConversationRow)
                .where(ConversationRow.status != "deleted")
            )
            conversation_count = result.scalar() or 0

            # Active user count (distinct user_ids in non-deleted conversations)
            result = await session.execute(
                select(func.count(func.distinct(ConversationRow.user_id)))
                .where(ConversationRow.status != "deleted")
            )
            active_user_count = result.scalar() or 0

            # Message count (only from non-deleted conversations)
            result = await session.execute(
                select(func.count())
                .select_from(MessageRow)
                .join(
                    ConversationRow,
                    MessageRow.conversation_id == ConversationRow.id,
                )
                .where(ConversationRow.status != "deleted")
            )
            message_count = result.scalar() or 0

            # Audit event count
            result = await session.execute(
                select(func.count()).select_from(AuditEventRow)
            )
            audit_event_count = result.scalar() or 0
    except Exception:
        logger.debug("Failed to query DB counts for dashboard stats.", exc_info=True)

    return SystemStats(
        conversation_count=conversation_count,
        message_count=message_count,
        active_user_count=active_user_count,
        system_count=len(systems),
        knowledge_doc_count=len(knowledge_docs),
        audit_event_count=audit_event_count,
        llm_provider_count=len(providers),
    )


@router.get("/health", dependencies=[AdminDashboard])
async def get_health(
    request: Request,
    llm_repo: LLMRepo,
    session_factory: SessionFactory,
) -> DetailedHealth:
    """Return detailed health status of all system components."""
    components: list[ComponentHealth] = []

    # Database health
    try:
        async with session_factory() as session:
            await session.execute(text("SELECT 1"))
        components.append(ComponentHealth(name="database", status="healthy"))
    except Exception as exc:
        components.append(
            ComponentHealth(name="database", status="unhealthy", detail=str(exc))
        )

    # LLM provider health
    try:
        providers = await llm_repo.list_providers()
        active_providers = [p for p in providers if p.is_active]
        if active_providers:
            checker = LLMHealthChecker()
            for provider in active_providers:
                try:
                    health = await checker.check(provider)
                    components.append(
                        ComponentHealth(
                            name=f"llm:{provider.name}",
                            status="healthy" if health.reachable else "degraded",
                            detail=health.error,
                            latency_ms=health.latency_ms,
                        )
                    )
                except Exception as exc:
                    components.append(
                        ComponentHealth(
                            name=f"llm:{provider.name}",
                            status="unhealthy",
                            detail=str(exc),
                        )
                    )
        else:
            components.append(
                ComponentHealth(
                    name="llm",
                    status="degraded",
                    detail="No active LLM providers configured",
                )
            )
    except Exception as exc:
        components.append(
            ComponentHealth(name="llm", status="unhealthy", detail=str(exc))
        )

    # Calculate uptime
    started_at = getattr(request.app.state, "started_at", None)
    uptime_seconds = 0.0
    started_at_str = None
    if started_at:
        uptime_seconds = (datetime.now(timezone.utc) - started_at).total_seconds()
        started_at_str = started_at.isoformat()

    # Overall status
    statuses = [c.status for c in components]
    if "unhealthy" in statuses:
        overall = "unhealthy"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    return DetailedHealth(
        overall=overall,
        uptime_seconds=uptime_seconds,
        started_at=started_at_str,
        components=components,
    )


@router.get("/recent-events", dependencies=[AdminDashboard])
async def get_recent_events(audit: Audit) -> list[AuditEventSummary]:
    """Return the 10 most recent audit events for the dashboard."""
    events = await audit.query(limit=10)
    return [
        AuditEventSummary(
            event_type=e.event_type,
            user_id=e.user_id,
            action=e.action,
            detail=e.detail,
            created_at=e.timestamp.isoformat() if e.timestamp else None,
        )
        for e in events
    ]


@router.get("/analytics", dependencies=[AdminDashboard])
async def get_analytics(
    session_factory: SessionFactory,
    days: int = 30,
) -> ConversationAnalytics:
    """Return conversation analytics: messages per day, tool usage, etc."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    messages_per_day: list[DailyCount] = []
    avg_conversation_length: float = 0.0
    tool_usage: list[ToolUsageCount] = []
    top_event_types: list[EventTypeCount] = []

    try:
        async with session_factory() as session:
            # 1) Messages per day for the last N days
            date_col = func.date(MessageRow.created_at)
            stmt = (
                select(date_col.label("day"), func.count().label("cnt"))
                .where(MessageRow.created_at >= cutoff)
                .group_by(date_col)
                .order_by(date_col)
            )
            result = await session.execute(stmt)
            messages_per_day = [
                DailyCount(date=str(row.day), count=row.cnt)
                for row in result.all()
            ]

            # 2) Average conversation length (messages per conversation)
            sub = (
                select(
                    MessageRow.conversation_id,
                    func.count().label("msg_count"),
                )
                .group_by(MessageRow.conversation_id)
                .subquery()
            )
            result = await session.execute(
                select(func.avg(sub.c.msg_count))
            )
            avg_val = result.scalar()
            avg_conversation_length = round(float(avg_val), 2) if avg_val else 0.0

            # 3) Tool usage: GROUP BY action WHERE event_type = 'tool_call'
            stmt = (
                select(
                    AuditEventRow.action.label("tool_name"),
                    func.count().label("cnt"),
                )
                .where(AuditEventRow.event_type == "tool_call")
                .where(AuditEventRow.created_at >= cutoff)
                .group_by(AuditEventRow.action)
                .order_by(func.count().desc())
            )
            result = await session.execute(stmt)
            tool_usage = [
                ToolUsageCount(tool_name=row.tool_name, count=row.cnt)
                for row in result.all()
            ]

            # 4) Top event types: GROUP BY event_type, top 10
            stmt = (
                select(
                    AuditEventRow.event_type.label("evt"),
                    func.count().label("cnt"),
                )
                .where(AuditEventRow.created_at >= cutoff)
                .group_by(AuditEventRow.event_type)
                .order_by(func.count().desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            top_event_types = [
                EventTypeCount(event_type=row.evt, count=row.cnt)
                for row in result.all()
            ]
    except Exception:
        logger.debug("Failed to query analytics data.", exc_info=True)

    return ConversationAnalytics(
        messages_per_day=messages_per_day,
        avg_conversation_length=avg_conversation_length,
        tool_usage=tool_usage,
        top_event_types=top_event_types,
    )


# Default per-token pricing (USD per token)
_INPUT_PRICE_PER_TOKEN = 3.0 / 1_000_000   # $3 per 1M input tokens
_OUTPUT_PRICE_PER_TOKEN = 15.0 / 1_000_000  # $15 per 1M output tokens


@router.get("/token-usage", dependencies=[AdminDashboard])
async def get_token_usage(
    session_factory: SessionFactory,
    days: int = 30,
) -> TokenUsageStats:
    """Return token usage statistics with cost estimates."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    total_input_tokens = 0
    total_output_tokens = 0

    try:
        async with session_factory() as session:
            # Fetch agent_response audit events for the period.
            # The detail column stores token counts; since it's Text in
            # SQLite and JSONB in Postgres we parse in Python for portability.
            stmt = (
                select(AuditEventRow.detail)
                .where(AuditEventRow.event_type == "agent_response")
                .where(AuditEventRow.created_at >= cutoff)
            )
            result = await session.execute(stmt)

            for (detail_raw,) in result.all():
                detail = detail_raw
                # SQLite stores JSON as text; Postgres returns dict.
                if isinstance(detail, str):
                    try:
                        detail = json.loads(detail)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if not isinstance(detail, dict):
                    continue

                total_input_tokens += int(detail.get("input_tokens", 0))
                total_output_tokens += int(detail.get("output_tokens", 0))
    except Exception:
        logger.debug("Failed to query token usage data.", exc_info=True)

    estimated_cost = (
        total_input_tokens * _INPUT_PRICE_PER_TOKEN
        + total_output_tokens * _OUTPUT_PRICE_PER_TOKEN
    )

    return TokenUsageStats(
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        estimated_cost_usd=round(estimated_cost, 4),
        period_days=days,
    )
