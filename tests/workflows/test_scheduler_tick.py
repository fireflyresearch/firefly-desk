"""Tests for WorkflowScheduler tick logic, polling, and error recovery."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from flydesk.workflows.models import Trigger, TriggerType, Workflow, WorkflowStatus
from flydesk.workflows.scheduler import WorkflowScheduler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_workflow(**overrides) -> Workflow:
    defaults = dict(
        id="wf-1",
        user_id="u1",
        workflow_type="test",
        status=WorkflowStatus.WAITING,
        current_step=0,
        created_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return Workflow(**defaults)


def _make_scheduler(
    repo: AsyncMock | None = None,
    engine: AsyncMock | None = None,
    interval: int = 60,
) -> tuple[WorkflowScheduler, AsyncMock, AsyncMock]:
    repo = repo or AsyncMock()
    engine = engine or AsyncMock()
    repo.list_due_for_poll = repo.list_due_for_poll or AsyncMock(return_value=[])
    scheduler = WorkflowScheduler(repo, engine, interval_seconds=interval)
    return scheduler, repo, engine


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------

class TestTick:
    async def test_tick_no_due_workflows_is_noop(self):
        """When no workflows are due, tick does nothing."""
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[])

        await scheduler._tick()

        repo.list_due_for_poll.assert_awaited_once()
        engine.resume.assert_not_called()

    async def test_tick_resumes_single_due_workflow(self):
        """Tick resumes a single due workflow with POLL trigger."""
        wf = _make_workflow(id="wf-due", current_step=2)
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[wf])

        await scheduler._tick()

        engine.resume.assert_awaited_once()
        call_args = engine.resume.call_args
        assert call_args[0][0] == "wf-due"
        trigger = call_args[0][1]
        assert isinstance(trigger, Trigger)
        assert trigger.trigger_type == TriggerType.POLL
        assert trigger.step_index == 2

    async def test_tick_resumes_multiple_due_workflows(self):
        """Tick resumes all due workflows in order."""
        wf1 = _make_workflow(id="wf-1", current_step=0)
        wf2 = _make_workflow(id="wf-2", current_step=3)
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[wf1, wf2])

        await scheduler._tick()

        assert engine.resume.await_count == 2
        ids_called = [c[0][0] for c in engine.resume.call_args_list]
        assert ids_called == ["wf-1", "wf-2"]

    async def test_tick_trigger_step_index_matches_current_step(self):
        """The trigger's step_index must match the workflow's current_step."""
        wf = _make_workflow(current_step=5)
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[wf])

        await scheduler._tick()

        trigger = engine.resume.call_args[0][1]
        assert trigger.step_index == 5


# ---------------------------------------------------------------------------
# Error recovery
# ---------------------------------------------------------------------------

class TestErrorRecovery:
    async def test_tick_exception_does_not_crash_loop(self):
        """If _tick raises, the _loop method catches it and continues."""
        scheduler, repo, engine = _make_scheduler(interval=0)
        scheduler._running = True  # Must be True for _loop to iterate
        call_count = 0

        async def failing_tick():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("db error")
            # Stop the loop on second call
            scheduler._running = False

        scheduler._tick = failing_tick

        with patch("flydesk.workflows.scheduler.asyncio.sleep", new_callable=AsyncMock):
            await scheduler._loop()

        # tick was called at least twice (first fails, second stops)
        assert call_count >= 2

    async def test_engine_resume_error_propagates_in_tick(self):
        """If engine.resume raises inside _tick, the exception propagates up."""
        wf = _make_workflow()
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[wf])
        engine.resume = AsyncMock(side_effect=RuntimeError("engine failed"))

        with pytest.raises(RuntimeError, match="engine failed"):
            await scheduler._tick()


# ---------------------------------------------------------------------------
# Start / Stop lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    async def test_custom_interval(self):
        """Scheduler stores the configured interval."""
        scheduler, _, _ = _make_scheduler(interval=120)
        assert scheduler._interval == 120

    async def test_start_sets_running_and_creates_task(self):
        """start() sets _running and creates a background task."""
        scheduler, repo, engine = _make_scheduler()
        repo.list_due_for_poll = AsyncMock(return_value=[])

        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._task is not None

        await scheduler.stop()
        assert scheduler._running is False
        assert scheduler._task is None
