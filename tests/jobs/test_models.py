# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for job domain models and SQLAlchemy ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from flydesk.jobs.models import Job, JobStatus


class TestJobStatus:
    def test_enum_values(self):
        """All expected status values are present."""
        assert JobStatus.PENDING == "pending"
        assert JobStatus.RUNNING == "running"
        assert JobStatus.COMPLETED == "completed"
        assert JobStatus.FAILED == "failed"
        assert JobStatus.CANCELLED == "cancelled"

    def test_from_string(self):
        """Enum can be constructed from string values."""
        assert JobStatus("pending") is JobStatus.PENDING
        assert JobStatus("running") is JobStatus.RUNNING
        assert JobStatus("completed") is JobStatus.COMPLETED
        assert JobStatus("failed") is JobStatus.FAILED
        assert JobStatus("cancelled") is JobStatus.CANCELLED

    def test_invalid_status_raises(self):
        """An invalid string raises a ValueError."""
        with pytest.raises(ValueError):
            JobStatus("invalid")


class TestJob:
    def test_create_minimal_job(self):
        """A Job can be created with only required fields."""
        now = datetime.now(timezone.utc)
        job = Job(id="j-1", job_type="indexing", created_at=now)
        assert job.id == "j-1"
        assert job.job_type == "indexing"
        assert job.status == JobStatus.PENDING
        assert job.progress_pct == 0
        assert job.progress_message == ""
        assert job.result is None
        assert job.error is None
        assert job.started_at is None
        assert job.completed_at is None
        assert job.payload == {}

    def test_create_full_job(self):
        """A Job can be created with all fields populated."""
        now = datetime.now(timezone.utc)
        job = Job(
            id="j-2",
            job_type="process_discovery",
            status=JobStatus.RUNNING,
            progress_pct=50,
            progress_message="Analyzing logs",
            result={"entities": 10},
            error=None,
            created_at=now,
            started_at=now,
            completed_at=None,
            payload={"log_id": "abc"},
        )
        assert job.status == JobStatus.RUNNING
        assert job.progress_pct == 50
        assert job.progress_message == "Analyzing logs"
        assert job.result == {"entities": 10}
        assert job.payload == {"log_id": "abc"}

    def test_job_serialisation(self):
        """A Job can be serialised to and deserialised from JSON."""
        now = datetime.now(timezone.utc)
        job = Job(
            id="j-3",
            job_type="kg_recompute",
            status=JobStatus.COMPLETED,
            progress_pct=100,
            result={"nodes": 42},
            created_at=now,
            started_at=now,
            completed_at=now,
        )
        data = job.model_dump_json()
        restored = Job.model_validate_json(data)
        assert restored.id == job.id
        assert restored.status == JobStatus.COMPLETED
        assert restored.result == {"nodes": 42}


class TestJobRow:
    def test_job_row_table_name(self):
        """JobRow has the correct table name."""
        from flydesk.models.job import JobRow

        assert JobRow.__tablename__ == "jobs"

    def test_job_row_columns(self):
        """JobRow has all expected columns."""
        from flydesk.models.job import JobRow

        col_names = {c.name for c in JobRow.__table__.columns}
        expected = {
            "id",
            "job_type",
            "status",
            "progress_pct",
            "progress_message",
            "result_json",
            "error",
            "payload_json",
            "created_at",
            "started_at",
            "completed_at",
        }
        assert expected.issubset(col_names)
