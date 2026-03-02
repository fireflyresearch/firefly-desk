"""Tests for checkpoint persistence in JobRepository."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.models.base import Base

from datetime import datetime, timezone


@pytest.fixture
async def repo():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    yield JobRepository(sf)
    await engine.dispose()


def _job(job_id="j-1", **kw) -> Job:
    return Job(
        id=job_id,
        job_type="test",
        created_at=datetime.now(timezone.utc),
        **kw,
    )


class TestCheckpointPersistence:
    async def test_create_with_checkpoint(self, repo):
        job = _job(checkpoint={"index": 5, "processed": ["a", "b"]})
        await repo.create(job)
        loaded = await repo.get("j-1")
        assert loaded is not None
        assert loaded.checkpoint == {"index": 5, "processed": ["a", "b"]}

    async def test_create_without_checkpoint(self, repo):
        job = _job()
        await repo.create(job)
        loaded = await repo.get("j-1")
        assert loaded is not None
        assert loaded.checkpoint is None

    async def test_update_status_with_checkpoint(self, repo):
        await repo.create(_job())
        await repo.update_status(
            "j-1", JobStatus.PAUSED, checkpoint={"step": 3}
        )
        loaded = await repo.get("j-1")
        assert loaded.status == JobStatus.PAUSED
        assert loaded.checkpoint == {"step": 3}

    async def test_update_status_clears_checkpoint(self, repo):
        await repo.create(_job(checkpoint={"step": 3}))
        await repo.update_status("j-1", JobStatus.PENDING, checkpoint=None)
        loaded = await repo.get("j-1")
        assert loaded.checkpoint is None
