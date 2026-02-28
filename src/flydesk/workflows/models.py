# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for durable workflows."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class WorkflowStatus(StrEnum):
    """Possible states for a workflow."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(StrEnum):
    """Types of workflow steps."""

    AGENT_RUN = "agent_run"
    TOOL_CALL = "tool_call"
    WAIT_WEBHOOK = "wait_webhook"
    WAIT_POLL = "wait_poll"
    WAIT_HUMAN = "wait_human"
    NOTIFY = "notify"


class StepStatus(StrEnum):
    """Possible states for a workflow step."""

    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep(BaseModel):
    """A single step within a workflow."""

    id: str
    workflow_id: str
    step_index: int
    step_type: StepType
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    input: dict | None = None
    output: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class Workflow(BaseModel):
    """Domain representation of a durable workflow."""

    id: str
    conversation_id: str | None = None
    user_id: str
    workspace_id: str | None = None
    workflow_type: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: int = 0
    state: dict = Field(default_factory=dict)
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_check_at: datetime | None = None
    steps: list[WorkflowStep] = Field(default_factory=list)


class WebhookRegistration(BaseModel):
    """Tracks a webhook registered for a workflow step."""

    id: str
    workflow_id: str
    step_index: int
    webhook_token: str
    external_system: str | None = None
    status: str = "active"
    expires_at: datetime | None = None
    created_at: datetime


class TriggerType(StrEnum):
    """Types of events that can resume a workflow."""

    STEP_COMPLETE = "step_complete"
    WEBHOOK = "webhook"
    POLL = "poll"
    HUMAN_INPUT = "human_input"
    TIMER = "timer"


class Trigger(BaseModel):
    """An event that advances a workflow."""

    trigger_type: TriggerType
    step_index: int | None = None
    payload: dict = Field(default_factory=dict)
