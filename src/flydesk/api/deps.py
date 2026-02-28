# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Shared FastAPI dependency stubs for the Firefly Desk API layer.

Each function is a no-op placeholder that **must** be wired via
``app.dependency_overrides`` in ``server.py`` (or in test fixtures).
Centralising the stubs here eliminates per-module duplication and
means ``server.py`` only needs one override per dependency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.audit.logger import AuditLogger
from flydesk.auth.oidc import OIDCClient
from flydesk.auth.local_user_repository import LocalUserRepository
from flydesk.auth.repository import OIDCProviderRepository
from flydesk.callbacks.delivery_repository import CallbackDeliveryRepository
from flydesk.catalog.repository import CatalogRepository
from flydesk.conversation.folder_repository import FolderRepository
from flydesk.feedback.repository import FeedbackRepository
from flydesk.conversation.repository import ConversationRepository
from flydesk.exports.repository import ExportRepository
from flydesk.exports.service import ExportService
from flydesk.files.extractor import ContentExtractor
from flydesk.files.repository import FileUploadRepository
from flydesk.files.storage import FileStorageProvider
from flydesk.jobs.repository import JobRepository
from flydesk.jobs.runner import JobRunner
from flydesk.knowledge.git_provider_repository import GitProviderRepository
from flydesk.knowledge.graph import KnowledgeGraph
from flydesk.knowledge.importer import KnowledgeImporter
from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.queue import IndexingQueueProducer
from flydesk.llm.repository import LLMProviderRepository
from flydesk.memory.repository import MemoryRepository
from flydesk.processes.repository import ProcessRepository
from flydesk.rbac.repository import RoleRepository
from flydesk.settings.repository import SettingsRepository
from flydesk.tools.custom_repository import CustomToolRepository
from flydesk.tools.sandbox import SandboxExecutor
from flydesk.triggers.auto_trigger import AutoTriggerService
from flydesk.email.webhook_log_repository import WebhookLogRepository
from flydesk.knowledge.document_source_repository import DocumentSourceRepository
from flydesk.workflows.engine import WorkflowEngine
from flydesk.workflows.repository import WorkflowRepository
from flydesk.workspaces.repository import WorkspaceRepository

if TYPE_CHECKING:
    from flydesk.catalog.ports import CredentialStore
    from flydesk.channels.router import ChannelRouter
    from flydesk.email.channel_adapter import EmailChannelAdapter
    from flydesk.knowledge.analyzer import DocumentAnalyzer
    from flydesk.knowledge.ports import KnowledgeDocumentStore
    from flydesk.security.kms import KMSProvider


# ---------------------------------------------------------------------------
# Repository / service dependency stubs
# ---------------------------------------------------------------------------


def get_audit_logger() -> AuditLogger:
    """Provide an AuditLogger instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_audit_logger must be overridden via app.dependency_overrides"
    )


def get_callback_delivery_repo() -> CallbackDeliveryRepository:
    """Provide a CallbackDeliveryRepository instance."""
    raise NotImplementedError(
        "get_callback_delivery_repo must be overridden via app.dependency_overrides"
    )


def get_catalog_repo() -> CatalogRepository:
    """Provide a CatalogRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_catalog_repo must be overridden via app.dependency_overrides"
    )


def get_channel_router() -> ChannelRouter:
    """Provide the :class:`ChannelRouter` instance.

    In production this is wired via the lifespan after channel adapters
    are registered.  In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_channel_router must be overridden via app.dependency_overrides"
    )


def get_content_extractor() -> ContentExtractor:
    """Provide a ContentExtractor instance."""
    raise NotImplementedError(
        "get_content_extractor must be overridden via app.dependency_overrides"
    )


def get_conversation_repo() -> ConversationRepository:
    """Provide a ConversationRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_conversation_repo must be overridden via app.dependency_overrides"
    )


def get_credential_store() -> CredentialStore:
    """Provide a CredentialStore instance.

    In production this is wired to the real encrypted storage.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_credential_store must be overridden via app.dependency_overrides"
    )


def get_custom_tool_repo() -> CustomToolRepository:
    """Provide a CustomToolRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_custom_tool_repo must be overridden via app.dependency_overrides"
    )


def get_document_analyzer() -> DocumentAnalyzer:
    """Provide a DocumentAnalyzer instance -- overridden in server lifespan."""
    raise NotImplementedError(
        "get_document_analyzer must be overridden via app.dependency_overrides"
    )


def get_document_source_repo() -> DocumentSourceRepository:
    """Provide a DocumentSourceRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_document_source_repo must be overridden via app.dependency_overrides"
    )


def get_email_channel_adapter() -> EmailChannelAdapter:
    """Provide the :class:`EmailChannelAdapter` instance.

    In production this is wired via the lifespan when the email channel
    is enabled.  In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_email_channel_adapter must be overridden via app.dependency_overrides"
    )


def get_folder_repo() -> FolderRepository:
    """Provide a FolderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_folder_repo must be overridden via app.dependency_overrides"
    )


def get_export_repo() -> ExportRepository:
    """Provide an ExportRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_export_repo must be overridden via app.dependency_overrides"
    )


