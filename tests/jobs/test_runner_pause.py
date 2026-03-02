"""Tests for JobRunner pause/resume functionality."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.handlers import ExecutionResult
from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.jobs.runner import JobRunner
from flydesk.models.base import Base


class _PausableHandler:
    """Handler that yields to pause after 2 iterations."""

    async def execute(self, job_id, payload, on_progress, checkpoint=None, should_pause=lambda: False):
        start = (checkpoint or {}).get("index", 0)
        for i in range(start, 5):
            await on_progress(i * 20, f"Step {i}")
            if should_pause():
                return ExecutionResult(result={}, checkpoint={"index": i + 1})
        return ExecutionResult(result={"done": True})


class _NonPausableHandler:
    """Handler that ignores should_pause (single-shot)."""

    async def execute(self, job_id, payload, on_progress, checkpoint=None, should_pause=lambda: False):
        await on_progress(50, "Working")
        await on_progress(100, "Done")
        return {"completed": True}


@pytest.fixture
async def setup():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    repo = JobRepository(sf)
    runner = JobRunner(repo)
    runner.register_handler("pausable", _PausableHandler())
    runner.register_handler("simple", _NonPausableHandler())
    yield repo, runner
    await engine.dispose()


class TestPauseRequest:
    async def test_request_pause_sets_flag(self, setup):
        repo, runner = setup
        job = await runner.submit("pausable", {})
        runner.request_pause(job.id)
        assert runner.is_pause_requested(job.id)

    async def test_request_pause_unknown_job_is_noop(self, setup):
        _, runner = setup
        runner.request_pause("nonexistent")  # should not raise


class TestResumeJob:
    async def test_resume_enqueues_paused_job(self, setup):
        repo, runner = setup
        job = Job(
            id="j-paused",
            job_type="pausable",
            status=JobStatus.PAUSED,
            created_at=datetime.now(timezone.utc),
            checkpoint={"index": 2},
        )
        await repo.create(job)
        await runner.resume(job.id)
        loaded = await repo.get("j-paused")
        assert loaded.status == JobStatus.PENDING
