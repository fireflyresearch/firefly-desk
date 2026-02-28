# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Integration test: full workflow lifecycle."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.models import (
    StepType,
    Trigger,
    TriggerType,
    WebhookRegistration,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
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


class TestWorkflowIntegration:
    async def test_full_workflow_lifecycle(self, engine, repo):
        """Create workflow -> add steps -> start -> webhook resume -> complete."""
        # 1. Create workflow with steps
        wf = await engine.start(
            workflow_type="vendor_onboard",
            params={"vendor_name": "Acme Corp"},
            user_id="user-1",
            conversation_id="conv-1",
            steps=[
                {"step_type": "tool_call", "description": "Create vendor record"},
                {"step_type": "wait_webhook", "description": "Wait for approval"},
                {"step_type": "notify", "description": "Send confirmation"},
            ],
        )
        assert wf.status == WorkflowStatus.PENDING
        steps = await repo.get_steps(wf.id)
        assert len(steps) == 3

        # 2. Resume with webhook trigger
        trigger = Trigger(
            trigger_type=TriggerType.WEBHOOK,
            step_index=1,
            payload={"approved": True},
        )
        await engine.resume(wf.id, trigger)
        result = await repo.get(wf.id)
        assert result.status == WorkflowStatus.RUNNING

        # 3. Cancel
        await engine.cancel(wf.id)
        result = await repo.get(wf.id)
        assert result.status == WorkflowStatus.CANCELLED

    async def test_webhook_registration_and_consume(self, repo):
        """Register a webhook -> look it up by token -> consume it."""
        reg = WebhookRegistration(
            id="wh-test-1",
            workflow_id="wf-1",
            step_index=1,
            webhook_token="unique-secret-token",
            external_system="jira",
            created_at=datetime.now(timezone.utc),
        )
        await repo.register_webhook(reg)

        found = await repo.get_webhook_by_token("unique-secret-token")
        assert found is not None
        assert found.external_system == "jira"

        await repo.consume_webhook("wh-test-1")
        found = await repo.get_webhook_by_token("unique-secret-token")
        assert found.status == "consumed"
