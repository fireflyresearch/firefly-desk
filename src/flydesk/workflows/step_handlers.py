# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Concrete step handlers for the workflow execution engine."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.callbacks.dispatcher import CallbackDispatcher
    from flydesk.tools.executor import ToolExecutor
    from flydesk.workflows.models import Workflow, WorkflowStep

logger = logging.getLogger(__name__)


async def handle_agent_run(step: WorkflowStep, workflow: Workflow) -> dict:
    """Execute an agent_run step -- sends the step description to the LLM agent.

    Requires ``_agent_factory`` to be set on the function via :func:`create_handlers`.
    """
    factory: DeskAgentFactory = handle_agent_run._agent_factory  # type: ignore[attr-defined]
    prompt = step.description or "Execute the next step in this workflow."

    # Include workflow state as context
    context_parts = [prompt]
    if workflow.state:
        context_parts.append(f"\nWorkflow state: {workflow.state}")
    if step.input:
        context_parts.append(f"\nStep input: {step.input}")

    full_prompt = "\n".join(context_parts)

    try:
        agent = await factory.create_agent(
            "You are a workflow step executor. Complete the requested task and return "
            "a JSON summary of the result.",
        )
        if agent is None:
            return {"status": "skipped", "reason": "no LLM provider configured"}

        result = await agent.run(full_prompt)
        output_text = str(result.output)
        return {"status": "completed", "output": output_text[:10_000]}
    except Exception as exc:
        logger.exception("agent_run step %s failed", step.id)
        raise RuntimeError(f"Agent run failed: {exc}") from exc


async def handle_tool_call(step: WorkflowStep, workflow: Workflow) -> dict:
    """Execute a tool_call step -- invokes an external API endpoint.

    Requires ``_tool_executor`` to be set on the function via :func:`create_handlers`.
    """
    executor: ToolExecutor = handle_tool_call._tool_executor  # type: ignore[attr-defined]
    step_input = step.input or {}
    endpoint_id = step_input.get("endpoint_id")

    if not endpoint_id:
        return {"status": "skipped", "reason": "no endpoint_id in step input"}

    from flydesk.tools.executor import ToolCall

    call = ToolCall(
        call_id=step.id,
        tool_name=step.description or "workflow_step",
        endpoint_id=endpoint_id,
        arguments=step_input.get("arguments", {}),
    )

    results = await executor.execute_sequential([call], user_session=None, conversation_id="")
    if results and results[0].success:
        return {"status": "completed", "data": results[0].data}
    elif results:
        return {"status": "failed", "error": str(results[0].data)}
    return {"status": "failed", "error": "no result from tool executor"}


async def handle_notify(step: WorkflowStep, workflow: Workflow) -> dict:
    """Execute a notify step -- dispatches a callback event.

    Requires ``_callback_dispatcher`` to be set on the function via :func:`create_handlers`.
    """
    dispatcher: CallbackDispatcher | None = handle_notify._callback_dispatcher  # type: ignore[attr-defined]
    step_input = step.input or {}
    message = step.description or "Workflow notification"

    if dispatcher is None:
        logger.info("Notify step %s: no dispatcher configured, logging only", step.id)
        return {"status": "completed", "message": message}

    try:
        await dispatcher.dispatch(
            "workflow.notify",
            {
                "workflow_id": workflow.id,
                "step_id": step.id,
                "message": message,
                **step_input,
            },
        )
        return {"status": "completed", "message": message}
    except Exception as exc:
        logger.warning("Notify dispatch failed for step %s: %s", step.id, exc)
        return {"status": "completed", "message": message, "dispatch_error": str(exc)}


def create_handlers(
    *,
    agent_factory: DeskAgentFactory | None = None,
    tool_executor: ToolExecutor | None = None,
    callback_dispatcher: Any | None = None,
) -> dict[str, Any]:
    """Build a step handler registry from available dependencies.

    Only registers handlers for which the required dependency is available.
    """
    handlers: dict[str, Any] = {}

    if agent_factory is not None:
        handle_agent_run._agent_factory = agent_factory  # type: ignore[attr-defined]
        handlers["agent_run"] = handle_agent_run

    if tool_executor is not None:
        handle_tool_call._tool_executor = tool_executor  # type: ignore[attr-defined]
        handlers["tool_call"] = handle_tool_call

    handle_notify._callback_dispatcher = callback_dispatcher  # type: ignore[attr-defined]
    handlers["notify"] = handle_notify

    return handlers
