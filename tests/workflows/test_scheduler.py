# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for WorkflowScheduler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from flydesk.workflows.models import Workflow, WorkflowStatus
from flydesk.workflows.scheduler import WorkflowScheduler


class TestWorkflowScheduler:
    async def test_start_and_stop(self):
        repo = AsyncMock()
        engine = AsyncMock()
        repo.list_due_for_poll = AsyncMock(return_value=[])

        scheduler = WorkflowScheduler(repo, engine, interval_seconds=1)
        await scheduler.start()
        assert scheduler._running is True
        await scheduler.stop()
        assert scheduler._running is False

    async def test_tick_resumes_due_workflows(self):
        repo = AsyncMock()
        engine = AsyncMock()

        wf = Workflow(
            id="wf-due",
            user_id="u1",
            workflow_type="test",
            status=WorkflowStatus.WAITING,
            current_step=1,
            next_check_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            created_at=datetime.now(timezone.utc),
        )
        repo.list_due_for_poll = AsyncMock(return_value=[wf])

        scheduler = WorkflowScheduler(repo, engine, interval_seconds=60)
        await scheduler._tick()

        engine.resume.assert_called_once()
        call_args = engine.resume.call_args
        assert call_args[0][0] == "wf-due"
