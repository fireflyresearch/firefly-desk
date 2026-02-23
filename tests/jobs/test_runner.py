# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for JobRunner -- job submission, dispatching, and lifecycle."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.handlers import JobHandler, ProgressCallback
from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.jobs.runner import JobRunner
from flydesk.models.base import Base


# ---------------------------------------------------------------------------
# Test handler stubs
# ---------------------------------------------------------------------------


class SuccessHandler:
    """A handler that completes successfully and reports progress."""

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        await on_progress(50, "Halfway")
        await on_progress(100, "Done")
        return {"key": payload.get("value", "ok")}


class FailingHandler:
    """A handler that always raises an exception."""

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        raise RuntimeError("Something went wrong")


class SlowHandler:
    """A handler that takes a while so we can test cancellation."""

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        await on_progress(10, "Starting")
        await asyncio.sleep(10)  # Will be cancelled before completion
        return {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return JobRepository(session_factory)


@pytest.fixture
def runner(repo):
    return JobRunner(repo)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJobRunner:
    async def test_register_handler(self, runner):
        """A handler can be registered for a job type."""
        runner.register_handler("test", SuccessHandler())
        # No exception means success; verify by submitting later
        assert True

    async def test_submit_unregistered_type_raises(self, runner):
        """Submitting a job with no registered handler raises ValueError."""
        with pytest.raises(ValueError, match="No handler registered"):
            await runner.submit("unregistered", {})

    async def test_submit_creates_pending_job(self, runner, repo):
        """submit() creates a pending job in the repository."""
        runner.register_handler("test", SuccessHandler())
        job = await runner.submit("test", {"value": "hello"})

        assert job.status == JobStatus.PENDING
        assert job.job_type == "test"

        persisted = await repo.get(job.id)
        assert persisted is not None
        assert persisted.status == JobStatus.PENDING
        assert persisted.payload == {"value": "hello"}

    async def test_start_and_stop(self, runner):
        """The runner can be started and stopped without errors."""
        runner.register_handler("test", SuccessHandler())
        await runner.start()
        assert runner.is_running is True

        await runner.stop()
        assert runner.is_running is False

    async def test_job_executes_to_completion(self, runner, repo):
        """A submitted job is consumed, executed, and marked completed."""
        runner.register_handler("test", SuccessHandler())
        await runner.start()

        job = await runner.submit("test", {"value": "hello"})

        # Wait for the job to complete (give the consumer a moment)
        for _ in range(50):
            current = await repo.get(job.id)
            if current and current.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)

        await runner.stop()

        final = await repo.get(job.id)
        assert final is not None
        assert final.status == JobStatus.COMPLETED
        assert final.result == {"key": "hello"}
        assert final.progress_pct == 100
        assert final.started_at is not None
        assert final.completed_at is not None

    async def test_failed_job_records_error(self, runner, repo):
        """A failing handler results in a FAILED job with the error message."""
        runner.register_handler("fail", FailingHandler())
        await runner.start()

        job = await runner.submit("fail", {})

        for _ in range(50):
            current = await repo.get(job.id)
            if current and current.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)

        await runner.stop()

        final = await repo.get(job.id)
        assert final is not None
        assert final.status == JobStatus.FAILED
        assert "Something went wrong" in final.error
        assert final.completed_at is not None

    async def test_cancelled_job_is_skipped(self, runner, repo):
        """A job cancelled before execution is skipped by the runner."""
        runner.register_handler("slow", SlowHandler())

        # Submit without starting the runner, then cancel
        job = await runner.submit("slow", {})
        await repo.update_status(job.id, JobStatus.CANCELLED)

        await runner.start()
        # Allow consumer to process
        await asyncio.sleep(0.3)
        await runner.stop()

        final = await repo.get(job.id)
        assert final is not None
        assert final.status == JobStatus.CANCELLED

    async def test_multiple_jobs_processed_sequentially(self, runner, repo):
        """Multiple submitted jobs are processed one after another."""
        runner.register_handler("test", SuccessHandler())
        await runner.start()

        jobs = []
        for i in range(3):
            j = await runner.submit("test", {"value": f"item-{i}"})
            jobs.append(j)

        # Wait for all to complete
        for _ in range(100):
            all_done = True
            for j in jobs:
                current = await repo.get(j.id)
                if current and current.status not in (
                    JobStatus.COMPLETED,
                    JobStatus.FAILED,
                ):
                    all_done = False
                    break
            if all_done:
                break
            await asyncio.sleep(0.05)

        await runner.stop()

        for j in jobs:
            final = await repo.get(j.id)
            assert final is not None
            assert final.status == JobStatus.COMPLETED

    async def test_sse_queue_receives_progress(self, runner, repo):
        """Progress events are published to the SSE queue."""
        sse_queue: asyncio.Queue = asyncio.Queue()
        runner_with_sse = JobRunner(repo, on_sse_progress=sse_queue)
        runner_with_sse.register_handler("test", SuccessHandler())
        await runner_with_sse.start()

        job = await runner_with_sse.submit("test", {"value": "x"})

        # Wait for completion
        for _ in range(50):
            current = await repo.get(job.id)
            if current and current.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.05)

        await runner_with_sse.stop()

        # Drain SSE queue
        events = []
        while not sse_queue.empty():
            events.append(sse_queue.get_nowait())

        # Should have received at least two progress events (50%, 100%)
        assert len(events) >= 2
        assert events[0]["progress_pct"] == 50
        assert events[0]["job_id"] == job.id

    async def test_handler_protocol_check(self):
        """SuccessHandler and FailingHandler satisfy the JobHandler protocol."""
        assert isinstance(SuccessHandler(), JobHandler)
        assert isinstance(FailingHandler(), JobHandler)
