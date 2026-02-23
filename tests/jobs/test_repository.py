# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for JobRepository -- CRUD for background jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
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
def repo(session_factory):
    return JobRepository(session_factory)


def _make_job(
    job_id: str = "j-1",
    job_type: str = "indexing",
    status: JobStatus = JobStatus.PENDING,
    **kwargs,
) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=job_id,
        job_type=job_type,
        status=status,
        created_at=kwargs.pop("created_at", now),
        payload=kwargs.pop("payload", {"doc_id": "d1"}),
        **kwargs,
    )


class TestJobRepository:
    async def test_create_and_get(self, repo):
        """Creating a job and retrieving it returns matching data."""
        job = _make_job()
        await repo.create(job)
        result = await repo.get("j-1")
        assert result is not None
        assert result.id == "j-1"
        assert result.job_type == "indexing"
        assert result.status == JobStatus.PENDING
        assert result.payload == {"doc_id": "d1"}

    async def test_get_nonexistent_returns_none(self, repo):
        """Getting a non-existent job returns None."""
        result = await repo.get("nonexistent")
        assert result is None

    async def test_list_all(self, repo):
        """list() returns all jobs, most recent first."""
        now = datetime.now(timezone.utc)
        j1 = _make_job("j-1", created_at=now - timedelta(minutes=2))
        j2 = _make_job("j-2", created_at=now - timedelta(minutes=1))
        j3 = _make_job("j-3", created_at=now)
        await repo.create(j1)
        await repo.create(j2)
        await repo.create(j3)

        result = await repo.list()
        assert len(result) == 3
        # Most recent first
        assert result[0].id == "j-3"
        assert result[2].id == "j-1"

    async def test_list_filter_by_type(self, repo):
        """list() filters by job_type."""
        await repo.create(_make_job("j-1", job_type="indexing"))
        await repo.create(_make_job("j-2", job_type="process_discovery"))
        await repo.create(_make_job("j-3", job_type="indexing"))

        result = await repo.list(job_type="indexing")
        assert len(result) == 2
        assert all(j.job_type == "indexing" for j in result)

    async def test_list_filter_by_status(self, repo):
        """list() filters by status."""
        await repo.create(_make_job("j-1", status=JobStatus.PENDING))
        await repo.create(_make_job("j-2", status=JobStatus.RUNNING))
        await repo.create(_make_job("j-3", status=JobStatus.COMPLETED))

        result = await repo.list(status=JobStatus.RUNNING)
        assert len(result) == 1
        assert result[0].id == "j-2"

    async def test_list_with_limit_and_offset(self, repo):
        """list() respects limit and offset."""
        for i in range(5):
            await repo.create(
                _make_job(
                    f"j-{i}",
                    created_at=datetime.now(timezone.utc) + timedelta(seconds=i),
                )
            )

        result = await repo.list(limit=2, offset=1)
        assert len(result) == 2
        # Most recent first: j-4, j-3, j-2, j-1, j-0
        # offset=1 skips j-4, limit=2 returns j-3, j-2
        assert result[0].id == "j-3"
        assert result[1].id == "j-2"

    async def test_update_status(self, repo):
        """update_status() changes the job status and optional fields."""
        await repo.create(_make_job())
        now = datetime.now(timezone.utc)
        await repo.update_status(
            "j-1",
            JobStatus.RUNNING,
            started_at=now,
        )

        job = await repo.get("j-1")
        assert job is not None
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None

    async def test_update_status_with_result(self, repo):
        """update_status() persists result dict."""
        await repo.create(_make_job())
        now = datetime.now(timezone.utc)
        await repo.update_status(
            "j-1",
            JobStatus.COMPLETED,
            result={"docs_indexed": 5},
            completed_at=now,
        )

        job = await repo.get("j-1")
        assert job is not None
        assert job.status == JobStatus.COMPLETED
        assert job.result == {"docs_indexed": 5}
        assert job.completed_at is not None

    async def test_update_status_with_error(self, repo):
        """update_status() persists error string."""
        await repo.create(_make_job())
        await repo.update_status(
            "j-1",
            JobStatus.FAILED,
            error="Connection timeout",
            completed_at=datetime.now(timezone.utc),
        )

        job = await repo.get("j-1")
        assert job is not None
        assert job.status == JobStatus.FAILED
        assert job.error == "Connection timeout"

    async def test_update_status_nonexistent_is_noop(self, repo):
        """update_status() on a missing job does not raise."""
        await repo.update_status("nope", JobStatus.FAILED)

    async def test_update_progress(self, repo):
        """update_progress() changes progress fields."""
        await repo.create(_make_job())
        await repo.update_progress("j-1", 42, "Processing chunk 42/100")

        job = await repo.get("j-1")
        assert job is not None
        assert job.progress_pct == 42
        assert job.progress_message == "Processing chunk 42/100"

    async def test_update_progress_nonexistent_is_noop(self, repo):
        """update_progress() on a missing job does not raise."""
        await repo.update_progress("nope", 50, "nope")

    async def test_cleanup_old(self, repo):
        """cleanup_old() removes old terminal jobs, keeps recent and active ones."""
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=60)

        # Old completed job -- should be cleaned up
        await repo.create(
            _make_job("j-old-done", status=JobStatus.COMPLETED, created_at=old)
        )
        # Old failed job -- should be cleaned up
        await repo.create(
            _make_job("j-old-fail", status=JobStatus.FAILED, created_at=old)
        )
        # Old running job -- should NOT be cleaned up (still active)
        await repo.create(
            _make_job("j-old-running", status=JobStatus.RUNNING, created_at=old)
        )
        # Recent completed job -- should NOT be cleaned up
        await repo.create(
            _make_job("j-new-done", status=JobStatus.COMPLETED, created_at=now)
        )

        deleted = await repo.cleanup_old(max_age_days=30)
        assert deleted == 2

        # Verify remaining
        remaining = await repo.list()
        ids = {j.id for j in remaining}
        assert ids == {"j-old-running", "j-new-done"}
