# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Durable workflow execution engine backed by PostgreSQL."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from flydesk.workflows.models import (
    StepStatus,
    StepType,
    Trigger,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from flydesk.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)

# A step handler takes (step, workflow) and returns a result dict.
StepHandler = Callable[[WorkflowStep, Workflow], Awaitable[dict]]


class WorkflowEngine:
    """Orchestrates durable workflow lifecycle: start, resume, cancel, and status queries."""

    def __init__(
        self,
        repo: WorkflowRepository,
        step_handlers: dict[str, StepHandler] | None = None,
    ) -> None:
        self._repo = repo
        self._step_handlers: dict[str, StepHandler] = step_handlers or {}

    async def start(
        self,
        workflow_type: str,
        params: dict,
        user_id: str,
        conversation_id: str | None = None,
        workspace_id: str | None = None,
        steps: list[dict] | None = None,
    ) -> Workflow:
        """Create a new workflow with optional pre-defined steps."""
        workflow_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        wf = Workflow(
            id=workflow_id,
            conversation_id=conversation_id,
            user_id=user_id,
            workspace_id=workspace_id,
            workflow_type=workflow_type,
            status=WorkflowStatus.PENDING,
            state=params,
            created_at=now,
        )
        await self._repo.create(wf)

        if steps:
            for i, step_def in enumerate(steps):
                step = WorkflowStep(
                    id=str(uuid.uuid4()),
                    workflow_id=workflow_id,
                    step_index=i,
                    step_type=StepType(step_def["step_type"]),
                    description=step_def.get("description", ""),
                    input=step_def.get("input"),
                )
                await self._repo.create_step(step)

        logger.info(
            "Workflow %s (%s) created with %d steps",
            workflow_id,
            workflow_type,
            len(steps or []),
        )
        return wf

    @staticmethod
    def _check_condition(state: dict, condition: dict) -> int:
        """Check condition expression and return target step index.

        Uses simple field comparison -- no dynamic code interpretation.
        Supported operators: eq, ne, gt, lt, gte, lte, in, contains.
        """
        field_path = condition["field"]
        # Resolve "state.field_name" to actual value
        parts = field_path.split(".")
        value = state
        for part in parts:
            if part == "state":
                continue
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = getattr(value, part, None)

        op = condition["operator"]
        expected = condition["value"]
        then_step = condition["then_step"]
        else_step = condition["else_step"]

        comparisons = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "lt": lambda a, b: a < b,
            "gte": lambda a, b: a >= b,
            "lte": lambda a, b: a <= b,
            "in": lambda a, b: a in b,
            "contains": lambda a, b: b in a if isinstance(a, (list, str)) else False,
        }

        check = comparisons.get(op, lambda a, b: False)
        return then_step if check(value, expected) else else_step

    async def resume(self, workflow_id: str, trigger: Trigger) -> None:
        """Resume a waiting or pending workflow with the given trigger."""
        wf = await self._repo.get(workflow_id)
        if wf is None:
            logger.warning("Workflow %s not found for resume", workflow_id)
            return

        if wf.status not in (WorkflowStatus.WAITING, WorkflowStatus.PENDING):
            logger.warning(
                "Workflow %s in non-resumable status: %s", workflow_id, wf.status
            )
            return

        await self._repo.update_status(workflow_id, WorkflowStatus.RUNNING)

        state = dict(wf.state)
        state[f"trigger_{wf.current_step}"] = trigger.payload
        wf.state = state  # keep in-memory copy in sync for step execution
        await self._repo.save_checkpoint(workflow_id, state=state)

        # Execute the current step with timeout enforcement
        steps = await self._repo.get_steps(workflow_id)
        if wf.current_step < len(steps):
            step = steps[wf.current_step]

            # Handle CONDITION steps by evaluating the branch immediately
            if step.step_type == StepType.CONDITION:
                condition = step.input or {}
                target_step = self._check_condition(state, condition)
                await self._repo.update_step_status(
                    step.id,
                    StepStatus.COMPLETED,
                    output={"target_step": target_step},
                    completed_at=datetime.now(UTC),
                )
                await self._repo.save_checkpoint(
                    workflow_id, current_step=target_step
                )
                logger.info(
                    "Condition step %d branched to step %d",
                    wf.current_step,
                    target_step,
                )
                return

            await self._run_step_with_timeout(step, wf)

    async def _execute_step(self, step: WorkflowStep, workflow: Workflow) -> dict:
        """Execute a single workflow step using registered handlers.

        Dispatches to the handler registered for ``step.step_type``.
        Steps of type ``wait_webhook`` / ``wait_human`` / ``wait_poll``
        transition to WAITING without executing — they resume on trigger.
        """
        await self._repo.update_step_status(
            step.id,
            StepStatus.RUNNING,
            started_at=datetime.now(UTC),
        )

        # Wait-type steps: when being *resumed* (trigger arrived), the step
        # is done.  When first encountered during auto-advance, they pause.
        if step.step_type in (
            StepType.WAIT_WEBHOOK,
            StepType.WAIT_HUMAN,
            StepType.WAIT_POLL,
        ):
            # Check if a trigger payload exists for this step (set by resume())
            trigger_key = f"trigger_{step.step_index}"
            if trigger_key in (workflow.state or {}):
                # Trigger already received — the wait is satisfied
                return {"status": "completed", "trigger": workflow.state[trigger_key]}
            # No trigger yet — pause
            await self._repo.update_step_status(step.id, StepStatus.WAITING)
            await self._repo.update_status(workflow.id, WorkflowStatus.WAITING)
            logger.info("Step %s (%s) waiting for trigger", step.id, step.step_type)
            return {"status": "waiting"}

        handler = self._step_handlers.get(step.step_type.value)
        if handler is None:
            logger.warning(
                "No handler registered for step type '%s', skipping step %s",
                step.step_type,
                step.id,
            )
            return {"status": "skipped", "reason": f"no handler for {step.step_type}"}

        return await handler(step, workflow)

    async def _run_step_with_timeout(
        self, step: WorkflowStep, workflow: Workflow
    ) -> None:
        """Wrap step execution in asyncio.wait_for with retry on timeout."""
        timeout = step.timeout_seconds if hasattr(step, "timeout_seconds") else 300
        max_retries = step.max_retries if hasattr(step, "max_retries") else 0
        retry_count = step.retry_count if hasattr(step, "retry_count") else 0

        try:
            result = await asyncio.wait_for(
                self._execute_step(step, workflow),
                timeout=timeout,
            )

            # If the step transitioned to WAITING, don't mark completed
            if result.get("status") == "waiting":
                return

            await self._repo.update_step_status(
                step.id,
                StepStatus.COMPLETED,
                output=result,
                completed_at=datetime.now(UTC),
            )

            # Advance to next step
            await self._advance_workflow(workflow)

        except TimeoutError:
            retry_count += 1
            if retry_count < max_retries:
                backoff = min(30 * (2 ** retry_count), 3600)
                # Reschedule the workflow for retry
                await self._repo.save_checkpoint(
                    workflow.id,
                    next_check_at=datetime.now(UTC) + timedelta(seconds=backoff),
                )
                await self._repo.update_step_status(
                    step.id,
                    StepStatus.PENDING,
                )
                await self._repo.update_status(
                    workflow.id, WorkflowStatus.WAITING
                )
                logger.warning(
                    "Step %s timed out, retry %d/%d (backoff %ds)",
                    step.id, retry_count, max_retries, backoff,
                )
            else:
                error_msg = (
                    f"Timed out after {timeout}s "
                    f"(exhausted {max_retries} retries)"
                )
                await self._repo.update_step_status(
                    step.id,
                    StepStatus.FAILED,
                    error=error_msg,
                    completed_at=datetime.now(UTC),
                )
                await self._repo.update_status(
                    workflow.id,
                    WorkflowStatus.FAILED,
                    error=error_msg,
                    completed_at=datetime.now(UTC),
                )
                logger.error("Step %s failed after all retries", step.id)

    async def _advance_workflow(self, workflow: Workflow) -> None:
        """Move to the next step or complete the workflow."""
        steps = await self._repo.get_steps(workflow.id)
        next_step = workflow.current_step + 1

        if next_step >= len(steps):
            # All steps done
            await self._repo.update_status(
                workflow.id,
                WorkflowStatus.COMPLETED,
                completed_at=datetime.now(UTC),
            )
            logger.info("Workflow %s completed all %d steps", workflow.id, len(steps))
            return

        await self._repo.save_checkpoint(workflow.id, current_step=next_step)

        # Auto-execute next step if it's not a wait type
        next_step_obj = steps[next_step]
        if next_step_obj.step_type == StepType.CONDITION:
            state = (await self._repo.get(workflow.id)).state or {}
            target = self._check_condition(state, next_step_obj.input or {})
            await self._repo.update_step_status(
                next_step_obj.id,
                StepStatus.COMPLETED,
                output={"target_step": target},
                completed_at=datetime.now(UTC),
            )
            await self._repo.save_checkpoint(workflow.id, current_step=target)
            # Recurse to advance past the condition
            workflow.current_step = target
            await self._advance_workflow(workflow)
        elif next_step_obj.step_type not in (
            StepType.WAIT_WEBHOOK, StepType.WAIT_HUMAN, StepType.WAIT_POLL,
        ):
            # Continue executing automatically
            workflow.current_step = next_step
            await self._run_step_with_timeout(next_step_obj, workflow)
        else:
            # Wait-type step — set workflow to WAITING
            await self._repo.update_status(workflow.id, WorkflowStatus.WAITING)
            logger.info(
                "Workflow %s waiting at step %d (%s)",
                workflow.id, next_step, next_step_obj.step_type,
            )

    async def cancel(self, workflow_id: str) -> None:
        """Cancel a workflow, setting its status and completed_at timestamp."""
        await self._repo.update_status(
            workflow_id,
            WorkflowStatus.CANCELLED,
            completed_at=datetime.now(UTC),
        )

    async def get_status(self, workflow_id: str) -> dict[str, Any] | None:
        """Return a status summary dict for a workflow, or None if not found."""
        wf = await self._repo.get(workflow_id)
        if wf is None:
            return None

        steps = await self._repo.get_steps(workflow_id)
        return {
            "id": wf.id,
            "workflow_type": wf.workflow_type,
            "status": wf.status.value,
            "current_step": wf.current_step,
            "total_steps": len(steps),
            "created_at": wf.created_at.isoformat(),
            "started_at": wf.started_at.isoformat() if wf.started_at else None,
            "completed_at": wf.completed_at.isoformat() if wf.completed_at else None,
            "error": wf.error,
        }
