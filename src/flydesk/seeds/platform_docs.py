# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Platform documentation seed data for the knowledge base.

Documents are loaded from a ``docs/`` directory of Markdown files when
available.  If no docs directory exists or it contains no ``.md`` files,
a hardcoded fallback list is used instead.
"""

from __future__ import annotations

import logging
from pathlib import Path

from flydesk.knowledge.docs_loader import DocsLoader
from flydesk.knowledge.models import KnowledgeDocument

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback documents (used only when no docs/ directory exists)
# ---------------------------------------------------------------------------

_FALLBACK_DOCUMENTS: list[KnowledgeDocument] = [
    KnowledgeDocument(
        id="doc-platform-overview",
        title="Firefly Desk Overview",
        content=(
            "Firefly Desk is a conversational backoffice platform designed to"
            " fundamentally change how operations teams interact with their backend"
            " systems. Rather than requiring operators to navigate through multiple"
            " admin panels, memorize API endpoints, or context-switch between"
            " dashboards, Firefly Desk consolidates all of these interactions into a"
            " single, natural-language interface. The platform includes process"
            " discovery to automatically map business workflows from registered"
            " systems and knowledge, and the agent's identity and behavior can be"
            " fully customized through the admin console."
        ),
        source="platform-docs://overview",
        tags=["platform", "documentation", "overview"],
        metadata={"document_type": "PLATFORM_DOCS", "section": "overview"},
    ),
    KnowledgeDocument(
        id="doc-platform-knowledge-base",
        title="Firefly Desk Knowledge Base",
        content=(
            "The Knowledge Base gives Ember access to operational documentation,"
            " runbooks, policies, and domain-specific information that is not"
            " available through the Service Catalog's structured API metadata."
            " Knowledge graph entities and relationships are automatically extracted"
            " from documents and catalog systems using LLM-based analysis, and can"
            " be recomputed when auto-analyze is enabled."
        ),
        source="platform-docs://knowledge-base",
        tags=["platform", "documentation", "knowledge-base", "rag"],
        metadata={"document_type": "PLATFORM_DOCS", "section": "knowledge-base"},
    ),
]


def load_platform_docs(docs_path: str | Path = "docs") -> list[KnowledgeDocument]:
    """Load platform documents from *docs_path*, falling back to hardcoded list.

    Returns the list of documents to index.
    """
    docs_path = Path(docs_path)
    if docs_path.is_dir():
        documents = DocsLoader.load_from_directory(docs_path)
        if documents:
            logger.info(
                "Loaded %d platform doc(s) from %s.", len(documents), docs_path
            )
            return documents

    logger.info("No docs directory or no .md files found; using fallback documents.")
    return list(_FALLBACK_DOCUMENTS)


async def seed_platform_docs(
    knowledge_indexer,
    catalog_repo=None,
    *,
    docs_path: str | Path = "docs",
) -> None:
    """Seed platform documentation into the knowledge base.

    Loads documents from the *docs_path* directory (falling back to
    hardcoded documents) and indexes them idempotently.
    """
    documents = load_platform_docs(docs_path)

    for doc in documents:
        try:
            if catalog_repo:
                existing = await catalog_repo.get_knowledge_document(doc.id)
                if existing is not None:
                    logger.debug("Platform doc %s already exists, skipping.", doc.id)
                    continue
            await knowledge_indexer.index_document(doc)
            logger.debug("Indexed platform doc: %s", doc.id)
        except Exception:
            logger.debug("Skipping platform doc %s (may already exist).", doc.id)
            continue

    logger.info(
        "Platform documentation seeding complete (%d documents).", len(documents)
    )


async def unseed_platform_docs(
    knowledge_indexer,
    *,
    docs_path: str | Path = "docs",
) -> None:
    """Remove all platform documentation from the knowledge base."""
    documents = load_platform_docs(docs_path)
    for doc in documents:
        try:
            await knowledge_indexer.delete_document(doc.id)
        except Exception:
            continue
    logger.info("Platform documentation removed.")
