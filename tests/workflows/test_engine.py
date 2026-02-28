# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for WorkflowEngine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.models import StepType, Trigger, TriggerType, Workflow, WorkflowStatus
from flydesk.workflows.repository import WorkflowRepository


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
    return WorkflowRepository(session_factory)


@pytest.fixture
def engine(repo):
    return WorkflowEngine(repo)


class TestWorkflowEngine:
    async def test_start_creates_workflow(self, engine, repo):
        wf = await engine.start(
            workflow_type="test_flow",
            params={"key": "value"},
            user_id="user-1",
            conversation_id="conv-1",
            steps=[
                {
                    "step_type": "tool_call",
                    "description": "Call API",
                    "input": {"url": "/api/test"},
                },
            ],
        )
        assert wf.status == WorkflowStatus.PENDING
        assert wf.workflow_type == "test_flow"
        persisted = await repo.get(wf.id)
        assert persisted is not None
        steps = await repo.get_steps(wf.id)
        assert len(steps) == 1
        assert steps[0].step_type == StepType.TOOL_CALL

    async def test_start_with_no_steps(self, engine, repo):
        wf = await engine.start(workflow_type="empty", params={}, user_id="user-1")
        assert wf.status == WorkflowStatus.PENDING
        steps = await repo.get_steps(wf.id)
        assert len(steps) == 0

    async def test_cancel(self, engine, repo):
        wf = await engine.start(workflow_type="cancel_test", params={}, user_id="user-1")
        await engine.cancel(wf.id)
        result = await repo.get(wf.id)
        assert result.status == WorkflowStatus.CANCELLED

    async def test_get_status(self, engine, repo):
        wf = await engine.start(workflow_type="status_test", params={}, user_id="user-1")
        status = await engine.get_status(wf.id)
        assert status is not None
        assert status["status"] == "pending"

    async def test_get_status_unknown_returns_none(self, engine):
        result = await engine.get_status("nonexistent")
        assert result is None

    async def test_resume_sets_running(self, engine, repo):
        wf = await engine.start(
            workflow_type="resume_test",
            params={},
            user_id="user-1",
            steps=[{"step_type": "wait_webhook", "description": "Wait"}],
        )
        await repo.update_status(wf.id, WorkflowStatus.WAITING)
        trigger = Trigger(trigger_type=TriggerType.WEBHOOK, step_index=0, payload={"data": "test"})
        await engine.resume(wf.id, trigger)
        result = await repo.get(wf.id)
        assert result.status == WorkflowStatus.RUNNING

    async def test_resume_non_resumable_is_noop(self, engine, repo):
        wf = await engine.start(workflow_type="t", params={}, user_id="u1")
        await repo.update_status(wf.id, WorkflowStatus.COMPLETED)
        trigger = Trigger(trigger_type=TriggerType.WEBHOOK, step_index=0)
        await engine.resume(wf.id, trigger)
        result = await repo.get(wf.id)
        assert result.status == WorkflowStatus.COMPLETED  # unchanged
