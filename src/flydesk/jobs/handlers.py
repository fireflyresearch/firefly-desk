# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Job handler protocol and built-in handler implementations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Protocol, runtime_checkable

from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import KnowledgeDocument
from flydesk.knowledge.queue import IndexingTask

if TYPE_CHECKING:
    from flydesk.catalog.discovery import SystemDiscoveryEngine
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.knowledge.graph import KnowledgeGraph
    from flydesk.knowledge.kg_extractor import KGExtractor
    from flydesk.processes.discovery import ProcessDiscoveryEngine

logger = logging.getLogger(__name__)

# Type alias for the progress callback passed to handlers.
ProgressCallback = Callable[[int, str], Coroutine[Any, Any, None]]


@runtime_checkable
class JobHandler(Protocol):
    """Protocol that all job handlers must satisfy.

    Parameters passed to ``execute``:
        job_id: The unique identifier of the running job.
        payload: Arbitrary JSON-serialisable dict with handler-specific data.
        on_progress: Async callback ``(pct, message)`` to report progress.

    Returns:
        A result dict to persist with the completed job.
    """

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict: ...


class IndexingJobHandler:
    """Wraps the existing ``KnowledgeIndexer`` as a ``JobHandler``.

    The payload is expected to be a serialised ``IndexingTask``.
    """

    def __init__(self, indexer: KnowledgeIndexer) -> None:
        self._indexer = indexer

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Index a single knowledge document."""
        task = IndexingTask.model_validate(payload)
        await on_progress(10, f"Indexing document {task.document_id}")

        doc = KnowledgeDocument(
            id=task.document_id,
            title=task.title,
            content=task.content,
            document_type=task.document_type,
            source=task.source,
            tags=task.tags,
            metadata=task.metadata,
        )
        await self._indexer.index_document(doc)

        await on_progress(100, "Indexing complete")
        return {"document_id": task.document_id, "title": task.title}


class ProcessDiscoveryHandler:
    """Wraps ``ProcessDiscoveryEngine`` as a ``JobHandler``.

    Delegates the full discovery analysis pipeline to the engine, which
    gathers context, calls the LLM, parses results, and merges with
    existing processes.
    """

    def __init__(self, engine: ProcessDiscoveryEngine) -> None:
        self._engine = engine

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Run process discovery analysis."""
        return await self._engine._analyze(job_id, payload, on_progress)


class SystemDiscoveryHandler:
    """Wraps ``SystemDiscoveryEngine`` as a ``JobHandler``.

    Delegates the full discovery analysis pipeline to the engine, which
    gathers context from the catalog, knowledge graph, and knowledge base,
    calls the LLM, parses results, and merges with existing systems.
    """

    def __init__(self, engine: SystemDiscoveryEngine) -> None:
        self._engine = engine

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Run system discovery analysis."""
        return await self._engine._analyze(job_id, payload, on_progress)


class KGRecomputeHandler:
    """Recomputes the knowledge graph by extracting entities and relations
    from all knowledge documents via ``KGExtractor``.

    Iterates every document in the knowledge base, calls the LLM-based
    extractor for each, and upserts the resulting entities and relations
    into the ``KnowledgeGraph``.  Progress is reported per document.
    """

    def __init__(
        self,
        catalog_repo: CatalogRepository,
        knowledge_graph: KnowledgeGraph,
        extractor: KGExtractor,
    ) -> None:
        self._catalog_repo = catalog_repo
        self._knowledge_graph = knowledge_graph
        self._extractor = extractor

    async def execute(
        self,
        job_id: str,
        payload: dict,
        on_progress: ProgressCallback,
    ) -> dict:
        """Extract entities/relations from all documents and upsert into the KG."""
        from flydesk.knowledge.graph import Entity, Relation

        await on_progress(0, "Loading knowledge documents")

        docs = await self._catalog_repo.list_knowledge_documents()
        total = len(docs)

        if total == 0:
            await on_progress(100, "No documents to process")
            return {"entities_added": 0, "relations_added": 0, "documents_processed": 0}

        entities_added = 0
        relations_added = 0

        for i, doc in enumerate(docs):
            doc_title = getattr(doc, "title", "Untitled")
            doc_content = getattr(doc, "content", "")

            if not doc_content:
                logger.debug("Skipping empty document: %s", doc_title)
                pct = int((i + 1) / total * 100)
                await on_progress(pct, f"Skipped {doc_title} (empty)")
                continue

            try:
                entities, relations = await self._extractor.extract_from_document(
                    doc_content, doc_title
                )
            except Exception:
                logger.warning("Extraction failed for '%s'.", doc_title, exc_info=True)
                pct = int((i + 1) / total * 100)
                await on_progress(pct, f"Extraction failed for {doc_title}")
                continue

            for ent_dict in entities:
                entity = Entity(
                    id=ent_dict["id"],
                    entity_type=ent_dict["entity_type"],
                    name=ent_dict["name"],
                    properties=ent_dict.get("properties", {}),
                    source_system=ent_dict.get("source_system"),
                    confidence=ent_dict.get("confidence", 1.0),
                )
                await self._knowledge_graph.upsert_entity(entity)
                entities_added += 1

            for rel_dict in relations:
                relation = Relation(
                    source_id=rel_dict["source_id"],
                    target_id=rel_dict["target_id"],
                    relation_type=rel_dict["relation_type"],
                    properties=rel_dict.get("properties", {}),
                    confidence=rel_dict.get("confidence", 1.0),
                )
                await self._knowledge_graph.add_relation(relation)
                relations_added += 1

            pct = int((i + 1) / total * 100)
            await on_progress(
                pct,
                f"Processed {i + 1}/{total} documents ({entities_added} entities, {relations_added} relations)",
            )

        return {
            "entities_added": entities_added,
            "relations_added": relations_added,
            "documents_processed": total,
        }
