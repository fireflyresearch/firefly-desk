# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Process execution engine -- bridges processes to workflows."""

from __future__ import annotations

import logging

from flydesk.processes.repository import ProcessRepository
from flydesk.workflows.engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ProcessExecutor:
    """Creates and starts a workflow from a process definition."""

    def __init__(self, process_repo: ProcessRepository, workflow_engine: WorkflowEngine) -> None:
        self._process_repo = process_repo
        self._workflow_engine = workflow_engine

    async def execute(
        self, process_id: str, params: dict, user_id: str
    ) -> str:
        """Create workflow from process, return workflow_id."""
        process = await self._process_repo.get(process_id)
        if process is None:
            raise ValueError(f"Process {process_id} not found")

        steps = [self._map_step(s) for s in (process.steps or [])]
        workflow = await self._workflow_engine.start(
            workflow_type=f"process:{process.name}",
            params=params,
            user_id=user_id,
            steps=steps,
        )
        logger.info("Started workflow %s for process %s", workflow.id, process_id)
        return workflow.id

    @staticmethod
    def _map_step_type(process_step_type: str) -> str:
        """Map a process step_type string to a valid workflow StepType value."""
        mapping = {
            "action": "agent_run",
            "decision": "condition",
            "wait": "wait_human",
            "notification": "notify",
            "api_call": "tool_call",
        }
        return mapping.get(process_step_type, "agent_run")

    def _map_step(self, process_step) -> dict:
        """Map a process step definition to a workflow step spec."""
        step_type = self._map_step_type(process_step.step_type)
        return {
            "step_type": step_type,
            "description": process_step.description or process_step.name,
            "input": {
                "system_id": process_step.system_id,
                "endpoint_id": process_step.endpoint_id,
                "inputs": process_step.inputs,
                "outputs": process_step.outputs,
            },
        }
