# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Notifications REST API -- unified view of recent jobs and workflows."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.api.deps import get_job_repo, get_session_factory, get_workflow_repo
from flydesk.jobs.models import Job
from flydesk.jobs.repository import JobRepository
from flydesk.models.notification_dismissal import NotificationDismissalRow
from flydesk.workflows.models import Workflow
from flydesk.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

JobRepo = Annotated[JobRepository, Depends(get_job_repo)]
WorkflowRepo = Annotated[WorkflowRepository, Depends(get_workflow_repo)]
SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_to_notification(job: Job) -> dict:
    """Convert a Job domain model to a notification dict."""
    # For updated_at, use the most recent timestamp available
    updated_at = job.completed_at or job.started_at or job.created_at
    return {
        "id": job.id,
        "type": "job",
        "title": job.job_type,
        "status": job.status.value,
        "progress": job.progress_pct,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


def _workflow_to_notification(wf: Workflow) -> dict:
    """Convert a Workflow domain model to a notification dict."""
    updated_at = wf.completed_at or wf.started_at or wf.created_at
    return {
        "id": wf.id,
        "type": "workflow",
        "title": wf.workflow_type,
        "status": wf.status.value,
        "progress": None,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
        "updated_at": updated_at.isoformat() if updated_at else None,
    }


async def _get_dismissed_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> set[str]:
    """Return the set of dismissed notification IDs."""
    async with session_factory() as session:
        stmt = select(NotificationDismissalRow.notification_id)
        result = await session.execute(stmt)
        return {row for row in result.scalars().all()}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_notifications(
    job_repo: JobRepo,
    wf_repo: WorkflowRepo,
    session_factory: SessionFactory,
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    """Return recent jobs and workflows as a unified notification list.

    Results are ordered by ``created_at DESC`` and capped at *limit*.
    Dismissed notifications are excluded.
    """
    # Fetch jobs and workflows in parallel-ish (both are async)
    jobs = await job_repo.list(limit=limit)
    workflows = await wf_repo.list(limit=limit)

    # Get dismissed IDs
    dismissed = await _get_dismissed_ids(session_factory)

    # Convert to notifications
    notifications: list[dict] = []
    for job in jobs:
        if job.id not in dismissed:
            notifications.append(_job_to_notification(job))
    for wf in workflows:
        if wf.id not in dismissed:
            notifications.append(_workflow_to_notification(wf))

    # Sort by created_at descending
    notifications.sort(
        key=lambda n: n["created_at"] or "",
        reverse=True,
    )

    # Apply limit
    notifications = notifications[:limit]

    return {"notifications": notifications}


@router.patch("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: str,
    job_repo: JobRepo,
    wf_repo: WorkflowRepo,
    session_factory: SessionFactory,
) -> dict:
    """Mark a notification as dismissed so it no longer appears in the list.

    Returns 404 if the notification ID does not correspond to an existing
    job or workflow.
    """
    # Verify the notification exists (either as a job or a workflow)
    job = await job_repo.get(notification_id)
    workflow = await wf_repo.get(notification_id)

    if job is None and workflow is None:
        raise HTTPException(status_code=404, detail="Notification not found")

    # Persist the dismissal
    async with session_factory() as session:
        row = NotificationDismissalRow(
            id=str(uuid.uuid4()),
            notification_id=notification_id,
            dismissed_at=datetime.now(timezone.utc),
        )
        session.add(row)
        await session.commit()

    return {"dismissed": True, "notification_id": notification_id}
