# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for durable workflows, steps, and webhooks."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.workflow import WorkflowRow, WorkflowStepRow, WorkflowWebhookRow
from flydesk.workflows.models import (
    StepStatus,
    StepType,
    WebhookRegistration,
    Workflow,
    WorkflowStatus,
    WorkflowStep,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON helpers (same pattern as jobs.repository)
# ---------------------------------------------------------------------------

def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> dict | list | None:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


class WorkflowRepository:
    """CRUD operations for workflows, steps, and webhook registrations."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- Workflow CRUD -------------------------------------------------------

    async def create(self, wf: Workflow) -> None:
        """Persist a new workflow record."""
        async with self._session_factory() as session:
            row = WorkflowRow(
                id=wf.id,
                conversation_id=wf.conversation_id,
                user_id=wf.user_id,
                workspace_id=wf.workspace_id,
                workflow_type=wf.workflow_type,
                status=wf.status.value,
                current_step=wf.current_step,
                state_json=_to_json(wf.state),
                result_json=_to_json(wf.result),
                error=wf.error,
                created_at=wf.created_at,
                started_at=wf.started_at,
                completed_at=wf.completed_at,
                next_check_at=wf.next_check_at,
            )
            session.add(row)
            await session.commit()

    async def get(self, workflow_id: str) -> Workflow | None:
        """Retrieve a workflow by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(WorkflowRow, workflow_id)
            if row is None:
                return None
            return self._row_to_workflow(row)

    async def list(
        self,
        *,
        user_id: str | None = None,
        status: WorkflowStatus | None = None,
        conversation_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Workflow]:
        """Return workflows, optionally filtered, most recent first."""
        async with self._session_factory() as session:
            stmt = select(WorkflowRow)
            if user_id is not None:
                stmt = stmt.where(WorkflowRow.user_id == user_id)
            if status is not None:
                stmt = stmt.where(WorkflowRow.status == status.value)
            if conversation_id is not None:
                stmt = stmt.where(WorkflowRow.conversation_id == conversation_id)
            stmt = stmt.order_by(WorkflowRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._row_to_workflow(r) for r in result.scalars().all()]

    async def list_due_for_poll(self) -> list[Workflow]:
        """Return WAITING workflows whose next_check_at is in the past."""
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            stmt = (
                select(WorkflowRow)
                .where(
                    WorkflowRow.status == WorkflowStatus.WAITING.value,
                    WorkflowRow.next_check_at <= now,
                )
                .order_by(WorkflowRow.next_check_at.asc())
            )
            result = await session.execute(stmt)
            return [self._row_to_workflow(r) for r in result.scalars().all()]

    async def update_status(
        self,
        workflow_id: str,
        status: WorkflowStatus,
        *,
        error: str | None = None,
        result: dict | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update the status of a workflow, plus optional result/error/timestamps."""
        async with self._session_factory() as session:
            row = await session.get(WorkflowRow, workflow_id)
            if row is None:
                logger.warning("update_status: workflow %s not found", workflow_id)
                return
            row.status = status.value
            if error is not None:
                row.error = error
            if result is not None:
                row.result_json = _to_json(result)
            if started_at is not None:
                row.started_at = started_at
            if completed_at is not None:
                row.completed_at = completed_at
            await session.commit()

    async def save_checkpoint(
        self,
        workflow_id: str,
        *,
        current_step: int | None = None,
        state: dict | None = None,
        next_check_at: datetime | None = None,
    ) -> None:
        """Update checkpoint fields: current_step, state, and next_check_at."""
        async with self._session_factory() as session:
            row = await session.get(WorkflowRow, workflow_id)
            if row is None:
                logger.warning("save_checkpoint: workflow %s not found", workflow_id)
                return
            if current_step is not None:
                row.current_step = current_step
            if state is not None:
                row.state_json = _to_json(state)
            if next_check_at is not None:
                row.next_check_at = next_check_at
            await session.commit()

    # -- Steps ----------------------------------------------------------------

    async def create_step(self, step: WorkflowStep) -> None:
        """Persist a new workflow step."""
        async with self._session_factory() as session:
            row = WorkflowStepRow(
                id=step.id,
                workflow_id=step.workflow_id,
                step_index=step.step_index,
                step_type=step.step_type.value,
                description=step.description,
                status=step.status.value,
                input_json=_to_json(step.input),
                output_json=_to_json(step.output),
                error=step.error,
                started_at=step.started_at,
                completed_at=step.completed_at,
            )
            session.add(row)
            await session.commit()

    async def get_steps(self, workflow_id: str) -> list[WorkflowStep]:
        """Return all steps for a workflow, ordered by step_index."""
        async with self._session_factory() as session:
            stmt = (
                select(WorkflowStepRow)
                .where(WorkflowStepRow.workflow_id == workflow_id)
                .order_by(WorkflowStepRow.step_index.asc())
            )
            result = await session.execute(stmt)
            return [self._row_to_step(r) for r in result.scalars().all()]

    async def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        *,
        output: dict | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update the status of a workflow step, plus optional output/error/timestamps."""
        async with self._session_factory() as session:
            row = await session.get(WorkflowStepRow, step_id)
            if row is None:
                logger.warning("update_step_status: step %s not found", step_id)
                return
            row.status = status.value
            if output is not None:
                row.output_json = _to_json(output)
            if error is not None:
                row.error = error
            if started_at is not None:
                row.started_at = started_at
            if completed_at is not None:
                row.completed_at = completed_at
            await session.commit()

    # -- Webhooks --------------------------------------------------------------

    async def register_webhook(self, reg: WebhookRegistration) -> None:
        """Persist a new webhook registration."""
        async with self._session_factory() as session:
            row = WorkflowWebhookRow(
                id=reg.id,
                workflow_id=reg.workflow_id,
                step_index=reg.step_index,
                webhook_token=reg.webhook_token,
                external_system=reg.external_system,
                status=reg.status,
                expires_at=reg.expires_at,
                created_at=reg.created_at,
            )
            session.add(row)
            await session.commit()

    async def get_webhook_by_token(self, token: str) -> WebhookRegistration | None:
        """Look up a webhook registration by its unique token."""
        async with self._session_factory() as session:
            stmt = select(WorkflowWebhookRow).where(
                WorkflowWebhookRow.webhook_token == token
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_webhook(row)

    async def consume_webhook(self, webhook_id: str) -> None:
        """Set a webhook's status to ``consumed``."""
        async with self._session_factory() as session:
            row = await session.get(WorkflowWebhookRow, webhook_id)
            if row is None:
                logger.warning("consume_webhook: webhook %s not found", webhook_id)
                return
            row.status = "consumed"
            await session.commit()

    # -- Row converters --------------------------------------------------------

    @staticmethod
    def _row_to_workflow(row: WorkflowRow) -> Workflow:
        return Workflow(
            id=row.id,
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            workspace_id=row.workspace_id,
            workflow_type=row.workflow_type,
            status=WorkflowStatus(row.status),
            current_step=row.current_step,
            state=_from_json(row.state_json) or {},
            result=_from_json(row.result_json),
            error=row.error,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            next_check_at=row.next_check_at,
        )

    @staticmethod
    def _row_to_step(row: WorkflowStepRow) -> WorkflowStep:
        return WorkflowStep(
            id=row.id,
            workflow_id=row.workflow_id,
            step_index=row.step_index,
            step_type=StepType(row.step_type),
            description=row.description,
            status=StepStatus(row.status),
            input=_from_json(row.input_json),
            output=_from_json(row.output_json),
            error=row.error,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )

    @staticmethod
    def _row_to_webhook(row: WorkflowWebhookRow) -> WebhookRegistration:
        return WebhookRegistration(
            id=row.id,
            workflow_id=row.workflow_id,
            step_index=row.step_index,
            webhook_token=row.webhook_token,
            external_system=row.external_system,
            status=row.status,
            expires_at=row.expires_at,
            created_at=row.created_at,
        )
