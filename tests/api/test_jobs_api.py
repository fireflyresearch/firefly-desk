# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Jobs REST API endpoints."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.jobs.runner import JobRunner
from flydesk.models.base import Base


# ---------------------------------------------------------------------------
# Test handler for submission tests
# ---------------------------------------------------------------------------


class _QuickHandler:
    async def execute(self, job_id, payload, on_progress):
        await on_progress(100, "Done")
        return {"ok": True}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_DEV_MODE": "true",
        "FLYDESK_AGENT_NAME": "Ember",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.jobs import get_job_repo, get_job_runner
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        job_repo = JobRepository(session_factory)
        job_runner = JobRunner(job_repo)
        job_runner.register_handler("test", _QuickHandler())

        app.dependency_overrides[get_job_repo] = lambda: job_repo
        app.dependency_overrides[get_job_runner] = lambda: job_runner

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, job_repo, job_runner

        await engine.dispose()


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
        payload=kwargs.pop("payload", {}),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestJobsListAPI:
    async def test_list_jobs_empty(self, client):
        """GET /api/jobs returns empty list when no jobs exist."""
        ac, repo, runner = client
        response = await ac.get("/api/jobs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_jobs_returns_all(self, client):
        """GET /api/jobs returns all jobs."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1"))
        await repo.create(_make_job("j-2", job_type="process_discovery"))

        response = await ac.get("/api/jobs")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 2

    async def test_list_jobs_filter_by_type(self, client):
        """GET /api/jobs?job_type=indexing filters by job type."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1", job_type="indexing"))
        await repo.create(_make_job("j-2", job_type="process_discovery"))

        response = await ac.get("/api/jobs", params={"job_type": "indexing"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["job_type"] == "indexing"

    async def test_list_jobs_filter_by_status(self, client):
        """GET /api/jobs?status=running filters by status."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1", status=JobStatus.PENDING))
        await repo.create(_make_job("j-2", status=JobStatus.RUNNING))

        response = await ac.get("/api/jobs", params={"status": "running"})
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["status"] == "running"

    async def test_list_jobs_invalid_status(self, client):
        """GET /api/jobs?status=bogus returns 400."""
        ac, repo, runner = client
        response = await ac.get("/api/jobs", params={"status": "bogus"})
        assert response.status_code == 400

    async def test_list_jobs_with_limit(self, client):
        """GET /api/jobs?limit=1 limits results."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1"))
        await repo.create(_make_job("j-2"))

        response = await ac.get("/api/jobs", params={"limit": 1})
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestJobsDetailAPI:
    async def test_get_job(self, client):
        """GET /api/jobs/{id} returns job details."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1", job_type="indexing"))

        response = await ac.get("/api/jobs/j-1")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "j-1"
        assert body["job_type"] == "indexing"
        assert body["status"] == "pending"

    async def test_get_job_not_found(self, client):
        """GET /api/jobs/{id} returns 404 for unknown jobs."""
        ac, repo, runner = client
        response = await ac.get("/api/jobs/nonexistent")
        assert response.status_code == 404

    async def test_get_job_with_result(self, client):
        """GET /api/jobs/{id} includes result for completed jobs."""
        ac, repo, runner = client
        job = _make_job("j-done", status=JobStatus.COMPLETED)
        await repo.create(job)
        await repo.update_status("j-done", JobStatus.COMPLETED, result={"docs": 5})

        response = await ac.get("/api/jobs/j-done")
        assert response.status_code == 200
        body = response.json()
        assert body["result"] == {"docs": 5}


class TestJobsCancelAPI:
    async def test_cancel_pending_job(self, client):
        """DELETE /api/jobs/{id} cancels a pending job."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1"))

        response = await ac.delete("/api/jobs/j-1")
        assert response.status_code == 204

        job = await repo.get("j-1")
        assert job is not None
        assert job.status == JobStatus.CANCELLED

    async def test_cancel_running_job(self, client):
        """DELETE /api/jobs/{id} cancels a running job."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1", status=JobStatus.RUNNING))

        response = await ac.delete("/api/jobs/j-1")
        assert response.status_code == 204

        job = await repo.get("j-1")
        assert job.status == JobStatus.CANCELLED

    async def test_cancel_completed_job_returns_409(self, client):
        """DELETE /api/jobs/{id} returns 409 for terminal-state jobs."""
        ac, repo, runner = client
        await repo.create(_make_job("j-1", status=JobStatus.COMPLETED))

        response = await ac.delete("/api/jobs/j-1")
        assert response.status_code == 409

    async def test_cancel_nonexistent_job_returns_404(self, client):
        """DELETE /api/jobs/{id} returns 404 for unknown jobs."""
        ac, repo, runner = client
        response = await ac.delete("/api/jobs/nonexistent")
        assert response.status_code == 404


class TestJobsStreamAPI:
    async def test_stream_not_found(self, client):
        """GET /api/jobs/{id}/stream returns 404 for unknown jobs."""
        ac, repo, runner = client
        response = await ac.get("/api/jobs/nonexistent/stream")
        assert response.status_code == 404

    async def test_stream_completed_job(self, client):
        """GET /api/jobs/{id}/stream for completed job emits progress + done."""
        ac, repo, runner = client
        await repo.create(
            _make_job("j-done", status=JobStatus.COMPLETED, progress_pct=100)
        )
        await repo.update_status("j-done", JobStatus.COMPLETED, result={"ok": True})

        response = await ac.get("/api/jobs/j-done/stream")
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

        text = response.text
        assert "event: job_progress" in text
        assert "event: done" in text
