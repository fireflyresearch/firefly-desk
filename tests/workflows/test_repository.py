# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for WorkflowRepository -- CRUD operations on workflows, steps, and webhooks."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.workflows.models import (
    StepStatus,
    StepType,
    WebhookRegistration,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from flydesk.workflows.repository import WorkflowRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _make_workflow(**overrides) -> Workflow:
    defaults = dict(
        id=str(uuid.uuid4()),
        user_id="user-1",
        workflow_type="email_send",
        status=WorkflowStatus.PENDING,
        state={},
        created_at=_utcnow(),
    )
    defaults.update(overrides)
    return Workflow(**defaults)


def _make_step(workflow_id: str, index: int = 0, **overrides) -> WorkflowStep:
    defaults = dict(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        step_index=index,
        step_type=StepType.AGENT_RUN,
        description=f"Step {index}",
        status=StepStatus.PENDING,
    )
    defaults.update(overrides)
    return WorkflowStep(**defaults)


def _make_webhook(workflow_id: str, **overrides) -> WebhookRegistration:
    defaults = dict(
        id=str(uuid.uuid4()),
        workflow_id=workflow_id,
        step_index=0,
        webhook_token=str(uuid.uuid4()),
        status="active",
        created_at=_utcnow(),
    )
    defaults.update(overrides)
    return WebhookRegistration(**defaults)


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
    return WorkflowRepository(session_factory)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestWorkflowRepository:
    # -- Workflow CRUD -------------------------------------------------------

    async def test_create_and_get_workflow(self, repo):
        """A persisted workflow can be retrieved by ID."""
        wf = _make_workflow(conversation_id="conv-1", state={"key": "val"})
        await repo.create(wf)

        fetched = await repo.get(wf.id)
        assert fetched is not None
        assert fetched.id == wf.id
        assert fetched.user_id == "user-1"
        assert fetched.workflow_type == "email_send"
        assert fetched.status == WorkflowStatus.PENDING
        assert fetched.conversation_id == "conv-1"
        assert fetched.state == {"key": "val"}

    async def test_get_returns_none_for_unknown_id(self, repo):
        """get() returns None when the workflow does not exist."""
        assert await repo.get("nonexistent") is None

    async def test_update_status_to_running(self, repo):
        """update_status sets the status and started_at timestamp."""
        wf = _make_workflow()
        await repo.create(wf)

        now = _utcnow()
        await repo.update_status(wf.id, WorkflowStatus.RUNNING, started_at=now)

        fetched = await repo.get(wf.id)
        assert fetched is not None
        assert fetched.status == WorkflowStatus.RUNNING
        assert fetched.started_at is not None

    async def test_update_status_to_failed_with_error(self, repo):
        """update_status records error message and completed_at."""
        wf = _make_workflow(status=WorkflowStatus.RUNNING)
        await repo.create(wf)

        now = _utcnow()
        await repo.update_status(
            wf.id, WorkflowStatus.FAILED, error="boom", completed_at=now
        )

        fetched = await repo.get(wf.id)
        assert fetched is not None
        assert fetched.status == WorkflowStatus.FAILED
        assert fetched.error == "boom"
        assert fetched.completed_at is not None

    async def test_update_status_with_result(self, repo):
        """update_status can attach a result dict."""
        wf = _make_workflow(status=WorkflowStatus.RUNNING)
        await repo.create(wf)

        await repo.update_status(
            wf.id, WorkflowStatus.COMPLETED, result={"answer": 42}, completed_at=_utcnow()
        )

        fetched = await repo.get(wf.id)
        assert fetched is not None
        assert fetched.result == {"answer": 42}

    # -- Listing & filtering --------------------------------------------------

    async def test_list_by_status(self, repo):
        """list() filters workflows by status."""
        wf_pending = _make_workflow(status=WorkflowStatus.PENDING)
        wf_running = _make_workflow(status=WorkflowStatus.RUNNING)
        await repo.create(wf_pending)
        await repo.create(wf_running)

        results = await repo.list(status=WorkflowStatus.PENDING)
        assert len(results) == 1
        assert results[0].id == wf_pending.id

    async def test_list_by_user_id(self, repo):
        """list() filters workflows by user_id."""
        wf_a = _make_workflow(user_id="alice")
        wf_b = _make_workflow(user_id="bob")
        await repo.create(wf_a)
        await repo.create(wf_b)

        results = await repo.list(user_id="alice")
        assert len(results) == 1
        assert results[0].user_id == "alice"

    async def test_list_by_conversation_id(self, repo):
        """list() filters workflows by conversation_id."""
        wf1 = _make_workflow(conversation_id="conv-1")
        wf2 = _make_workflow(conversation_id="conv-2")
        await repo.create(wf1)
        await repo.create(wf2)

        results = await repo.list(conversation_id="conv-1")
        assert len(results) == 1
        assert results[0].conversation_id == "conv-1"

    # -- Polling --------------------------------------------------------------

    async def test_list_due_for_poll(self, repo):
        """list_due_for_poll returns WAITING workflows whose next_check_at is past."""
        past = _utcnow() - timedelta(minutes=5)
        future = _utcnow() + timedelta(hours=1)

        wf_due = _make_workflow(status=WorkflowStatus.WAITING, next_check_at=past)
        wf_not_due = _make_workflow(status=WorkflowStatus.WAITING, next_check_at=future)
        wf_wrong_status = _make_workflow(status=WorkflowStatus.RUNNING, next_check_at=past)

        await repo.create(wf_due)
        await repo.create(wf_not_due)
        await repo.create(wf_wrong_status)

        due = await repo.list_due_for_poll()
        assert len(due) == 1
        assert due[0].id == wf_due.id

    # -- Steps -----------------------------------------------------------------

    async def test_create_and_get_steps(self, repo):
        """Steps are persisted and returned in step_index order."""
        wf = _make_workflow()
        await repo.create(wf)

        step_1 = _make_step(wf.id, index=1, description="Second")
        step_0 = _make_step(wf.id, index=0, description="First")
        await repo.create_step(step_1)
        await repo.create_step(step_0)

        steps = await repo.get_steps(wf.id)
        assert len(steps) == 2
        assert steps[0].step_index == 0
        assert steps[0].description == "First"
        assert steps[1].step_index == 1
        assert steps[1].description == "Second"

    async def test_update_step_status_with_output(self, repo):
        """update_step_status sets status, output, and timestamps."""
        wf = _make_workflow()
        await repo.create(wf)

        step = _make_step(wf.id, index=0)
        await repo.create_step(step)

        now = _utcnow()
        await repo.update_step_status(
            step.id,
            StepStatus.COMPLETED,
            output={"data": "result"},
            started_at=now,
            completed_at=now,
        )

        steps = await repo.get_steps(wf.id)
        assert len(steps) == 1
        assert steps[0].status == StepStatus.COMPLETED
        assert steps[0].output == {"data": "result"}
        assert steps[0].started_at is not None
        assert steps[0].completed_at is not None

    # -- Webhooks --------------------------------------------------------------

    async def test_register_and_get_webhook(self, repo):
        """A registered webhook can be retrieved by token."""
        wf = _make_workflow()
        await repo.create(wf)

        hook = _make_webhook(wf.id, external_system="stripe")
        await repo.register_webhook(hook)

        fetched = await repo.get_webhook_by_token(hook.webhook_token)
        assert fetched is not None
        assert fetched.id == hook.id
        assert fetched.workflow_id == wf.id
        assert fetched.external_system == "stripe"
        assert fetched.status == "active"

    async def test_get_webhook_by_token_returns_none_for_unknown(self, repo):
        """get_webhook_by_token returns None for an unregistered token."""
        result = await repo.get_webhook_by_token("unknown-token")
        assert result is None

    async def test_consume_webhook(self, repo):
        """consume_webhook sets the webhook status to 'consumed'."""
        wf = _make_workflow()
        await repo.create(wf)

        hook = _make_webhook(wf.id)
        await repo.register_webhook(hook)

        await repo.consume_webhook(hook.id)

        fetched = await repo.get_webhook_by_token(hook.webhook_token)
        assert fetched is not None
        assert fetched.status == "consumed"

    # -- Checkpointing ---------------------------------------------------------

    async def test_save_checkpoint(self, repo):
        """save_checkpoint updates current_step, state, and next_check_at."""
        wf = _make_workflow(state={"old": True})
        await repo.create(wf)

        future = _utcnow() + timedelta(minutes=30)
        await repo.save_checkpoint(
            wf.id,
            current_step=2,
            state={"new": True},
            next_check_at=future,
        )

        fetched = await repo.get(wf.id)
        assert fetched is not None
        assert fetched.current_step == 2
        assert fetched.state == {"new": True}
        assert fetched.next_check_at is not None
