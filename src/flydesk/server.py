# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""FastAPI application factory with proper lifecycle management.

The ``lifespan`` async context manager orchestrates startup and shutdown by
delegating to focused ``_init_*`` helpers.  Each helper creates a related
group of services, wires dependency overrides, and returns objects needed by
later phases.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request as _Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import flydesk
from flydesk.api.audit import router as audit_router
from flydesk.api.auth import router as auth_router
from flydesk.api.catalog import router as catalog_router
from flydesk.api.cloud_import import router as cloud_import_router
from flydesk.api.chat import router as chat_router
from flydesk.api.conversations import router as conversations_router
from flydesk.api.credentials import router as credentials_router
from flydesk.api.custom_tools import router as custom_tools_router
from flydesk.api.dashboard import router as dashboard_router
from flydesk.api.document_sources import router as document_sources_router
from flydesk.api.email_inbound import router as email_inbound_router
from flydesk.api.email_settings import router as email_settings_router
from flydesk.api.webhooks import router as webhooks_router
from flydesk.api.deps import (
    get_audit_logger,
    get_auto_trigger,
    get_catalog_repo,
    get_channel_router,
    get_content_extractor,
    get_conversation_repo,
    get_credential_store,
    get_custom_tool_repo,
    get_document_analyzer,
    get_document_source_repo,
    get_email_channel_adapter,
    get_export_repo,
    get_export_service,
    get_export_storage,
    get_feedback_repo,
    get_file_repo,
    get_file_storage,
    get_folder_repo,
    get_git_provider_repo,
    get_indexing_producer,
    get_job_repo,
    get_job_runner,
    get_kms,
    get_knowledge_doc_store,
    get_knowledge_graph,
    get_knowledge_importer,
    get_knowledge_indexer,
    get_llm_repo,
    get_local_user_repo,
    get_memory_repo,
    get_oidc_client,
    get_oidc_repo,
    get_process_repo,
    get_role_repo,
    get_sandbox_executor,
    get_session_factory,
    get_settings_repo,
    get_workflow_engine,
    get_workflow_repo,
    get_workspace_repo,
)
from flydesk.api.exports import router as exports_router
from flydesk.api.feedback import router as feedback_router
from flydesk.api.files import router as files_router
from flydesk.api.git_import import router as git_import_router
from flydesk.api.git_providers import router as git_providers_router
from flydesk.api.github import router as github_router
from flydesk.api.health import router as health_router
from flydesk.api.jobs import router as jobs_router
from flydesk.api.knowledge import router as knowledge_router
from flydesk.api.llm_providers import router as llm_providers_router
from flydesk.api.llm_status import router as llm_status_router
from flydesk.api.memory import router as memory_router
from flydesk.api.notifications import router as notifications_router
from flydesk.api.oidc_providers import router as oidc_providers_router
from flydesk.api.openapi_import import router as openapi_import_router
from flydesk.api.processes import router as processes_router
from flydesk.api.prompts import router as prompts_router
from flydesk.api.roles import router as roles_router
from flydesk.api.settings import router as settings_router
from flydesk.api.setup import router as setup_router
from flydesk.api.sso_mappings import router as sso_mappings_router
from flydesk.api.tools_admin import router as tools_admin_router
from flydesk.api.users import router as users_router
from flydesk.api.workspaces import router as workspace_router
from flydesk.api.help_docs import router as help_docs_router
from flydesk.knowledge.models import DocumentStatus
from flydesk.audit.logger import AuditLogger
from flydesk.auth.middleware import AuthMiddleware
from flydesk.catalog.repository import CatalogRepository
from flydesk.conversation.repository import ConversationRepository
from flydesk.config import DeskConfig, get_config
from flydesk.db import create_engine_from_url, create_session_factory
from flydesk.models import Base
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shutdown context — collects objects that need teardown
# ---------------------------------------------------------------------------


@dataclass
class _ShutdownContext:
    """Collects resources that must be closed during shutdown."""

    closables: list[Any] = field(default_factory=list)

    async def shutdown(self) -> None:
        for obj in reversed(self.closables):
            try:
                if hasattr(obj, "cancel_pending"):
                    obj.cancel_pending()
                elif hasattr(obj, "stop"):
                    await obj.stop()
                elif hasattr(obj, "aclose"):
                    await obj.aclose()
                elif hasattr(obj, "close"):
                    await obj.close()
                elif hasattr(obj, "dispose"):
                    await obj.dispose()
            except Exception:
                logger.warning("Error during shutdown of %s", type(obj).__name__, exc_info=True)
        logger.info("Firefly Desk shutdown complete.")


# ---------------------------------------------------------------------------
# Database initialisation
# ---------------------------------------------------------------------------


