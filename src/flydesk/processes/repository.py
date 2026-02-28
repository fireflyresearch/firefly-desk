# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for business processes."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.process import (
    BusinessProcessRow,
    ProcessDependencyRow,
    ProcessStepRow,
)
from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)

logger = logging.getLogger(__name__)


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> list | dict | None:
    """Deserialize a value that may be a JSON string (SQLite) or already a list/dict."""
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessRepository:
    """CRUD operations for business processes, steps, and dependencies."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Process CRUD
    # ------------------------------------------------------------------

    async def create(self, process: BusinessProcess) -> BusinessProcess:
        """Persist a new business process with its steps and dependencies."""
        now = _utcnow()
        async with self._session_factory() as session:
            row = BusinessProcessRow(
                id=process.id,
                name=process.name,
                description=process.description,
                category=process.category,
                workspace_id=process.workspace_id,
                source=process.source.value,
                confidence=process.confidence,
                status=process.status.value,
                tags_json=_to_json(process.tags),
                created_at=process.created_at or now,
                updated_at=process.updated_at or now,
            )
            # Add steps
            for step in process.steps:
                row.steps.append(self._step_to_row(step, process.id))
            # Add dependencies
            for dep in process.dependencies:
                row.dependencies.append(self._dep_to_row(dep, process.id))

            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_process(row)

    async def get(self, process_id: str) -> BusinessProcess | None:
        """Retrieve a business process by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(BusinessProcessRow, process_id)
            if row is None:
                return None
            return self._row_to_process(row)

    async def list(
        self,
        *,
        category: str | None = None,
        status: ProcessStatus | None = None,
        tag: str | None = None,
        workspace_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BusinessProcess]:
        """Return processes, optionally filtered, most recent first."""
        async with self._session_factory() as session:
            stmt = select(BusinessProcessRow)
            if category is not None:
                stmt = stmt.where(BusinessProcessRow.category == category)
            if status is not None:
                stmt = stmt.where(BusinessProcessRow.status == status.value)
            if workspace_id is not None:
                stmt = stmt.where(BusinessProcessRow.workspace_id == workspace_id)
            stmt = stmt.order_by(BusinessProcessRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            rows = result.scalars().unique().all()

            # Post-filter by tag in Python (JSON column not easily searchable in SQL)
            if tag is not None:
                filtered = []
                for r in rows:
                    tags = _from_json(r.tags_json) or []
                    if tag in tags:
                        filtered.append(r)
                rows = filtered

            return [self._row_to_process(r) for r in rows]

    async def update(self, process: BusinessProcess) -> BusinessProcess:
        """Update an existing business process (replaces steps and dependencies)."""
        async with self._session_factory() as session:
            row = await session.get(BusinessProcessRow, process.id)
            if row is None:
                raise ValueError(f"Process {process.id!r} not found")

            row.name = process.name
            row.description = process.description
            row.category = process.category
            row.workspace_id = process.workspace_id
            row.source = process.source.value
            row.confidence = process.confidence
            row.status = process.status.value
            row.tags_json = _to_json(process.tags)
            row.updated_at = _utcnow()

            # Replace steps: remove old, add new
            row.steps.clear()
            for step in process.steps:
                row.steps.append(self._step_to_row(step, process.id))

            # Replace dependencies: remove old, add new
            row.dependencies.clear()
            for dep in process.dependencies:
                row.dependencies.append(self._dep_to_row(dep, process.id))

            await session.commit()
            await session.refresh(row)
            return self._row_to_process(row)

    async def delete(self, process_id: str) -> bool:
        """Delete a process by ID. Returns ``True`` if it existed."""
        async with self._session_factory() as session:
            row = await session.get(BusinessProcessRow, process_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # ------------------------------------------------------------------
    # Step operations
    # ------------------------------------------------------------------

    async def update_step(self, process_id: str, step: ProcessStep) -> ProcessStep | None:
        """Add or update a single step within a process.

        If a step with the same ID exists it is updated in-place; otherwise
        a new step row is appended.  Returns the persisted step, or ``None``
        if the parent process does not exist.
        """
        async with self._session_factory() as session:
            row = await session.get(BusinessProcessRow, process_id)
            if row is None:
                return None

            # Look for existing step
            existing = None
            for s in row.steps:
                if s.id == step.id:
                    existing = s
                    break

            if existing is not None:
                existing.name = step.name
                existing.description = step.description
                existing.step_type = step.step_type
                existing.system_id = step.system_id
                existing.endpoint_id = step.endpoint_id
                existing.order = step.order
                existing.inputs_json = _to_json(step.inputs)
                existing.outputs_json = _to_json(step.outputs)
            else:
                row.steps.append(self._step_to_row(step, process_id))

            row.updated_at = _utcnow()
            await session.commit()
            return step

    async def delete_step(self, process_id: str, step_id: str) -> bool:
        """Delete a step and all dependencies referencing it."""
        async with self._session_factory() as session:
            row = await session.execute(
                select(ProcessStepRow).where(
                    ProcessStepRow.process_id == process_id,
                    ProcessStepRow.id == step_id,
                )
            )
            step_row = row.scalar_one_or_none()
            if not step_row:
                return False
            await session.execute(
                delete(ProcessDependencyRow).where(
                    ProcessDependencyRow.process_id == process_id,
                    or_(
                        ProcessDependencyRow.source_step_id == step_id,
                        ProcessDependencyRow.target_step_id == step_id,
                    ),
                )
            )
            await session.delete(step_row)
            # Touch updated_at on the parent process
            proc = await session.get(BusinessProcessRow, process_id)
            if proc is not None:
                proc.updated_at = _utcnow()
            await session.commit()
            return True

    # ------------------------------------------------------------------
    # Dependency operations
    # ------------------------------------------------------------------

    async def add_dependency(
        self, process_id: str, dep: ProcessDependency
    ) -> ProcessDependency | None:
        """Add a dependency edge between two steps.

        Returns the dependency, or ``None`` if the parent process does not exist.
        """
        async with self._session_factory() as session:
            row = await session.get(BusinessProcessRow, process_id)
            if row is None:
                return None

            row.dependencies.append(self._dep_to_row(dep, process_id))
            row.updated_at = _utcnow()
            await session.commit()
            return dep

    async def remove_dependency(
        self, process_id: str, source_step_id: str, target_step_id: str
    ) -> bool:
        """Remove a dependency edge. Returns ``True`` if a matching row was deleted."""
        async with self._session_factory() as session:
            result = await session.execute(
                delete(ProcessDependencyRow).where(
                    ProcessDependencyRow.process_id == process_id,
                    ProcessDependencyRow.source_step_id == source_step_id,
                    ProcessDependencyRow.target_step_id == target_step_id,
                )
            )
            if result.rowcount:  # type: ignore[union-attr]
                # Touch updated_at on the parent process
                proc = await session.get(BusinessProcessRow, process_id)
                if proc is not None:
                    proc.updated_at = _utcnow()
                await session.commit()
                return True
            await session.commit()
            return False

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _step_to_row(step: ProcessStep, process_id: str) -> ProcessStepRow:
        return ProcessStepRow(
            id=step.id,
            process_id=process_id,
            name=step.name,
            description=step.description,
            step_type=step.step_type,
            system_id=step.system_id,
            endpoint_id=step.endpoint_id,
            order=step.order,
            inputs_json=_to_json(step.inputs),
            outputs_json=_to_json(step.outputs),
        )

    @staticmethod
    def _dep_to_row(dep: ProcessDependency, process_id: str) -> ProcessDependencyRow:
        return ProcessDependencyRow(
            process_id=process_id,
            source_step_id=dep.source_step_id,
            target_step_id=dep.target_step_id,
            condition=dep.condition,
        )

    @staticmethod
    def _row_to_step(row: ProcessStepRow) -> ProcessStep:
        return ProcessStep(
            id=row.id,
            name=row.name,
            description=row.description,
            step_type=row.step_type,
            system_id=row.system_id,
            endpoint_id=row.endpoint_id,
            order=row.order,
            inputs=_from_json(row.inputs_json) or [],
            outputs=_from_json(row.outputs_json) or [],
        )

    @staticmethod
    def _row_to_dep(row: ProcessDependencyRow) -> ProcessDependency:
        return ProcessDependency(
            source_step_id=row.source_step_id,
            target_step_id=row.target_step_id,
            condition=row.condition,
        )

    def _row_to_process(self, row: BusinessProcessRow) -> BusinessProcess:
        return BusinessProcess(
            id=row.id,
            name=row.name,
            description=row.description,
            category=row.category,
            workspace_id=row.workspace_id,
            source=ProcessSource(row.source),
            confidence=row.confidence,
            status=ProcessStatus(row.status),
            tags=_from_json(row.tags_json) or [],
            steps=[self._row_to_step(s) for s in sorted(row.steps, key=lambda s: s.order)],
            dependencies=[self._row_to_dep(d) for d in row.dependencies],
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