def get_feedback_repo() -> FeedbackRepository:
    """Provide a FeedbackRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_feedback_repo must be overridden via app.dependency_overrides"
    )


def get_export_service() -> ExportService:
    """Provide an ExportService instance."""
    raise NotImplementedError(
        "get_export_service must be overridden via app.dependency_overrides"
    )


def get_export_storage() -> FileStorageProvider:
    """Provide a FileStorageProvider instance for export downloads."""
    raise NotImplementedError(
        "get_export_storage must be overridden via app.dependency_overrides"
    )


def get_file_repo() -> FileUploadRepository:
    """Provide a FileUploadRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_file_repo must be overridden via app.dependency_overrides"
    )


def get_file_storage() -> FileStorageProvider:
    """Provide a FileStorageProvider instance."""
    raise NotImplementedError(
        "get_file_storage must be overridden via app.dependency_overrides"
    )


def get_git_provider_repo() -> GitProviderRepository:
    """Provide a GitProviderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_git_provider_repo must be overridden via app.dependency_overrides"
    )


def get_indexing_producer() -> IndexingQueueProducer:
    """Provide the background indexing queue producer.

    In production this is wired via the lifespan.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_indexing_producer must be overridden via app.dependency_overrides"
    )


def get_job_repo() -> JobRepository:
    """Provide a JobRepository instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_job_repo must be overridden via app.dependency_overrides"
    )


def get_job_runner() -> JobRunner:
    """Provide a JobRunner instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_job_runner must be overridden via app.dependency_overrides"
    )


def get_kms() -> KMSProvider:
    """Provide the KMS provider for credential encryption.

    In production this is wired to the configured KMS backend.
    In tests the dependency is overridden with a NoOpKMSProvider or mock.
    """
    from flydesk.security.kms import NoOpKMSProvider

    return NoOpKMSProvider()


def get_knowledge_doc_store() -> KnowledgeDocumentStore:
    """Provide a KnowledgeDocumentStore instance.

    In production this is wired to the real database.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_doc_store must be overridden via app.dependency_overrides"
    )


def get_knowledge_graph() -> KnowledgeGraph:
    """Provide a KnowledgeGraph instance.

    In production this is wired via the lifespan with the real session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_graph must be overridden via app.dependency_overrides"
    )


def get_knowledge_importer() -> KnowledgeImporter:
    """Provide a KnowledgeImporter instance.

    In production this is wired via the lifespan with the real indexer and HTTP client.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_importer must be overridden via app.dependency_overrides"
    )


def get_knowledge_indexer() -> KnowledgeIndexer:
    """Provide a KnowledgeIndexer instance.

    In production this is wired to the real indexer with embeddings.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_indexer must be overridden via app.dependency_overrides"
    )


def get_llm_repo() -> LLMProviderRepository:
    """Provide an LLMProviderRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_llm_repo must be overridden via app.dependency_overrides"
    )


def get_local_user_repo() -> LocalUserRepository:
    """Provide a LocalUserRepository instance.

    In production this is wired in the lifespan.
    """
    raise NotImplementedError(
        "get_local_user_repo must be overridden via app.dependency_overrides"
    )


def get_memory_repo() -> MemoryRepository:
    """Provide a MemoryRepository instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_memory_repo must be overridden via app.dependency_overrides"
    )


def get_oidc_client() -> OIDCClient | None:
    """Provide a default OIDCClient configured from env.

    Returns ``None`` when no issuer URL is configured.
    """
    return None


def get_oidc_repo() -> OIDCProviderRepository:
    """Provide an OIDCProviderRepository instance.

    In production this is wired in the lifespan.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_oidc_repo must be overridden via app.dependency_overrides"
    )


def get_process_repo() -> ProcessRepository:
    """Provide a ProcessRepository instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_process_repo must be overridden via app.dependency_overrides"
    )


def get_role_repo() -> RoleRepository:
    """Provide a RoleRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_role_repo must be overridden via app.dependency_overrides"
    )


def get_sandbox_executor() -> SandboxExecutor:
    """Provide a SandboxExecutor instance.

    In production this is wired in server.py.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_sandbox_executor must be overridden via app.dependency_overrides"
    )


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide the database session factory."""
    raise NotImplementedError(
        "get_session_factory must be overridden via app.dependency_overrides"
    )


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


def get_workflow_engine() -> WorkflowEngine:
    """Provide a WorkflowEngine instance."""
    raise NotImplementedError(
        "get_workflow_engine must be overridden via app.dependency_overrides"
    )


def get_workflow_repo() -> WorkflowRepository:
    """Provide a WorkflowRepository instance."""
    raise NotImplementedError(
        "get_workflow_repo must be overridden via app.dependency_overrides"
    )


def get_webhook_log_repo() -> WebhookLogRepository:
    """Provide a WebhookLogRepository instance."""
    raise NotImplementedError(
        "get_webhook_log_repo must be overridden via app.dependency_overrides"
    )


def get_workspace_repo() -> WorkspaceRepository:
    """Provide a WorkspaceRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_workspace_repo must be overridden via app.dependency_overrides"
    )


# ---------------------------------------------------------------------------
# Non-raising defaults (return ``None`` when not wired)
# ---------------------------------------------------------------------------


def get_auto_trigger() -> AutoTriggerService | None:
    """Provide the AutoTriggerService instance (or None if not wired).

    In production this is wired via the lifespan.
    In tests the dependency is overridden with a mock.
    """
    return None