async def _init_database(
    config: DeskConfig,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create engine, run DDL, return session factory."""
    engine = create_engine_from_url(config.database_url)

    async with engine.begin() as conn:
        if "postgresql" in config.database_url:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        # Backfill columns for existing databases that predate schema additions.
        _backfills = [
            "ALTER TABLE conversations ADD COLUMN deleted_at DATETIME",
            "ALTER TABLE conversation_folders ADD COLUMN icon VARCHAR(50) NOT NULL DEFAULT 'folder'",
            "ALTER TABLE conversations ADD COLUMN channel VARCHAR(50) NOT NULL DEFAULT 'chat'",
        ]
        for sql in _backfills:
            try:
                await conn.execute(text(sql))
            except Exception:
                pass  # Column already exists

    session_factory = create_session_factory(engine)
    return engine, session_factory


# ---------------------------------------------------------------------------
# Core repositories
# ---------------------------------------------------------------------------


async def _init_repositories(
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Wire all basic repository dependency overrides.

    Returns a dict of named services that later init phases need.
    """
    from flydesk.rbac.repository import RoleRepository

    role_repo = RoleRepository(session_factory)
    try:
        await role_repo.seed_builtin_roles()
    except Exception:
        logger.warning("Failed to seed built-in roles (non-fatal).", exc_info=True)
    app.state.role_repo = role_repo
    app.dependency_overrides[get_role_repo] = lambda: role_repo

    catalog_repo = CatalogRepository(session_factory)
    audit_logger = AuditLogger(session_factory)
    conversation_repo = ConversationRepository(session_factory)

    from flydesk.workspaces.repository import WorkspaceRepository

    workspace_repo = WorkspaceRepository(session_factory)

    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)

    from flydesk.memory.repository import MemoryRepository

    memory_repo = MemoryRepository(session_factory)
    app.state.memory_repo = memory_repo

    from flydesk.tools.custom_repository import CustomToolRepository
    from flydesk.tools.sandbox import SandboxExecutor

    custom_tool_repo = CustomToolRepository(session_factory)
    sandbox_executor = SandboxExecutor()

    from flydesk.llm.repository import LLMProviderRepository

    llm_repo = LLMProviderRepository(session_factory, config.credential_encryption_key)

    from flydesk.knowledge.document_source_repository import DocumentSourceRepository

    doc_source_repo = DocumentSourceRepository(
        session_factory=session_factory,
        encryption_key=config.credential_encryption_key,
    )

    from flydesk.conversation.folder_repository import FolderRepository
    from flydesk.feedback.repository import FeedbackRepository

    folder_repo = FolderRepository(session_factory)
    feedback_repo = FeedbackRepository(session_factory)

    # Wire dependency overrides
    app.dependency_overrides[get_catalog_repo] = lambda: catalog_repo
    app.dependency_overrides[get_audit_logger] = lambda: audit_logger
    app.dependency_overrides[get_conversation_repo] = lambda: conversation_repo
    app.dependency_overrides[get_workspace_repo] = lambda: workspace_repo
    app.dependency_overrides[get_settings_repo] = lambda: settings_repo
    app.dependency_overrides[get_memory_repo] = lambda: memory_repo
    app.dependency_overrides[get_custom_tool_repo] = lambda: custom_tool_repo
    app.dependency_overrides[get_sandbox_executor] = lambda: sandbox_executor
    app.dependency_overrides[get_llm_repo] = lambda: llm_repo
    app.dependency_overrides[get_document_source_repo] = lambda: doc_source_repo
    app.dependency_overrides[get_folder_repo] = lambda: folder_repo
    app.dependency_overrides[get_feedback_repo] = lambda: feedback_repo

    return {
        "catalog_repo": catalog_repo,
        "audit_logger": audit_logger,
        "conversation_repo": conversation_repo,
        "settings_repo": settings_repo,
        "memory_repo": memory_repo,
        "llm_repo": llm_repo,
        "doc_source_repo": doc_source_repo,
        "feedback_repo": feedback_repo,
        "custom_tool_repo": custom_tool_repo,
        "sandbox_executor": sandbox_executor,
    }


# ---------------------------------------------------------------------------
# File system and exports
# ---------------------------------------------------------------------------


