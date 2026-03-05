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

from flydesk.config import DeskConfig
from flydesk.jobs.dead_letter import DeadLetterRepository
from flydesk.jobs.handlers import ExecutionResult, JobHandler, ProgressCallback
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
        config: DeskConfig | None = None,
        on_sse_progress: asyncio.Queue | None = None,
        dead_letter: DeadLetterRepository | None = None,
    ) -> None:
        self._repo = repo
        self._config = config or DeskConfig()
        self._dead_letter = dead_letter
        self._handlers: dict[str, JobHandler] = {}
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._pause_requests: set[str] = set()
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
        """Start the background consumer loop and recover interrupted jobs."""
        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("JobRunner started")

        # Recover jobs that were pending/running when the server last shut down.
        recovered = 0
        for status in (JobStatus.PENDING, JobStatus.RUNNING):
            stale = await self._repo.list(status=status, limit=200)
            for job in stale:
                if job.job_type in self._handlers:
                    if status == JobStatus.RUNNING:
                        # Reset to pending — it was interrupted mid-execution
                        await self._repo.update_status(job.id, JobStatus.PENDING)
                    await self._queue.put(job.id)
                    recovered += 1
                else:
                    # No handler registered — mark as failed
                    await self._repo.update_status(
                        job.id,
                        JobStatus.FAILED,
                        error=f"No handler for '{job.job_type}' after restart",
                    )
        if recovered:
            logger.info("Recovered %d interrupted job(s)", recovered)

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

    # -- Pause / Resume ------------------------------------------------------

    def request_pause(self, job_id: str) -> None:
        """Signal that a running job should pause at next checkpoint."""
        self._pause_requests.add(job_id)

    def is_pause_requested(self, job_id: str) -> bool:
        return job_id in self._pause_requests

    def clear_pause_request(self, job_id: str) -> None:
        self._pause_requests.discard(job_id)

    async def resume(self, job_id: str) -> None:
        """Re-enqueue a paused job for execution."""
        await self._repo.update_status(job_id, JobStatus.PENDING)
        await self._queue.put(job_id)

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

        if job.status == JobStatus.PAUSED:
            # Resuming from checkpoint — this is expected
            pass

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

        should_pause = lambda: self.is_pause_requested(job_id)

        try:
            raw_result = await asyncio.wait_for(
                handler.execute(
                    job_id, job.payload, _on_progress,
                    checkpoint=job.checkpoint,
                    should_pause=should_pause,
                ),
                timeout=self._config.job_timeout_seconds,
            )

            # Handle pause: handler returned an ExecutionResult with checkpoint
            if isinstance(raw_result, ExecutionResult) and raw_result.is_paused:
                self.clear_pause_request(job_id)
                await self._repo.update_status(
                    job_id, JobStatus.PAUSED,
                    checkpoint=raw_result.checkpoint,
                )
                logger.info("Job %s paused with checkpoint", job_id)
                return

            result = raw_result.result if isinstance(raw_result, ExecutionResult) else raw_result

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
        except (asyncio.TimeoutError, TimeoutError):
            error_msg = (
                f"Job {job_id} timed out after {self._config.job_timeout_seconds}s"
            )
            logger.error(error_msg)
            await self._repo.update_status(
                job_id,
                JobStatus.FAILED,
                error=error_msg,
                completed_at=datetime.now(timezone.utc),
            )
            if self._dead_letter:
                await self._dead_letter.add(
                    source_type="job",
                    source_id=job_id,
                    payload={"job_type": str(getattr(job, "job_type", "")), "error_context": "timeout"},
                    error=error_msg,
                )
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            await self._repo.update_status(
                job_id,
                JobStatus.FAILED,
                error=str(exc),
                completed_at=datetime.now(timezone.utc),
            )
            if self._dead_letter:
                await self._dead_letter.add(
                    source_type="job",
                    source_id=job_id,
                    payload={"job_type": str(getattr(job, "job_type", "")), "error_context": "execution_failure"},
                    error=str(exc),
                )
