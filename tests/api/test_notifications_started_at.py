"""Tests for started_at in notification responses."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.models.base import Base
from flydesk.workflows.repository import WorkflowRepository


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_DEV_MODE": "true",
        "FLYDESK_AGENT_NAME": "Ember",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_job_repo, get_session_factory, get_workflow_repo
        from flydesk.server import create_app

        app = create_app()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sf = async_sessionmaker(engine, expire_on_commit=False)
        repo = JobRepository(sf)
        wf_repo = WorkflowRepository(sf)
        app.dependency_overrides[get_job_repo] = lambda: repo
        app.dependency_overrides[get_workflow_repo] = lambda: wf_repo
        app.dependency_overrides[get_session_factory] = lambda: sf
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, repo
        await engine.dispose()


class TestNotificationStartedAt:
    async def test_notification_includes_started_at(self, client):
        ac, repo = client
        now = datetime.now(timezone.utc)
        job = Job(
            id="j-1",
            job_type="indexing",
            status=JobStatus.RUNNING,
            created_at=now,
            started_at=now,
        )
        await repo.create(job)

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        notifs = response.json()["notifications"]
        assert len(notifs) == 1
        assert notifs[0]["started_at"] is not None