def _init_file_system(
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Wire file storage, upload repo, content extractor, and exports."""
    from flydesk.files.extractor import ContentExtractor
    from flydesk.files.repository import FileUploadRepository
    from flydesk.files.storage import LocalFileStorage

    file_repo = FileUploadRepository(session_factory)
    file_storage = LocalFileStorage(config.file_storage_path)
    content_extractor = ContentExtractor()

    app.dependency_overrides[get_file_repo] = lambda: file_repo
    app.dependency_overrides[get_file_storage] = lambda: file_storage
    app.dependency_overrides[get_content_extractor] = lambda: content_extractor

    from flydesk.exports.repository import ExportRepository
    from flydesk.exports.service import ExportService

    export_repo = ExportRepository(session_factory)
    export_service = ExportService(export_repo, file_storage)
    app.dependency_overrides[get_export_repo] = lambda: export_repo
    app.dependency_overrides[get_export_service] = lambda: export_service
    app.dependency_overrides[get_export_storage] = lambda: file_storage

    return {
        "file_repo": file_repo,
        "file_storage": file_storage,
        "content_extractor": content_extractor,
    }


# ---------------------------------------------------------------------------
# Security (KMS, credential/document stores)
# ---------------------------------------------------------------------------


def _init_security(
    app: FastAPI,
    config: DeskConfig,
    catalog_repo: CatalogRepository,
) -> dict[str, Any]:
    """Wire KMS provider, credential store, and knowledge document store."""
    from flydesk.security.kms import FernetKMSProvider, create_kms_provider

    kms = create_kms_provider(config)
    if isinstance(kms, FernetKMSProvider) and kms.is_dev_key:
        logger.warning(
            "Using dev encryption key. Set FLYDESK_CREDENTIAL_ENCRYPTION_KEY "
            "for production."
        )
    app.dependency_overrides[get_kms] = lambda: kms

    from flydesk.catalog.credential_store import CatalogCredentialStore

    cred_store = CatalogCredentialStore(catalog_repo)
    app.dependency_overrides[get_credential_store] = lambda: cred_store

    from flydesk.knowledge.document_store import CatalogDocumentStore

    doc_store = CatalogDocumentStore(catalog_repo)
    app.dependency_overrides[get_knowledge_doc_store] = lambda: doc_store

    return {"kms": kms, "cred_store": cred_store}


# ---------------------------------------------------------------------------
# Knowledge system (embeddings, indexer, vector store)
# ---------------------------------------------------------------------------


async def _init_knowledge(
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
    settings_repo: Any,
    llm_repo: Any,
    http_client: Any,
) -> dict[str, Any]:
    """Wire embedding provider, knowledge indexer, and vector store."""
    from flydesk.knowledge.embeddings import LLMEmbeddingProvider
    from flydesk.knowledge.indexer import KnowledgeIndexer
    from flydesk.knowledge.stores import create_vector_store

    embed_settings = await settings_repo.get_all_app_settings(category="embedding")
    embed_model = embed_settings.get("embedding_model") or config.embedding_model
    embed_key = embed_settings.get("embedding_api_key") or config.embedding_api_key
    embed_url = embed_settings.get("embedding_base_url") or config.embedding_base_url
    embed_dims = int(
        embed_settings.get("embedding_dimensions", "0")
        or config.embedding_dimensions
    )

    embedding_provider = LLMEmbeddingProvider(
        http_client=http_client,
        embedding_model=embed_model,
        dimensions=embed_dims,
        llm_repo=llm_repo,
        api_key=embed_key or None,
        base_url=embed_url or None,
    )

    knowledge_settings = await settings_repo.get_all_app_settings(category="knowledge")
    chunk_size = int(knowledge_settings.get("chunk_size", str(config.chunk_size)))
    chunk_overlap = int(knowledge_settings.get("chunk_overlap", str(config.chunk_overlap)))
    chunking_mode = knowledge_settings.get("chunking_mode", config.chunking_mode)
    auto_kg_extract = knowledge_settings.get(
        "auto_kg_extract", str(config.auto_kg_extract)
    ).lower() in ("true", "1")

    try:
        vector_store = create_vector_store(config, session_factory)
    except Exception:
        logger.warning("Failed to create vector store; falling back to direct SQLAlchemy.", exc_info=True)
        vector_store = None

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        chunking_mode=chunking_mode,
        vector_store=vector_store,
    )
    app.dependency_overrides[get_knowledge_indexer] = lambda: indexer

    return {
        "embedding_provider": embedding_provider,
        "indexer": indexer,
        "vector_store": vector_store,
        "auto_kg_extract": auto_kg_extract,
    }


# ---------------------------------------------------------------------------
# Background jobs and indexing queue
# ---------------------------------------------------------------------------


async def _init_jobs(
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
    indexer: Any,
    doc_source_repo: Any = None,
) -> dict[str, Any]:
    """Wire job runner, register indexing handler, and start indexing queue."""
    from flydesk.jobs.handlers import IndexingJobHandler
    from flydesk.jobs.repository import JobRepository
    from flydesk.jobs.runner import JobRunner

    job_repo = JobRepository(session_factory)
    job_runner = JobRunner(job_repo)
    job_runner.register_handler("indexing", IndexingJobHandler(indexer))

    if doc_source_repo is not None:
        from flydesk.jobs.source_sync import SourceSyncHandler

        sync_handler = SourceSyncHandler(doc_source_repo)
        job_runner.register_handler("source_sync", sync_handler)

    await job_runner.start()
    app.state.job_runner = job_runner
    app.state.job_repo = job_repo
    app.dependency_overrides[get_job_repo] = lambda: job_repo
    app.dependency_overrides[get_job_runner] = lambda: job_runner

    from flydesk.knowledge.queue import IndexingTask, create_indexing_queue

    async def _handle_indexing_task(task: IndexingTask) -> None:
        await job_runner.submit("indexing", task.model_dump())

    indexing_producer, indexing_consumer = create_indexing_queue(
        backend=config.queue_backend,
        handler=_handle_indexing_task,
        redis_url=config.redis_url,
    )
    await indexing_consumer.start()
    app.state.indexing_producer = indexing_producer
    app.state.indexing_consumer = indexing_consumer
    app.dependency_overrides[get_indexing_producer] = lambda: indexing_producer

    return {
        "job_runner": job_runner,
        "indexing_producer": indexing_producer,
        "indexing_consumer": indexing_consumer,
    }


# ---------------------------------------------------------------------------
# Agent and intelligence layer
# ---------------------------------------------------------------------------


async def _init_agent(  # noqa: PLR0913
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    catalog_repo: CatalogRepository,
    audit_logger: AuditLogger,
    conversation_repo: ConversationRepository,
    settings_repo: Any,
    memory_repo: Any,
    llm_repo: Any,
    embedding_provider: Any,
    vector_store: Any,
    indexer: Any,
    job_runner: Any,
    auto_kg_extract: bool,
    kms: Any,
    cred_store: Any,
    file_repo: Any,
    file_storage: Any,
    http_client: Any,
    feedback_repo: Any = None,
    custom_tool_repo: Any = None,
    sandbox_executor: Any = None,
) -> dict[str, Any]:
    """Wire the DeskAgent and all its dependencies (retriever, tools, KG, etc.)."""
    from flydesk.agent.context import ContextEnricher
    from flydesk.agent.desk_agent import DeskAgent
    from flydesk.agent.prompt import SystemPromptBuilder
    from flydesk.prompts.registry import register_desk_prompts
    from flydesk.knowledge.graph import KnowledgeGraph
    from flydesk.knowledge.retriever import KnowledgeRetriever
    from flydesk.tools.executor import ToolExecutor
    from flydesk.tools.factory import ToolFactory
    from flydesk.widgets.parser import WidgetParser

    knowledge_graph = KnowledgeGraph(session_factory)
    retriever = KnowledgeRetriever(session_factory, embedding_provider, vector_store=vector_store)
    context_enricher = ContextEnricher(
        knowledge_graph=knowledge_graph,
        retriever=retriever,
        memory_repo=memory_repo,
        entity_limit=config.kg_max_entities_in_context,
        retrieval_top_k=config.rag_top_k,
    )
    prompt_registry = register_desk_prompts()
    prompt_builder = SystemPromptBuilder(prompt_registry)
    tool_factory = ToolFactory()
    widget_parser = WidgetParser()

    app.dependency_overrides[get_knowledge_graph] = lambda: knowledge_graph

    from flydesk.knowledge.importer import KnowledgeImporter

    knowledge_importer = KnowledgeImporter(indexer=indexer, http_client=http_client)
    app.dependency_overrides[get_knowledge_importer] = lambda: knowledge_importer

    tool_executor = ToolExecutor(
        http_client=http_client,
        catalog_repo=catalog_repo,
        credential_store=cred_store,
        audit_logger=audit_logger,
        max_parallel=config.max_tools_per_turn,
        kms=kms,
    )

    from flydesk.agent.confirmation import ConfirmationService

    confirmation_service = ConfirmationService()
    app.state.confirmation_service = confirmation_service

    from flydesk.processes.repository import ProcessRepository

    process_repo = ProcessRepository(session_factory)

    from flydesk.tools.builtin import BuiltinToolExecutor

    # Initialize search provider from settings (if configured)
    search_provider = None
    try:
        search_settings = await settings_repo.get_all_app_settings(category="search")
        search_provider_name = search_settings.get("search_provider", "")
        search_api_key = search_settings.get("search_api_key", "")
        if search_provider_name and search_api_key:
            import flydesk.search.adapters.tavily  # noqa: F401
            from flydesk.search.provider import SearchProviderFactory

            search_max = int(search_settings.get("search_max_results", "5"))
            search_provider = SearchProviderFactory.create(
                search_provider_name,
                {"api_key": search_api_key, "max_results": search_max},
            )
            logger.info("Search provider initialized: %s", search_provider_name)
    except Exception:
        logger.warning("Failed to initialize search provider.", exc_info=True)

    builtin_executor = BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
        knowledge_retriever=retriever,
        process_repo=process_repo,
        memory_repo=memory_repo,
        tool_executor=tool_executor,
        search_provider=search_provider,
    )
    app.state.search_provider = search_provider

    from flydesk.tools.document_tools import DocumentToolExecutor

    doc_executor = DocumentToolExecutor(file_storage, file_repo=file_repo)
    builtin_executor.set_document_executor(doc_executor)

    # Conversation memory store
    from fireflyframework_genai.memory import MemoryManager
    from fireflyframework_genai.memory.store import InMemoryStore

    if config.memory_backend == "postgres" and "sqlite" not in config.database_url:
        from fireflyframework_genai.memory.database_store import PostgreSQLStore

        memory_store = PostgreSQLStore(url=config.database_url)
        await memory_store.initialize()
    else:
        if config.memory_backend == "postgres":
            logger.warning(
                "memory_backend='postgres' but database_url is SQLite; "
                "falling back to in-memory store.",
            )
        memory_store = InMemoryStore()

    memory_manager = MemoryManager(
        store=memory_store,
        max_conversation_tokens=config.memory_max_tokens,
        summarize_threshold=config.memory_summarize_threshold,
    )

    from flydesk.agent.genai_bridge import DeskAgentFactory

    agent_factory = DeskAgentFactory(llm_repo, memory_manager=memory_manager, config=config)

    # Discovery engines (process + system)
    from flydesk.jobs.handlers import ProcessDiscoveryHandler
    from flydesk.processes.discovery import ProcessDiscoveryEngine

    discovery_engine = ProcessDiscoveryEngine(
        agent_factory=agent_factory,
        process_repo=process_repo,
        catalog_repo=catalog_repo,
        knowledge_graph=knowledge_graph,
        audit_logger=audit_logger,
    )
    job_runner.register_handler("process_discovery", ProcessDiscoveryHandler(discovery_engine))
    app.state.discovery_engine = discovery_engine
    app.state.process_repo = process_repo
    app.dependency_overrides[get_process_repo] = lambda: process_repo

    from flydesk.catalog.discovery import SystemDiscoveryEngine
    from flydesk.jobs.handlers import SystemDiscoveryHandler

    system_discovery_engine = SystemDiscoveryEngine(
        agent_factory=agent_factory,
        catalog_repo=catalog_repo,
        knowledge_graph=knowledge_graph,
        audit_logger=audit_logger,
    )
    job_runner.register_handler("system_discovery", SystemDiscoveryHandler(system_discovery_engine))
    app.state.system_discovery_engine = system_discovery_engine

    # KG extraction
    from flydesk.jobs.handlers import KGExtractSingleHandler, KGRecomputeHandler
    from flydesk.knowledge.kg_extractor import KGExtractor

    kg_extractor = KGExtractor(agent_factory)
    job_runner.register_handler("kg_recompute", KGRecomputeHandler(catalog_repo, knowledge_graph, kg_extractor))
    job_runner.register_handler("kg_extract_single", KGExtractSingleHandler(catalog_repo, knowledge_graph, kg_extractor))
    app.state.kg_extractor = kg_extractor

    # Document analyser
    from flydesk.knowledge.analyzer import DocumentAnalyzer

    document_analyzer = DocumentAnalyzer(agent_factory)
    app.dependency_overrides[get_document_analyzer] = lambda: document_analyzer

    # Auto-trigger service
    from flydesk.triggers.auto_trigger import AutoTriggerService

    auto_trigger = AutoTriggerService(
        config, job_runner, auto_kg_extract=auto_kg_extract, settings_repo=settings_repo,
    )
    app.state.auto_trigger = auto_trigger
    app.state.auto_kg_extract = auto_kg_extract
    app.dependency_overrides[get_auto_trigger] = lambda: auto_trigger
    builtin_executor.set_auto_trigger(auto_trigger)

    # Agent customization
    from flydesk.agent.customization import AgentCustomizationService

    customization_service = AgentCustomizationService(settings_repo)
    app.state.customization_service = customization_service

    desk_agent = DeskAgent(
        context_enricher=context_enricher,
        prompt_builder=prompt_builder,
        tool_factory=tool_factory,
        widget_parser=widget_parser,
        audit_logger=audit_logger,
        agent_name=config.agent_name,
        company_name=config.company_name or None,
        tool_executor=tool_executor,
        builtin_executor=builtin_executor,
        file_repo=file_repo,
        file_storage=file_storage,
        confirmation_service=confirmation_service,
        conversation_repo=conversation_repo,
        agent_factory=agent_factory,
        catalog_repo=catalog_repo,
        customization_service=customization_service,
        settings_repo=settings_repo,
        feedback_repo=feedback_repo,
        custom_tool_repo=custom_tool_repo,
        sandbox_executor=sandbox_executor,
    )
    app.state.desk_agent = desk_agent
    app.state.context_enricher = context_enricher
    app.state.agent_factory = agent_factory
    app.state.llm_repo = llm_repo
    app.state.settings_repo = settings_repo

    return {
        "auto_trigger": auto_trigger,
        "memory_store": memory_store,
    }


# ---------------------------------------------------------------------------
# Auth / OIDC
# ---------------------------------------------------------------------------


def _init_auth(
    app: FastAPI,
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Wire OIDC, git provider, and local user repository dependencies."""
    from flydesk.auth.oidc import OIDCClient as _OIDCClientCls
    from flydesk.auth.repository import OIDCProviderRepository

    oidc_repo = OIDCProviderRepository(session_factory, config.credential_encryption_key)
    app.dependency_overrides[get_oidc_repo] = lambda: oidc_repo
    app.state.oidc_repo = oidc_repo

    from flydesk.knowledge.git_provider_repository import GitProviderRepository

    git_provider_repo = GitProviderRepository(session_factory, config.credential_encryption_key)
    app.dependency_overrides[get_git_provider_repo] = lambda: git_provider_repo

    if config.oidc_issuer_url:
        _default_oidc_client = _OIDCClientCls(
            issuer_url=config.oidc_issuer_url,
            client_id=config.oidc_client_id,
            client_secret=config.oidc_client_secret,
        )
        app.dependency_overrides[get_oidc_client] = lambda: _default_oidc_client

    from flydesk.auth.local_user_repository import LocalUserRepository

    local_user_repo = LocalUserRepository(session_factory)
    app.state.local_user_repo = local_user_repo
    app.dependency_overrides[get_local_user_repo] = lambda: local_user_repo


# ---------------------------------------------------------------------------
# Default workspace bootstrap
# ---------------------------------------------------------------------------

DEFAULT_WORKSPACE_ID = "ws-flydesk-internals"


async def _ensure_default_workspace(
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Ensure the 'Flydesk Internals' default workspace exists (idempotent).

    Uses a stable ID so the workspace is the same across restarts.
    Returns the workspace ID.
    """
    from flydesk.models.workspace import WorkspaceRow

    async with session_factory() as session:
        existing = await session.get(WorkspaceRow, DEFAULT_WORKSPACE_ID)
        if existing is not None:
            logger.debug("Default workspace already exists.")
            return DEFAULT_WORKSPACE_ID

        row = WorkspaceRow(
            id=DEFAULT_WORKSPACE_ID,
            name="Flydesk Internals",
            description="System documentation and internal knowledge",
            is_system=True,
        )
        session.add(row)
        await session.commit()
        logger.info("Created default workspace 'Flydesk Internals'.")

    return DEFAULT_WORKSPACE_ID


# ---------------------------------------------------------------------------
# Platform documentation auto-indexing
# ---------------------------------------------------------------------------


async def _seed_platform_docs(
    config: DeskConfig,
    indexer: Any,
    catalog_repo: CatalogRepository,
    default_workspace_ids: list[str] | None = None,
) -> None:
    """Auto-index platform documentation from the docs/ directory."""
    ws_ids = default_workspace_ids or []
    try:
        if config.docs_auto_index:
            from flydesk.knowledge.docs_loader import DocsLoader

            docs_path = config.docs_path
            docs = DocsLoader.load_from_directory(docs_path, default_workspace_ids=ws_ids)
            if docs:
                existing_docs: dict[str, str] = {}
                try:
                    all_docs = await catalog_repo.list_knowledge_documents()
                    for edoc in all_docs:
                        meta = edoc.get("metadata") if isinstance(edoc, dict) else getattr(edoc, "metadata", None)
                        if meta and isinstance(meta, dict) and "content_hash" in meta:
                            doc_id = edoc.get("id") if isinstance(edoc, dict) else getattr(edoc, "id", None)
                            if doc_id:
                                existing_docs[doc_id] = meta["content_hash"]
                except Exception:
                    logger.debug("Could not fetch existing docs for change detection.", exc_info=True)

                new_docs, updated_docs, removed_ids = DocsLoader.detect_changes(
                    docs_path, existing_docs
                )

                # Assign default workspace and publish status to new and updated docs
                for doc in new_docs:
                    doc.workspace_ids = list(ws_ids)
                    doc.status = DocumentStatus.PUBLISHED
                for doc in updated_docs:
                    doc.workspace_ids = list(ws_ids)
                    doc.status = DocumentStatus.PUBLISHED

                for doc in new_docs:
                    try:
                        await indexer.index_document(doc)
                        logger.debug("Indexed new doc: %s", doc.id)
                    except Exception:
                        logger.debug("Skipping doc %s (may already exist).", doc.id)

                for doc in updated_docs:
                    try:
                        await indexer.delete_document(doc.id)
                        await indexer.index_document(doc)
                        logger.debug("Re-indexed updated doc: %s", doc.id)
                    except Exception:
                        logger.debug("Failed to update doc %s.", doc.id, exc_info=True)

                for doc_id in removed_ids:
                    try:
                        await indexer.delete_document(doc_id)
                        logger.debug("Removed stale doc: %s", doc_id)
                    except Exception:
                        logger.debug("Failed to remove doc %s.", doc_id, exc_info=True)

                logger.info(
                    "Docs auto-index complete: %d new, %d updated, %d removed.",
                    len(new_docs), len(updated_docs), len(removed_ids),
                )
            else:
                from flydesk.seeds.platform_docs import seed_platform_docs

                await seed_platform_docs(indexer, docs_path=docs_path)
                logger.info("Platform documentation seeded (fallback).")
        else:
            from flydesk.seeds.platform_docs import seed_platform_docs

            await seed_platform_docs(indexer, docs_path=config.docs_path)
            logger.info("Platform documentation seeded into knowledge base.")
    except Exception:
        logger.debug("Platform docs seeding skipped (non-fatal).", exc_info=True)


# ---------------------------------------------------------------------------
# Workflow engine
# ---------------------------------------------------------------------------


async def _init_workflows(
    app: FastAPI,
    session_factory: async_sessionmaker,
) -> dict[str, Any]:
    """Wire workflow engine, repository, and scheduler."""
    from flydesk.workflows.repository import WorkflowRepository
    from flydesk.workflows.engine import WorkflowEngine
    from flydesk.workflows.scheduler import WorkflowScheduler

    wf_repo = WorkflowRepository(session_factory)
    wf_engine = WorkflowEngine(wf_repo)
    wf_scheduler = WorkflowScheduler(wf_repo, wf_engine)
    await wf_scheduler.start()

    app.dependency_overrides[get_workflow_repo] = lambda: wf_repo
    app.dependency_overrides[get_workflow_engine] = lambda: wf_engine

    return {
        "workflow_repo": wf_repo,
        "workflow_engine": wf_engine,
        "workflow_scheduler": wf_scheduler,
    }


# ---------------------------------------------------------------------------
# Email channel
# ---------------------------------------------------------------------------


async def _init_email_channel(
    app: FastAPI,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    settings_repo: Any,
    file_repo: Any,
    file_storage: Any,
    content_extractor: Any,
) -> None:
    """Create and register the email channel adapter if email is enabled.

    Reads email settings from the database.  When the channel is disabled the
    function logs an informational message and returns without registering
    anything -- the rest of the application continues to work normally.
    """
    from flydesk.channels.router import ChannelRouter
    from flydesk.email.channel_adapter import EmailChannelAdapter
    from flydesk.email.identity import EmailIdentityResolver
    from flydesk.email.threading import EmailThreadTracker

    # Read persisted email settings to decide whether to enable.
    email_settings = await settings_repo.get_email_settings()

    # Always create a ChannelRouter even if no channels are enabled yet,
    # so other code can safely depend on it.
    router = ChannelRouter()

    if not email_settings.enabled:
        logger.info("Email channel is disabled; skipping adapter registration.")
        app.state.channel_router = router
        app.dependency_overrides[get_channel_router] = lambda: router
        return

    # Build the email transport adapter based on configured provider.
    provider = email_settings.provider.lower()
    if provider == "ses":
        from flydesk.email.adapters.ses_adapter import SESEmailAdapter

        email_port = SESEmailAdapter(
            region=email_settings.provider_region or "us-east-1",
        )
    else:
        # Default to Resend.
        from flydesk.email.adapters.resend_adapter import ResendEmailAdapter

        email_port = ResendEmailAdapter(api_key=email_settings.provider_api_key)

    identity_resolver = EmailIdentityResolver(session_factory)
    thread_tracker = EmailThreadTracker(session_factory)

    adapter = EmailChannelAdapter(
        email_port=email_port,
        identity_resolver=identity_resolver,
        thread_tracker=thread_tracker,
        settings_repo=settings_repo,
        file_repo=file_repo,
        file_storage=file_storage,
        content_extractor=content_extractor,
    )

    router.register("email", adapter)

    app.state.channel_router = router
    app.state.email_channel_adapter = adapter
    app.dependency_overrides[get_channel_router] = lambda: router
    app.dependency_overrides[get_email_channel_adapter] = lambda: adapter

    logger.info("Email channel registered (provider=%s).", provider)


# ---------------------------------------------------------------------------
# Lifespan orchestrator
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise database and wire dependency overrides on startup."""
    config = get_config()
    ctx = _ShutdownContext()

    # 1. Database
    engine, session_factory = await _init_database(config)
    ctx.closables.append(engine)

    # 2. Core repositories
    repos = await _init_repositories(app, config, session_factory)

    # 3. File system and exports
    files = _init_file_system(app, config, session_factory)

    # 4. Security (KMS, credential store)
    sec = _init_security(app, config, repos["catalog_repo"])

    # 5. Shared HTTP client
    import httpx

    http_client = httpx.AsyncClient()
    app.state.http_client = http_client
    ctx.closables.append(http_client)

    # 6. Knowledge (embeddings, indexer, vector store)
    knowledge = await _init_knowledge(
        app, config, session_factory,
        settings_repo=repos["settings_repo"],
        llm_repo=repos["llm_repo"],
        http_client=http_client,
    )
    if knowledge["vector_store"] is not None:
        ctx.closables.append(knowledge["vector_store"])

    # 7. Background jobs and indexing queue
    jobs = await _init_jobs(
        app, config, session_factory, knowledge["indexer"],
        doc_source_repo=repos["doc_source_repo"],
    )
    ctx.closables.append(jobs["indexing_consumer"])
    ctx.closables.append(jobs["indexing_producer"])
    ctx.closables.append(jobs["job_runner"])

    # 8. Agent and intelligence layer
    agent_ctx = await _init_agent(
        app, config, session_factory,
        catalog_repo=repos["catalog_repo"],
        audit_logger=repos["audit_logger"],
        conversation_repo=repos["conversation_repo"],
        settings_repo=repos["settings_repo"],
        memory_repo=repos["memory_repo"],
        llm_repo=repos["llm_repo"],
        embedding_provider=knowledge["embedding_provider"],
        vector_store=knowledge["vector_store"],
        indexer=knowledge["indexer"],
        job_runner=jobs["job_runner"],
        auto_kg_extract=knowledge["auto_kg_extract"],
        kms=sec["kms"],
        cred_store=sec["cred_store"],
        file_repo=files["file_repo"],
        file_storage=files["file_storage"],
        http_client=http_client,
        feedback_repo=repos["feedback_repo"],
        custom_tool_repo=repos["custom_tool_repo"],
        sandbox_executor=repos["sandbox_executor"],
    )
    ctx.closables.append(agent_ctx["auto_trigger"])
    if hasattr(agent_ctx["memory_store"], "close"):
        ctx.closables.append(agent_ctx["memory_store"])

    # 9. Workflows
    workflows = await _init_workflows(app, session_factory)
    ctx.closables.append(workflows["workflow_scheduler"])

    # 10. Email channel (conditionally enabled)
    await _init_email_channel(
        app,
        session_factory,
        settings_repo=repos["settings_repo"],
        file_repo=files["file_repo"],
        file_storage=files["file_storage"],
        content_extractor=files["content_extractor"],
    )

    # 11. Auth / OIDC
    _init_auth(app, config, session_factory)

    # 12. Store shared state
    app.dependency_overrides[get_session_factory] = lambda: session_factory
    app.state.config = config
    app.state.session_factory = session_factory
    app.state.conversation_repo = repos["conversation_repo"]
    app.state.started_at = datetime.now(timezone.utc)

    # 13. Ensure default workspace exists
    default_ws_id = await _ensure_default_workspace(session_factory)

    # 14. Auto-index platform docs (assigned to default workspace)
    await _seed_platform_docs(
        config, knowledge["indexer"], repos["catalog_repo"],
        default_workspace_ids=[default_ws_id],
    )

    logger.info(
        "Firefly Desk started (dev_mode=%s, db=%s, memory=%s)",
        config.dev_mode,
        config.database_url.split("@")[-1] if "@" in config.database_url else config.database_url,
        config.memory_backend,
    )

    yield

    # Stop ngrok tunnel if active
    tunnel_manager = getattr(app.state, "tunnel_manager", None)
    if tunnel_manager is not None:
        tunnel_manager.stop()

    search_provider = getattr(app.state, "search_provider", None)
    if search_provider and hasattr(search_provider, "aclose"):
        await search_provider.aclose()

    await ctx.shutdown()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the Firefly Desk FastAPI application."""
    config = get_config()

    app = FastAPI(
        title="Firefly Desk",
        version=flydesk.__version__,
        description="Backoffice as Agent",
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def global_exception_handler(_request: _Request, exc: Exception):
        logger.error("Unhandled exception: %s", exc, exc_info=True)
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    # CORS -- never use wildcard with credentials
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth middleware (skipped in dev mode -- a dev user session is injected)
    if config.dev_mode:
        from flydesk.auth.dev import DevAuthMiddleware

        app.add_middleware(DevAuthMiddleware)
    else:
        oidc_client = None
        provider_profile = None
        if config.oidc_issuer_url:
            from flydesk.auth.oidc import OIDCClient
            from flydesk.auth.providers import get_provider

            oidc_client = OIDCClient(
                issuer_url=config.oidc_issuer_url,
                client_id=config.oidc_client_id,
                client_secret=config.oidc_client_secret,
            )
            provider_profile = get_provider(config.oidc_provider_type)

        app.add_middleware(
            AuthMiddleware,
            roles_claim=config.oidc_roles_claim,
            permissions_claim=config.oidc_permissions_claim,
            oidc_client=oidc_client,
            provider_profile=provider_profile,
            local_jwt_secret=config.effective_jwt_secret,
        )

    # Routers
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(setup_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(catalog_router)
    app.include_router(credentials_router)
    app.include_router(knowledge_router)
    app.include_router(audit_router)
    app.include_router(exports_router)
    app.include_router(feedback_router)
    app.include_router(files_router)
    app.include_router(llm_providers_router)
    app.include_router(llm_status_router)
    app.include_router(oidc_providers_router)
    app.include_router(settings_router)
    app.include_router(dashboard_router)
    app.include_router(users_router)
    app.include_router(roles_router)
    app.include_router(prompts_router)
    app.include_router(tools_admin_router)
    app.include_router(sso_mappings_router)
    app.include_router(jobs_router)
    app.include_router(processes_router)
    app.include_router(custom_tools_router)
    app.include_router(openapi_import_router)
    app.include_router(github_router)
    app.include_router(git_import_router)
    app.include_router(git_providers_router)
    app.include_router(help_docs_router)
    app.include_router(memory_router)
    app.include_router(workspace_router)
    app.include_router(document_sources_router)
    app.include_router(cloud_import_router)
    app.include_router(email_inbound_router)
    app.include_router(email_settings_router)
    app.include_router(webhooks_router)
    app.include_router(notifications_router)

    return app
