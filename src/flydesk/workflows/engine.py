# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Durable workflow execution engine backed by PostgreSQL."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from flydesk.workflows.models import (
    StepStatus,
    StepType,
    Trigger,
    TriggerType,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)
from flydesk.workflows.repository import WorkflowRepository

logger = logging.getLogger(__name__)


class WorkflowEngine:
    """Orchestrates durable workflow lifecycle: start, resume, cancel, and status queries."""

    def __init__(self, repo: WorkflowRepository) -> None:
        self._repo = repo

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
        now = datetime.now(timezone.utc)

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
        await self._repo.save_checkpoint(workflow_id, state=state)

    async def cancel(self, workflow_id: str) -> None:
        """Cancel a workflow, setting its status and completed_at timestamp."""
        await self._repo.update_status(
            workflow_id,
            WorkflowStatus.CANCELLED,
            completed_at=datetime.now(timezone.utc),
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
