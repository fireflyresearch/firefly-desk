# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for background jobs."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.jobs.models import Job, JobStatus
from flydesk.models.job import JobRow

logger = logging.getLogger(__name__)


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


class JobRepository:
    """CRUD operations for background jobs."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, job: Job) -> None:
        """Persist a new job record."""
        async with self._session_factory() as session:
            row = JobRow(
                id=job.id,
                job_type=job.job_type,
                status=job.status.value,
                progress_pct=job.progress_pct,
                progress_message=job.progress_message,
                result_json=_to_json(job.result),
                error=job.error,
                payload_json=_to_json(job.payload),
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
            )
            session.add(row)
            await session.commit()

    async def get(self, job_id: str) -> Job | None:
        """Retrieve a job by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                return None
            return self._row_to_job(row)

    async def list(
        self,
        *,
        job_type: str | None = None,
        status: JobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Job]:
        """Return jobs, optionally filtered by type and/or status, most recent first."""
        async with self._session_factory() as session:
            stmt = select(JobRow)
            if job_type is not None:
                stmt = stmt.where(JobRow.job_type == job_type)
            if status is not None:
                stmt = stmt.where(JobRow.status == status.value)
            stmt = stmt.order_by(JobRow.created_at.desc()).limit(limit).offset(offset)
            result = await session.execute(stmt)
            return [self._row_to_job(r) for r in result.scalars().all()]

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        error: str | None = None,
        result: dict | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update the status of a job, plus optional result/error timestamps."""
        async with self._session_factory() as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                logger.warning("update_status: job %s not found", job_id)
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

    async def update_progress(
        self,
        job_id: str,
        progress_pct: int,
        progress_message: str = "",
    ) -> None:
        """Update the progress fields for a running job."""
        async with self._session_factory() as session:
            row = await session.get(JobRow, job_id)
            if row is None:
                logger.warning("update_progress: job %s not found", job_id)
                return
            row.progress_pct = progress_pct
            row.progress_message = progress_message
            await session.commit()

    async def cleanup_old(self, max_age_days: int = 30) -> int:
        """Delete completed/failed/cancelled jobs older than *max_age_days*.

        Returns the number of rows deleted.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
        terminal_statuses = [
            JobStatus.COMPLETED.value,
            JobStatus.FAILED.value,
            JobStatus.CANCELLED.value,
        ]
        async with self._session_factory() as session:
            result = await session.execute(
                delete(JobRow).where(
                    JobRow.status.in_(terminal_statuses),
                    JobRow.created_at < cutoff,
                )
            )
            await session.commit()
            return result.rowcount  # type: ignore[return-value]

    @staticmethod
    def _row_to_job(row: JobRow) -> Job:
        return Job(
            id=row.id,
            job_type=row.job_type,
            status=JobStatus(row.status),
            progress_pct=row.progress_pct,
            progress_message=row.progress_message,
            result=_from_json(row.result_json),
            error=row.error,
            payload=_from_json(row.payload_json) or {},
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
