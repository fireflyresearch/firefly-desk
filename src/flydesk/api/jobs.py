# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Jobs REST API -- list, detail, cancel, and stream progress for background jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.jobs.runner import JobRunner
from flydesk.rbac.guards import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Permission guard: any authenticated user can view/manage their own jobs.
JobsRead = require_permission("jobs:read")
JobsCancel = require_permission("jobs:cancel")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_job_repo() -> JobRepository:
    """Provide a JobRepository instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_job_repo must be overridden via app.dependency_overrides"
    )


def get_job_runner() -> JobRunner:
    """Provide a JobRunner instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_job_runner must be overridden via app.dependency_overrides"
    )


JobRepo = Annotated[JobRepository, Depends(get_job_repo)]
Runner = Annotated[JobRunner, Depends(get_job_runner)]  # Used by future submit endpoint


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[JobsRead])
async def list_jobs(
    repo: JobRepo,
    job_type: str | None = Query(None, description="Filter by job type"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List background jobs with optional filters."""
    status_enum: JobStatus | None = None
    if status is not None:
        try:
            status_enum = JobStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. "
                f"Must be one of: {', '.join(s.value for s in JobStatus)}",
            )

    jobs = await repo.list(
        job_type=job_type,
        status=status_enum,
        limit=limit,
        offset=offset,
    )
    return [_job_to_dict(j) for j in jobs]


@router.get("/{job_id}", dependencies=[JobsRead])
async def get_job(job_id: str, repo: JobRepo) -> dict:
    """Get details of a specific job."""
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_dict(job)


@router.delete("/{job_id}", dependencies=[JobsCancel], status_code=204)
async def cancel_job(job_id: str, repo: JobRepo) -> None:
    """Cancel a pending or running job."""
    job = await repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=409,
            detail=f"Job is already in terminal state '{job.status.value}'",
        )

    await repo.update_status(job_id, JobStatus.CANCELLED)


@router.get("/{job_id}/stream", dependencies=[JobsRead])
async def stream_job_progress(
    job_id: str,
    repo: JobRepo,
    request: Request,
) -> StreamingResponse:
    """SSE stream of progress events for a specific job.

    The stream emits ``job_progress`` events until the job reaches a terminal
    state (completed, failed, or cancelled), then sends a final ``done`` event.
    """
    # Allow a brief grace period for the job to appear in the DB after
    # creation.  The submit() call commits to the database before returning
    # the job ID to the caller, but the frontend may reach this endpoint
    # before the DB commit is fully visible (e.g. WAL mode lag, read
    # replica delay).  Three quick retries cover this edge case.
    job: Job | None = None
    for attempt in range(3):
        job = await repo.get(job_id)
        if job is not None:
            break
        await asyncio.sleep(0.15 * (attempt + 1))

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _event_generator():
        """Poll the job status and yield SSE events."""
        last_pct = -1
        last_msg = ""
        while True:
            if await request.is_disconnected():
                break

            current = await repo.get(job_id)
            if current is None:
                break

            # Emit progress if changed
            if current.progress_pct != last_pct or current.progress_message != last_msg:
                last_pct = current.progress_pct
                last_msg = current.progress_message
                event = SSEEvent(
                    event=SSEEventType.JOB_PROGRESS,
                    data={
                        "job_id": current.id,
                        "job_type": current.job_type,
                        "status": current.status.value,
                        "progress_pct": current.progress_pct,
                        "progress_message": current.progress_message,
                    },
                )
                yield event.to_sse()

            # Terminal state -- send done and close
            if current.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                done_data: dict = {
                    "job_id": current.id,
                    "status": current.status.value,
                }
                if current.result is not None:
                    done_data["result"] = current.result
                if current.error is not None:
                    done_data["error"] = current.error

                done_event = SSEEvent(
                    event=SSEEventType.DONE,
                    data=done_data,
                )
                yield done_event.to_sse()
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _job_to_dict(job: Job) -> dict:
    """Convert a Job domain model to a JSON-friendly dict."""
    return {
        "id": job.id,
        "job_type": job.job_type,
        "status": job.status.value,
        "progress_pct": job.progress_pct,
        "progress_message": job.progress_message,
        "result": job.result,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }
