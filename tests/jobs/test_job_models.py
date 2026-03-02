"""Tests for job domain model changes."""
from flydesk.jobs.models import Job, JobStatus


class TestJobStatus:
    def test_paused_status_exists(self):
        assert JobStatus.PAUSED == "paused"

    def test_paused_is_valid_status(self):
        assert JobStatus("paused") == JobStatus.PAUSED


class TestJobCheckpoint:
    def test_job_has_checkpoint_field(self):
        job = Job(
            id="j-1",
            job_type="test",
            checkpoint={"processed": [1, 2, 3]},
            created_at="2026-01-01T00:00:00Z",
        )
        assert job.checkpoint == {"processed": [1, 2, 3]}

    def test_job_checkpoint_defaults_to_none(self):
        job = Job(id="j-2", job_type="test", created_at="2026-01-01T00:00:00Z")
        assert job.checkpoint is None
