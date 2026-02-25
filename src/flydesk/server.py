# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""FastAPI application factory with proper lifecycle management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request as _Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import flydesk
from flydesk.api.audit import get_audit_logger
from flydesk.api.audit import router as audit_router
from flydesk.api.auth import get_oidc_client as auth_get_oidc_client
from flydesk.api.auth import get_oidc_repo as auth_get_oidc_repo
from flydesk.api.auth import router as auth_router
from flydesk.api.catalog import get_auto_trigger as catalog_get_auto_trigger
from flydesk.api.catalog import get_catalog_repo
from flydesk.api.catalog import router as catalog_router
from flydesk.api.custom_tools import get_custom_tool_repo, get_sandbox_executor
from flydesk.api.custom_tools import router as custom_tools_router
from flydesk.api.git_import import router as git_import_router
from flydesk.api.git_providers import get_git_provider_repo
from flydesk.api.git_providers import router as git_providers_router
from flydesk.api.github import router as github_router
from flydesk.api.help_docs import router as help_docs_router
from flydesk.api.openapi_import import get_catalog_repo as openapi_get_catalog
from flydesk.api.openapi_import import router as openapi_import_router
from flydesk.api.chat import router as chat_router
from flydesk.api.conversations import get_conversation_repo
from flydesk.api.conversations import router as conversations_router
from flydesk.api.credentials import get_credential_store
from flydesk.api.credentials import router as credentials_router
from flydesk.api.dashboard import get_audit_logger as dashboard_get_audit
from flydesk.api.dashboard import get_catalog_repo as dashboard_get_catalog
from flydesk.api.dashboard import get_llm_repo as dashboard_get_llm
from flydesk.api.dashboard import get_session_factory as dashboard_get_session
from flydesk.api.dashboard import router as dashboard_router
from flydesk.api.exports import get_export_repo, get_export_service, get_export_storage
from flydesk.api.exports import router as exports_router
from flydesk.api.feedback import get_audit_logger as feedback_get_audit
from flydesk.api.feedback import router as feedback_router
from flydesk.api.files import get_content_extractor, get_file_repo, get_file_storage
from flydesk.api.files import router as files_router
from flydesk.api.health import router as health_router
from flydesk.api.jobs import get_job_repo, get_job_runner
from flydesk.api.jobs import router as jobs_router
from flydesk.api.knowledge import (
    get_auto_trigger as knowledge_get_auto_trigger,
    get_indexing_producer,
    get_knowledge_doc_store,
    get_knowledge_graph,
    get_knowledge_importer,
    get_knowledge_indexer,
)
from flydesk.api.knowledge import router as knowledge_router
from flydesk.api.llm_providers import get_llm_repo
from flydesk.api.llm_providers import router as llm_providers_router
from flydesk.api.processes import get_process_repo
from flydesk.api.processes import router as processes_router
from flydesk.api.oidc_providers import get_oidc_repo as admin_get_oidc_repo
from flydesk.api.oidc_providers import router as oidc_providers_router
from flydesk.api.prompts import get_settings_repo as prompts_get_settings
from flydesk.api.prompts import router as prompts_router
from flydesk.api.roles import get_role_repo
from flydesk.api.roles import router as roles_router
from flydesk.api.settings import get_settings_repo
from flydesk.api.settings import router as settings_router
from flydesk.api.setup import router as setup_router
from flydesk.api.sso_mappings import get_settings_repo as sso_mappings_get_settings
from flydesk.api.sso_mappings import router as sso_mappings_router
from flydesk.api.tools_admin import get_catalog_repo as tools_get_catalog
from flydesk.api.tools_admin import get_settings_repo as tools_get_settings
from flydesk.api.tools_admin import router as tools_admin_router
from flydesk.api.users import get_local_user_repo as users_get_local_user_repo
from flydesk.api.users import get_session_factory as users_get_session
from flydesk.api.users import get_settings_repo as users_get_settings
from flydesk.api.users import router as users_router
from flydesk.audit.logger import AuditLogger
from flydesk.auth.middleware import AuthMiddleware
from flydesk.catalog.repository import CatalogRepository
from flydesk.conversation.repository import ConversationRepository
from flydesk.config import get_config
from flydesk.db import create_engine_from_url, create_session_factory
from flydesk.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise database and wire dependency overrides on startup."""
    config = get_config()

    # Create engine and ensure tables exist
    engine = create_engine_from_url(config.database_url)

    async with engine.begin() as conn:
        # Enable pgvector extension for PostgreSQL
        if "postgresql" in config.database_url:
            from sqlalchemy import text

            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    # RBAC: seed built-in roles and make the repository available to middleware
    from flydesk.rbac.repository import RoleRepository

    role_repo = RoleRepository(session_factory)
    try:
        await role_repo.seed_builtin_roles()
    except Exception:
        logger.warning("Failed to seed built-in roles (non-fatal).", exc_info=True)
    app.state.role_repo = role_repo
    app.dependency_overrides[get_role_repo] = lambda: role_repo

    # Wire dependency overrides
    catalog_repo = CatalogRepository(session_factory)
    audit_logger = AuditLogger(session_factory)
    conversation_repo = ConversationRepository(session_factory)

    # Settings repository
    from flydesk.settings.repository import SettingsRepository

    settings_repo = SettingsRepository(session_factory)
    app.dependency_overrides[get_settings_repo] = lambda: settings_repo
    app.dependency_overrides[prompts_get_settings] = lambda: settings_repo
    app.dependency_overrides[tools_get_settings] = lambda: settings_repo
    app.dependency_overrides[sso_mappings_get_settings] = lambda: settings_repo

    # Custom tools repository and sandbox executor
    from flydesk.tools.custom_repository import CustomToolRepository
    from flydesk.tools.sandbox import SandboxExecutor

    custom_tool_repo = CustomToolRepository(session_factory)
    sandbox_executor = SandboxExecutor()
    app.dependency_overrides[get_custom_tool_repo] = lambda: custom_tool_repo
    app.dependency_overrides[get_sandbox_executor] = lambda: sandbox_executor

    app.dependency_overrides[get_catalog_repo] = lambda: catalog_repo
    app.dependency_overrides[tools_get_catalog] = lambda: catalog_repo
    app.dependency_overrides[openapi_get_catalog] = lambda: catalog_repo
    app.dependency_overrides[get_audit_logger] = lambda: audit_logger
    app.dependency_overrides[feedback_get_audit] = lambda: audit_logger
    app.dependency_overrides[get_conversation_repo] = lambda: conversation_repo

    # LLM provider repository
    from flydesk.llm.repository import LLMProviderRepository

    llm_repo = LLMProviderRepository(session_factory, config.credential_encryption_key)
    app.dependency_overrides[get_llm_repo] = lambda: llm_repo

    # File upload dependencies
    from flydesk.files.extractor import ContentExtractor
    from flydesk.files.repository import FileUploadRepository
    from flydesk.files.storage import LocalFileStorage

    file_repo = FileUploadRepository(session_factory)
    file_storage = LocalFileStorage(config.file_storage_path)
    content_extractor = ContentExtractor()

    app.dependency_overrides[get_file_repo] = lambda: file_repo
    app.dependency_overrides[get_file_storage] = lambda: file_storage
    app.dependency_overrides[get_content_extractor] = lambda: content_extractor

    # Export dependencies
    from flydesk.exports.repository import ExportRepository
    from flydesk.exports.service import ExportService

    export_repo = ExportRepository(session_factory)
    export_service = ExportService(export_repo, file_storage)
    app.dependency_overrides[get_export_repo] = lambda: export_repo
    app.dependency_overrides[get_export_service] = lambda: export_service
    app.dependency_overrides[get_export_storage] = lambda: file_storage

    # KMS provider for credential encryption
    from flydesk.security.kms import FernetKMSProvider, create_kms_provider

    kms = create_kms_provider(config)
    if isinstance(kms, FernetKMSProvider) and kms.is_dev_key:
        logger.warning(
            "Using dev encryption key. Set FLYDESK_CREDENTIAL_ENCRYPTION_KEY "
            "for production."
        )

    from flydesk.api.credentials import CredentialStore, get_kms

    app.dependency_overrides[get_kms] = lambda: kms

    # Credential store backed by catalog repo (reuses session factory)
    class _LiveCredentialStore(CredentialStore):
        async def list_credentials(self):
            return await catalog_repo.list_credentials()

        async def get_credential(self, credential_id: str):
            return await catalog_repo.get_credential(credential_id)

        async def create_credential(self, credential):
            return await catalog_repo.create_credential(credential)

        async def update_credential(self, credential):
            return await catalog_repo.update_credential(credential)

        async def delete_credential(self, credential_id: str):
            return await catalog_repo.delete_credential(credential_id)

    cred_store = _LiveCredentialStore()
    app.dependency_overrides[get_credential_store] = lambda: cred_store

    # Knowledge doc store stub (reads from DB)
    from flydesk.api.knowledge import KnowledgeDocumentStore

    class _LiveDocStore(KnowledgeDocumentStore):
        async def list_documents(self):
            return await catalog_repo.list_knowledge_documents()

        async def get_document(self, document_id: str):
            return await catalog_repo.get_knowledge_document(document_id)

        async def update_document(self, document_id, *, title=None, document_type=None, tags=None, content=None, status=None):
            return await catalog_repo.update_knowledge_document(
                document_id, title=title, document_type=document_type, tags=tags, content=content, status=status
            )

    doc_store = _LiveDocStore()
    app.dependency_overrides[get_knowledge_doc_store] = lambda: doc_store

    # Shared HTTP client for external API calls (embeddings, tool calls, imports).
    import httpx

    http_client = httpx.AsyncClient()
    app.state.http_client = http_client

    # Knowledge embedding provider — check DB settings first, then env vars.
    # Graceful fallback to zero vectors (keyword search) if no key available.
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

    # Instantiate the configured vector store backend
    try:
        vector_store = create_vector_store(config, session_factory)
    except Exception:
        logger.warning("Failed to create vector store; falling back to direct SQLAlchemy.", exc_info=True)
        vector_store = None

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
    )
    app.dependency_overrides[get_knowledge_indexer] = lambda: indexer

    # Background job system -- general-purpose job runner with typed handlers.
    # Initialised *before* the indexing queue so that the queue consumer can
    # route indexing tasks through the job system for tracking.
    from flydesk.jobs.handlers import IndexingJobHandler
    from flydesk.jobs.repository import JobRepository
    from flydesk.jobs.runner import JobRunner

    job_repo = JobRepository(session_factory)
    job_runner = JobRunner(job_repo)
    job_runner.register_handler("indexing", IndexingJobHandler(indexer))
    await job_runner.start()
    app.state.job_runner = job_runner
    app.state.job_repo = job_repo
    app.dependency_overrides[get_job_repo] = lambda: job_repo
    app.dependency_overrides[get_job_runner] = lambda: job_runner

    # Background indexing queue -- offloads embedding work from HTTP handlers.
    # The consumer handler delegates to the job system so that every indexing
    # task appears in the jobs list with progress tracking.
    from flydesk.knowledge.queue import IndexingTask, create_indexing_queue

    async def _handle_indexing_task(task: IndexingTask) -> None:
        """Consumer handler: submit indexing work through the job system."""
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

    # Wire the DeskAgent and its dependencies
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
        entity_limit=config.kg_max_entities_in_context,
        retrieval_top_k=config.rag_top_k,
    )
    prompt_registry = register_desk_prompts()
    prompt_builder = SystemPromptBuilder(prompt_registry)
    tool_factory = ToolFactory()
    widget_parser = WidgetParser()

    # Knowledge graph + importer dependency overrides
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

    # Safety confirmation service for high-risk tool calls.
    from flydesk.agent.confirmation import ConfirmationService

    confirmation_service = ConfirmationService()
    app.state.confirmation_service = confirmation_service

    from flydesk.processes.repository import ProcessRepository

    process_repo = ProcessRepository(session_factory)

    from flydesk.tools.builtin import BuiltinToolExecutor

    builtin_executor = BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
        knowledge_retriever=retriever,
        process_repo=process_repo,
    )

    # Wire document tool executor into built-in tools
    from flydesk.tools.document_tools import DocumentToolExecutor

    doc_executor = DocumentToolExecutor(file_storage)
    builtin_executor.set_document_executor(doc_executor)

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

    # Process discovery engine -- analyses catalog, KG, and KB to find processes.
    from flydesk.jobs.handlers import ProcessDiscoveryHandler
    from flydesk.processes.discovery import ProcessDiscoveryEngine

    discovery_engine = ProcessDiscoveryEngine(
        agent_factory=agent_factory,
        process_repo=process_repo,
        catalog_repo=catalog_repo,
        knowledge_graph=knowledge_graph,
    )
    job_runner.register_handler("process_discovery", ProcessDiscoveryHandler(discovery_engine))
    app.state.discovery_engine = discovery_engine
    app.state.process_repo = process_repo
    app.dependency_overrides[get_process_repo] = lambda: process_repo

    # KG extraction and recomputation handler
    from flydesk.jobs.handlers import KGRecomputeHandler
    from flydesk.knowledge.kg_extractor import KGExtractor

    kg_extractor = KGExtractor(agent_factory)
    kg_recompute_handler = KGRecomputeHandler(catalog_repo, knowledge_graph, kg_extractor)
    job_runner.register_handler("kg_recompute", kg_recompute_handler)
    app.state.kg_extractor = kg_extractor

    # Document analyser for GitHub import enrichment
    from flydesk.api.github import get_document_analyzer
    from flydesk.knowledge.analyzer import DocumentAnalyzer

    document_analyzer = DocumentAnalyzer(agent_factory)
    app.dependency_overrides[get_document_analyzer] = lambda: document_analyzer

    # Auto-trigger service (debounced triggers for KG recompute and process discovery)
    from flydesk.triggers.auto_trigger import AutoTriggerService

    auto_trigger = AutoTriggerService(config, job_runner)
    app.state.auto_trigger = auto_trigger
    app.dependency_overrides[knowledge_get_auto_trigger] = lambda: auto_trigger
    app.dependency_overrides[catalog_get_auto_trigger] = lambda: auto_trigger

    # Agent customization service
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
    )
    app.state.desk_agent = desk_agent

    # Dashboard API dependency overrides
    app.dependency_overrides[dashboard_get_catalog] = lambda: catalog_repo
    app.dependency_overrides[dashboard_get_audit] = lambda: audit_logger
    app.dependency_overrides[dashboard_get_llm] = lambda: llm_repo
    app.dependency_overrides[dashboard_get_session] = lambda: session_factory

    # Auth / OIDC dependency overrides
    from flydesk.auth.oidc import OIDCClient as _OIDCClientCls
    from flydesk.auth.repository import OIDCProviderRepository

    oidc_repo = OIDCProviderRepository(session_factory, config.credential_encryption_key)
    app.dependency_overrides[auth_get_oidc_repo] = lambda: oidc_repo
    app.dependency_overrides[admin_get_oidc_repo] = lambda: oidc_repo
    app.state.oidc_repo = oidc_repo

    # Git provider repository
    from flydesk.knowledge.git_provider_repository import GitProviderRepository

    git_provider_repo = GitProviderRepository(session_factory, config.credential_encryption_key)
    app.dependency_overrides[get_git_provider_repo] = lambda: git_provider_repo

    # Provide a default OIDCClient from config (may be overridden per-request)
    if config.oidc_issuer_url:
        _default_oidc_client = _OIDCClientCls(
            issuer_url=config.oidc_issuer_url,
            client_id=config.oidc_client_id,
            client_secret=config.oidc_client_secret,
        )
        app.dependency_overrides[auth_get_oidc_client] = lambda: _default_oidc_client

    # Local user repository
    from flydesk.auth.local_user_repository import LocalUserRepository
    from flydesk.api.auth import get_local_user_repo

    local_user_repo = LocalUserRepository(session_factory)
    app.state.local_user_repo = local_user_repo
    app.dependency_overrides[get_local_user_repo] = lambda: local_user_repo

    # Users API dependency overrides
    app.dependency_overrides[users_get_session] = lambda: session_factory
    app.dependency_overrides[users_get_settings] = lambda: settings_repo
    app.dependency_overrides[users_get_local_user_repo] = lambda: local_user_repo

    # Store config, session factory, and conversation repo in app state
    app.state.config = config
    app.state.session_factory = session_factory
    app.state.conversation_repo = conversation_repo
    app.state.started_at = datetime.now(timezone.utc)

    # Auto-seed / auto-index platform documentation from docs/ directory
    try:
        if config.docs_auto_index:
            from flydesk.knowledge.docs_loader import DocsLoader

            docs_path = config.docs_path
            docs = DocsLoader.load_from_directory(docs_path)
            if docs:
                # Build existing-docs map from the database for change detection
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
                # No docs/ directory or empty -- fall back to hardcoded seeding
                from flydesk.seeds.platform_docs import seed_platform_docs

                await seed_platform_docs(indexer, docs_path=docs_path)
                logger.info("Platform documentation seeded (fallback).")
        else:
            # Auto-index disabled -- use legacy seeding
            from flydesk.seeds.platform_docs import seed_platform_docs

            await seed_platform_docs(indexer, docs_path=config.docs_path)
            logger.info("Platform documentation seeded into knowledge base.")
    except Exception:
        logger.debug("Platform docs seeding skipped (non-fatal).", exc_info=True)

    logger.info(
        "Firefly Desk started (dev_mode=%s, db=%s, memory=%s)",
        config.dev_mode,
        config.database_url.split("@")[-1] if "@" in config.database_url else config.database_url,
        config.memory_backend,
    )

    yield

    # Shutdown -- cancel pending auto-triggers first, then stop the indexing
    # consumer (no new tasks enqueued), then the job runner (drain in-progress
    # jobs), then the producer.
    auto_trigger.cancel_pending()
    await indexing_consumer.stop()
    await indexing_producer.stop()
    await job_runner.stop()
    if vector_store is not None:
        await vector_store.close()
    if hasattr(memory_store, "close"):
        await memory_store.close()
    await http_client.aclose()
    await engine.dispose()
    logger.info("Firefly Desk shutdown complete.")


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

    return app
