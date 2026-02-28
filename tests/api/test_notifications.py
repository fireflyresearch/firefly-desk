# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Notifications REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from unittest.mock import patch

from flydesk.jobs.models import Job, JobStatus
from flydesk.jobs.repository import JobRepository
from flydesk.models.base import Base
from flydesk.workflows.models import Workflow, WorkflowStatus
from flydesk.workflows.repository import WorkflowRepository


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
        from flydesk.api.deps import get_job_repo, get_workflow_repo, get_session_factory
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        job_repo = JobRepository(session_factory)
        workflow_repo = WorkflowRepository(session_factory)

        app.dependency_overrides[get_job_repo] = lambda: job_repo
        app.dependency_overrides[get_workflow_repo] = lambda: workflow_repo
        app.dependency_overrides[get_session_factory] = lambda: session_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac, job_repo, workflow_repo

        await engine.dispose()


def _make_job(
    job_id: str = "j-1",
    job_type: str = "indexing",
    status: JobStatus = JobStatus.RUNNING,
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


def _make_workflow(
    wf_id: str = "wf-1",
    workflow_type: str = "approval",
    status: WorkflowStatus = WorkflowStatus.RUNNING,
    **kwargs,
) -> Workflow:
    now = datetime.now(timezone.utc)
    return Workflow(
        id=wf_id,
        user_id=kwargs.pop("user_id", "user-1"),
        workflow_type=workflow_type,
        status=status,
        created_at=kwargs.pop("created_at", now),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Tests - List Notifications
# ---------------------------------------------------------------------------


class TestListNotifications:
    async def test_list_notifications_empty(self, client):
        """GET /api/notifications returns empty list when no jobs or workflows exist."""
        ac, job_repo, wf_repo = client
        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        assert body["notifications"] == []

    async def test_list_notifications_returns_jobs(self, client):
        """GET /api/notifications includes jobs as notifications."""
        ac, job_repo, wf_repo = client
        await job_repo.create(_make_job("j-1", job_type="indexing", status=JobStatus.RUNNING))
        await job_repo.create(_make_job("j-2", job_type="process_discovery", status=JobStatus.COMPLETED))

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        assert len(body["notifications"]) == 2

        ids = {n["id"] for n in body["notifications"]}
        assert "j-1" in ids
        assert "j-2" in ids

    async def test_list_notifications_returns_workflows(self, client):
        """GET /api/notifications includes workflows as notifications."""
        ac, job_repo, wf_repo = client
        await wf_repo.create(_make_workflow("wf-1", workflow_type="approval", status=WorkflowStatus.RUNNING))

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        assert len(body["notifications"]) == 1
        assert body["notifications"][0]["id"] == "wf-1"
        assert body["notifications"][0]["type"] == "workflow"

    async def test_list_notifications_returns_combined(self, client):
        """GET /api/notifications returns both jobs and workflows combined."""
        ac, job_repo, wf_repo = client
        await job_repo.create(_make_job("j-1", job_type="indexing", status=JobStatus.RUNNING))
        await wf_repo.create(_make_workflow("wf-1", workflow_type="approval", status=WorkflowStatus.RUNNING))

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        assert len(body["notifications"]) == 2

        types = {n["type"] for n in body["notifications"]}
        assert "job" in types
        assert "workflow" in types

    async def test_list_notifications_shape(self, client):
        """Each notification has the expected fields."""
        ac, job_repo, wf_repo = client
        await job_repo.create(
            _make_job(
                "j-1",
                job_type="indexing",
                status=JobStatus.RUNNING,
                progress_pct=42,
                progress_message="Indexing documents...",
            )
        )

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        n = body["notifications"][0]
        assert n["id"] == "j-1"
        assert n["type"] == "job"
        assert n["title"] == "indexing"
        assert n["status"] == "running"
        assert n["progress"] == 42
        assert "created_at" in n
        assert "updated_at" in n

    async def test_list_notifications_limit(self, client):
        """GET /api/notifications respects the limit parameter."""
        ac, job_repo, wf_repo = client
        for i in range(5):
            await job_repo.create(_make_job(f"j-{i}", job_type="indexing"))

        response = await ac.get("/api/notifications", params={"limit": 2})
        assert response.status_code == 200
        body = response.json()
        assert len(body["notifications"]) == 2

    async def test_list_notifications_ordered_by_created_at_desc(self, client):
        """Notifications are ordered most recent first."""
        ac, job_repo, wf_repo = client
        t1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        await job_repo.create(_make_job("j-old", created_at=t1))
        await job_repo.create(_make_job("j-new", created_at=t2))

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        assert body["notifications"][0]["id"] == "j-new"
        assert body["notifications"][1]["id"] == "j-old"


# ---------------------------------------------------------------------------
# Tests - Dismiss Notification
# ---------------------------------------------------------------------------


class TestDismissNotification:
    async def test_dismiss_notification(self, client):
        """PATCH /api/notifications/{id}/dismiss marks a notification as dismissed."""
        ac, job_repo, wf_repo = client
        await job_repo.create(_make_job("j-1", job_type="indexing", status=JobStatus.RUNNING))

        response = await ac.patch("/api/notifications/j-1/dismiss")
        assert response.status_code == 200
        assert response.json()["dismissed"] is True

    async def test_dismissed_notification_excluded_from_list(self, client):
        """Dismissed notifications do not appear in the list."""
        ac, job_repo, wf_repo = client
        await job_repo.create(_make_job("j-1", job_type="indexing", status=JobStatus.RUNNING))
        await job_repo.create(_make_job("j-2", job_type="indexing", status=JobStatus.RUNNING))

        # Dismiss j-1
        await ac.patch("/api/notifications/j-1/dismiss")

        response = await ac.get("/api/notifications")
        assert response.status_code == 200
        body = response.json()
        ids = {n["id"] for n in body["notifications"]}
        assert "j-1" not in ids
        assert "j-2" in ids

    async def test_dismiss_nonexistent_notification(self, client):
        """PATCH /api/notifications/{id}/dismiss returns 404 for unknown notifications."""
        ac, job_repo, wf_repo = client
        response = await ac.patch("/api/notifications/nonexistent/dismiss")
        assert response.status_code == 404
