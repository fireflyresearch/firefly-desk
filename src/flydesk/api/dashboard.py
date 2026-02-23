# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Admin Dashboard REST API -- system stats and detailed health."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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
