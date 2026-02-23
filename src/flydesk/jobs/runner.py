# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Background job runner -- dispatches jobs to registered handlers."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from flydesk.jobs.handlers import JobHandler, ProgressCallback
from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository

logger = logging.getLogger(__name__)


class JobRunner:
    """Manages job submission, queuing, and dispatching to typed handlers.

    Uses an internal ``asyncio.Queue`` for job dispatching, similar to the
    existing indexing queue infrastructure.

    Progress updates are persisted in the database *and* broadcast to any
    registered SSE listeners via the ``on_sse_progress`` callback.
    """

    def __init__(
        self,
        repo: JobRepository,
        *,
        on_sse_progress: asyncio.Queue | None = None,
    ) -> None:
        self._repo = repo
        self._handlers: dict[str, JobHandler] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        # Optional queue where SSE progress events are published for streaming.
        self._sse_queue: asyncio.Queue | None = on_sse_progress

    # -- Handler registration ------------------------------------------------

    def register_handler(self, job_type: str, handler: JobHandler) -> None:
        """Register a handler for a given job type."""
        self._handlers[job_type] = handler
        logger.info("Registered job handler for type=%s", job_type)

    # -- Submission ----------------------------------------------------------

    async def submit(self, job_type: str, payload: dict) -> Job:
        """Create a new pending job and enqueue it for processing.

        Returns the newly created ``Job`` domain object.
        """
        if job_type not in self._handlers:
            raise ValueError(f"No handler registered for job type '{job_type}'")

        job = Job(
            id=str(uuid.uuid4()),
            job_type=job_type,
            status=JobStatus.PENDING,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
        await self._repo.create(job)
        await self._queue.put(job.id)
        logger.debug("Submitted job %s (type=%s)", job.id, job_type)
        return job

    # -- Lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Start the background consumer loop."""
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("JobRunner started")

    async def stop(self) -> None:
        """Gracefully stop the consumer loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("JobRunner stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # -- Internal consumer ---------------------------------------------------

    async def _consume_loop(self) -> None:
        """Main consumer loop -- pulls job IDs and dispatches to handlers."""
        while self._running:
            try:
                job_id = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except (asyncio.TimeoutError, TimeoutError):
                continue
            except asyncio.CancelledError:
                break

            await self._execute_job(job_id)

    async def _execute_job(self, job_id: str) -> None:
        """Load, execute, and finalise a single job."""
        job = await self._repo.get(job_id)
        if job is None:
            logger.warning("Job %s not found; skipping", job_id)
            return

        if job.status == JobStatus.CANCELLED:
            logger.info("Job %s was cancelled before execution; skipping", job_id)
            return

        handler = self._handlers.get(job.job_type)
        if handler is None:
            await self._repo.update_status(
                job_id,
                JobStatus.FAILED,
                error=f"No handler for job type '{job.job_type}'",
                completed_at=datetime.now(timezone.utc),
            )
            return

        # Mark as running
        now = datetime.now(timezone.utc)
        await self._repo.update_status(job_id, JobStatus.RUNNING, started_at=now)

        # Build progress callback
        async def _on_progress(pct: int, message: str) -> None:
            await self._repo.update_progress(job_id, pct, message)
            if self._sse_queue is not None:
                await self._sse_queue.put(
                    {
                        "job_id": job_id,
                        "job_type": job.job_type,
                        "progress_pct": pct,
                        "progress_message": message,
                    }
                )

        try:
            result = await handler.execute(job_id, job.payload, _on_progress)
            # Re-check status — job may have been cancelled while running
            current = await self._repo.get(job_id)
            if current and current.status == JobStatus.CANCELLED:
                logger.info("Job %s was cancelled during execution", job_id)
                return
            await self._repo.update_status(
                job_id,
                JobStatus.COMPLETED,
                result=result,
                completed_at=datetime.now(timezone.utc),
            )
            await self._repo.update_progress(job_id, 100, "Complete")
            logger.info("Job %s completed successfully", job_id)
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            await self._repo.update_status(
                job_id,
                JobStatus.FAILED,
                error=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
