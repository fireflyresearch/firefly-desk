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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import flydek
from flydek.api.audit import get_audit_logger
from flydek.api.audit import router as audit_router
from flydek.api.catalog import get_catalog_repo
from flydek.api.catalog import router as catalog_router
from flydek.api.chat import router as chat_router
from flydek.api.conversations import get_conversation_repo
from flydek.api.conversations import router as conversations_router
from flydek.api.credentials import get_credential_store
from flydek.api.credentials import router as credentials_router
from flydek.api.health import router as health_router
from flydek.api.knowledge import get_knowledge_doc_store, get_knowledge_indexer
from flydek.api.knowledge import router as knowledge_router
from flydek.api.setup import router as setup_router
from flydek.audit.logger import AuditLogger
from flydek.auth.middleware import AuthMiddleware
from flydek.catalog.repository import CatalogRepository
from flydek.conversation.repository import ConversationRepository
from flydek.config import get_config
from flydek.db import create_engine_from_url, create_session_factory
from flydek.models import Base

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise database and wire dependency overrides on startup."""
    config = get_config()

    # Create engine and ensure tables exist
    engine = create_engine_from_url(config.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    # Wire dependency overrides
    catalog_repo = CatalogRepository(session_factory)
    audit_logger = AuditLogger(session_factory)
    conversation_repo = ConversationRepository(session_factory)

    app.dependency_overrides[get_catalog_repo] = lambda: catalog_repo
    app.dependency_overrides[get_audit_logger] = lambda: audit_logger
    app.dependency_overrides[get_conversation_repo] = lambda: conversation_repo

    # Credential store backed by catalog repo (reuses session factory)
    from flydek.api.credentials import CredentialStore

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
    from flydek.api.knowledge import KnowledgeDocumentStore

    class _LiveDocStore(KnowledgeDocumentStore):
        async def list_documents(self):
            return await catalog_repo.list_knowledge_documents()

        async def get_document(self, document_id: str):
            return await catalog_repo.get_knowledge_document(document_id)

    doc_store = _LiveDocStore()
    app.dependency_overrides[get_knowledge_doc_store] = lambda: doc_store

    # Knowledge indexer stub (placeholder -- no real embeddings in dev mode)
    from flydek.knowledge.indexer import KnowledgeIndexer

    class _NoOpEmbedding:
        async def embed(self, texts):
            return [[0.0] * config.embedding_dimensions for _ in texts]

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=_NoOpEmbedding(),
    )
    app.dependency_overrides[get_knowledge_indexer] = lambda: indexer

    # Wire the DeskAgent and its dependencies
    from flydek.agent.context import ContextEnricher
    from flydek.agent.desk_agent import DeskAgent
    from flydek.agent.prompt import SystemPromptBuilder
    from flydek.knowledge.graph import KnowledgeGraph
    from flydek.knowledge.retriever import KnowledgeRetriever
    from flydek.tools.factory import ToolFactory
    from flydek.widgets.parser import WidgetParser

    knowledge_graph = KnowledgeGraph(session_factory)
    retriever = KnowledgeRetriever(session_factory, _NoOpEmbedding())
    context_enricher = ContextEnricher(
        knowledge_graph=knowledge_graph,
        retriever=retriever,
        entity_limit=config.kg_max_entities_in_context,
        retrieval_top_k=config.rag_top_k,
    )
    prompt_builder = SystemPromptBuilder()
    tool_factory = ToolFactory()
    widget_parser = WidgetParser()

    desk_agent = DeskAgent(
        context_enricher=context_enricher,
        prompt_builder=prompt_builder,
        tool_factory=tool_factory,
        widget_parser=widget_parser,
        audit_logger=audit_logger,
        agent_name=config.agent_name,
    )
    app.state.desk_agent = desk_agent

    # Store config, session factory, and conversation repo in app state
    app.state.config = config
    app.state.session_factory = session_factory
    app.state.conversation_repo = conversation_repo

    # Auto-seed platform documentation into the knowledge base (idempotent)
    try:
        from flydek.seeds.platform_docs import seed_platform_docs

        await seed_platform_docs(indexer)
        logger.info("Platform documentation seeded into knowledge base.")
    except Exception:
        logger.debug("Platform docs seeding skipped (non-fatal).", exc_info=True)

    logger.info(
        "Firefly Desk started (dev_mode=%s, db=%s)",
        config.dev_mode,
        config.database_url.split("@")[-1] if "@" in config.database_url else config.database_url,
    )

    yield

    # Shutdown
    await engine.dispose()
    logger.info("Firefly Desk shutdown complete.")


def create_app() -> FastAPI:
    """Create and configure the Firefly Desk FastAPI application."""
    config = get_config()

    app = FastAPI(
        title="Firefly Desk",
        version=flydek.__version__,
        description="Backoffice as Agent",
        lifespan=lifespan,
    )

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
        from flydek.auth.dev import DevAuthMiddleware

        app.add_middleware(DevAuthMiddleware)
    else:
        app.add_middleware(
            AuthMiddleware,
            roles_claim=config.oidc_roles_claim,
            permissions_claim=config.oidc_permissions_claim,
        )

    # Routers
    app.include_router(health_router)
    app.include_router(setup_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    app.include_router(catalog_router)
    app.include_router(credentials_router)
    app.include_router(knowledge_router)
    app.include_router(audit_router)

    return app
