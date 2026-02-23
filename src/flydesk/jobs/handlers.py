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
