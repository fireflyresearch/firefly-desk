"""Tests for ORM model constraints, defaults, and nullable settings.

Uses ``sqlalchemy.inspect`` to verify column properties declaratively,
without needing a running database.
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect as sa_inspect


def _get_columns(model_cls):
    """Get column definitions from a model class."""
    mapper = sa_inspect(model_cls)
    return {c.key: c for c in mapper.columns}


def _has_primary_key(model_cls, column_name: str) -> bool:
    cols = _get_columns(model_cls)
    return cols[column_name].primary_key


# ---------------------------------------------------------------------------
# WorkflowStepRow
# ---------------------------------------------------------------------------


class TestWorkflowStepRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.workflow import WorkflowStepRow

        self.cols = _get_columns(WorkflowStepRow)
        self.model = WorkflowStepRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_timeout_seconds_exists(self):
        assert "timeout_seconds" in self.cols

    def test_timeout_seconds_not_nullable(self):
        assert not self.cols["timeout_seconds"].nullable

    def test_max_retries_not_nullable(self):
        assert not self.cols["max_retries"].nullable

    def test_retry_count_not_nullable(self):
        assert not self.cols["retry_count"].nullable

    def test_workflow_id_not_nullable(self):
        assert not self.cols["workflow_id"].nullable

    def test_step_type_not_nullable(self):
        assert not self.cols["step_type"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable


# ---------------------------------------------------------------------------
# WorkflowRow
# ---------------------------------------------------------------------------


class TestWorkflowRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.workflow import WorkflowRow

        self.cols = _get_columns(WorkflowRow)
        self.model = WorkflowRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_user_id_not_nullable(self):
        assert not self.cols["user_id"].nullable

    def test_conversation_id_nullable(self):
        assert self.cols["conversation_id"].nullable

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_workflow_type_not_nullable(self):
        assert not self.cols["workflow_type"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable

    def test_state_json_nullable(self):
        assert self.cols["state_json"].nullable

    def test_completed_at_nullable(self):
        assert self.cols["completed_at"].nullable


# ---------------------------------------------------------------------------
# WorkflowWebhookRow
# ---------------------------------------------------------------------------


class TestWorkflowWebhookRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.workflow import WorkflowWebhookRow

        self.cols = _get_columns(WorkflowWebhookRow)
        self.model = WorkflowWebhookRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_webhook_token_not_nullable(self):
        assert not self.cols["webhook_token"].nullable

    def test_webhook_token_unique(self):
        assert self.cols["webhook_token"].unique

    def test_workflow_id_not_nullable(self):
        assert not self.cols["workflow_id"].nullable

    def test_external_system_nullable(self):
        assert self.cols["external_system"].nullable

    def test_expires_at_nullable(self):
        assert self.cols["expires_at"].nullable


# ---------------------------------------------------------------------------
# DeadLetterEntryRow
# ---------------------------------------------------------------------------


class TestDeadLetterEntryRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.dead_letter import DeadLetterEntryRow

        self.cols = _get_columns(DeadLetterEntryRow)
        self.model = DeadLetterEntryRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_source_type_not_nullable(self):
        assert not self.cols["source_type"].nullable

    def test_source_id_nullable(self):
        assert self.cols["source_id"].nullable

    def test_payload_json_not_nullable(self):
        assert not self.cols["payload_json"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable

    def test_has_created_at(self):
        assert "created_at" in self.cols

    def test_created_at_not_nullable(self):
        assert not self.cols["created_at"].nullable

    def test_updated_at_nullable(self):
        assert self.cols["updated_at"].nullable


# ---------------------------------------------------------------------------
# CacheEntryRow
# ---------------------------------------------------------------------------


class TestCacheEntryRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.cache_entry import CacheEntryRow

        self.cols = _get_columns(CacheEntryRow)
        self.model = CacheEntryRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_namespace_not_nullable(self):
        assert not self.cols["namespace"].nullable

    def test_cache_key_not_nullable(self):
        assert not self.cols["cache_key"].nullable

    def test_value_json_not_nullable(self):
        assert not self.cols["value_json"].nullable

    def test_expires_at_not_nullable(self):
        assert not self.cols["expires_at"].nullable

    def test_created_at_not_nullable(self):
        assert not self.cols["created_at"].nullable

    def test_unique_constraint_namespace_key(self):
        """The table must enforce unique(namespace, cache_key)."""
        from flydesk.models.cache_entry import CacheEntryRow

        table = CacheEntryRow.__table__
        unique_names = [
            c.name for c in table.constraints if hasattr(c, "columns") and len(c.columns) > 1
        ]
        assert "uq_cache_ns_key" in unique_names


# ---------------------------------------------------------------------------
# ConversationRow
# ---------------------------------------------------------------------------


class TestConversationRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.conversation import ConversationRow

        self.cols = _get_columns(ConversationRow)
        self.model = ConversationRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_user_id_not_nullable(self):
        assert not self.cols["user_id"].nullable

    def test_title_nullable(self):
        assert self.cols["title"].nullable

    def test_deleted_at_nullable(self):
        assert self.cols["deleted_at"].nullable

    def test_channel_not_nullable(self):
        assert not self.cols["channel"].nullable

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_model_id_nullable(self):
        assert self.cols["model_id"].nullable


# ---------------------------------------------------------------------------
# MessageRow
# ---------------------------------------------------------------------------


class TestMessageRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.conversation import MessageRow

        self.cols = _get_columns(MessageRow)
        self.model = MessageRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_conversation_id_not_nullable(self):
        assert not self.cols["conversation_id"].nullable

    def test_role_not_nullable(self):
        assert not self.cols["role"].nullable

    def test_content_not_nullable(self):
        assert not self.cols["content"].nullable

    def test_turn_id_nullable(self):
        assert self.cols["turn_id"].nullable

    def test_token_count_nullable(self):
        assert self.cols["token_count"].nullable


# ---------------------------------------------------------------------------
# JobRow
# ---------------------------------------------------------------------------


class TestJobRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.job import JobRow

        self.cols = _get_columns(JobRow)
        self.model = JobRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_job_type_not_nullable(self):
        assert not self.cols["job_type"].nullable

    def test_progress_pct_not_nullable(self):
        assert not self.cols["progress_pct"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable

    def test_started_at_nullable(self):
        assert self.cols["started_at"].nullable

    def test_completed_at_nullable(self):
        assert self.cols["completed_at"].nullable


# ---------------------------------------------------------------------------
# FileUploadRow
# ---------------------------------------------------------------------------


class TestFileUploadRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.file_upload import FileUploadRow

        self.cols = _get_columns(FileUploadRow)
        self.model = FileUploadRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_filename_not_nullable(self):
        assert not self.cols["filename"].nullable

    def test_content_type_not_nullable(self):
        assert not self.cols["content_type"].nullable

    def test_file_size_not_nullable(self):
        assert not self.cols["file_size"].nullable

    def test_storage_path_not_nullable(self):
        assert not self.cols["storage_path"].nullable

    def test_user_id_not_nullable(self):
        assert not self.cols["user_id"].nullable

    def test_conversation_id_nullable(self):
        assert self.cols["conversation_id"].nullable

    def test_extracted_text_nullable(self):
        assert self.cols["extracted_text"].nullable


# ---------------------------------------------------------------------------
# KnowledgeDocumentRow
# ---------------------------------------------------------------------------


class TestKnowledgeDocumentRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.knowledge_base import KnowledgeDocumentRow

        self.cols = _get_columns(KnowledgeDocumentRow)
        self.model = KnowledgeDocumentRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_title_not_nullable(self):
        assert not self.cols["title"].nullable

    def test_content_not_nullable(self):
        assert not self.cols["content"].nullable

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_source_nullable(self):
        assert self.cols["source"].nullable


# ---------------------------------------------------------------------------
# AuditEventRow
# ---------------------------------------------------------------------------


class TestAuditEventRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.audit import AuditEventRow

        self.cols = _get_columns(AuditEventRow)
        self.model = AuditEventRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_event_type_not_nullable(self):
        assert not self.cols["event_type"].nullable

    def test_user_id_not_nullable(self):
        assert not self.cols["user_id"].nullable

    def test_action_not_nullable(self):
        assert not self.cols["action"].nullable

    def test_conversation_id_nullable(self):
        assert self.cols["conversation_id"].nullable

    def test_risk_level_nullable(self):
        assert self.cols["risk_level"].nullable

    def test_ip_address_nullable(self):
        assert self.cols["ip_address"].nullable


# ---------------------------------------------------------------------------
# RoleRow
# ---------------------------------------------------------------------------


class TestRoleRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.role import RoleRow

        self.cols = _get_columns(RoleRow)
        self.model = RoleRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_name_not_nullable(self):
        assert not self.cols["name"].nullable

    def test_name_unique(self):
        assert self.cols["name"].unique

    def test_display_name_not_nullable(self):
        assert not self.cols["display_name"].nullable

    def test_is_builtin_not_nullable(self):
        assert not self.cols["is_builtin"].nullable

    def test_permissions_not_nullable(self):
        assert not self.cols["permissions"].nullable

    def test_access_scopes_nullable(self):
        assert self.cols["access_scopes"].nullable


# ---------------------------------------------------------------------------
# CallbackDeliveryRow
# ---------------------------------------------------------------------------


class TestCallbackDeliveryRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.callback_delivery import CallbackDeliveryRow

        self.cols = _get_columns(CallbackDeliveryRow)
        self.model = CallbackDeliveryRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_callback_id_not_nullable(self):
        assert not self.cols["callback_id"].nullable

    def test_event_not_nullable(self):
        assert not self.cols["event"].nullable

    def test_url_not_nullable(self):
        assert not self.cols["url"].nullable

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_status_code_nullable(self):
        assert self.cols["status_code"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable


# ---------------------------------------------------------------------------
# WebhookLogEntryRow
# ---------------------------------------------------------------------------


class TestWebhookLogEntryRow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        from flydesk.models.webhook_log import WebhookLogEntryRow

        self.cols = _get_columns(WebhookLogEntryRow)
        self.model = WebhookLogEntryRow

    def test_id_is_primary_key(self):
        assert _has_primary_key(self.model, "id")

    def test_provider_not_nullable(self):
        assert not self.cols["provider"].nullable

    def test_status_not_nullable(self):
        assert not self.cols["status"].nullable

    def test_from_address_not_nullable(self):
        assert not self.cols["from_address"].nullable

    def test_error_nullable(self):
        assert self.cols["error"].nullable

    def test_processing_ms_not_nullable(self):
        assert not self.cols["processing_ms"].nullable
