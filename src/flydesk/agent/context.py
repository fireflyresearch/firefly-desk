# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Context enricher -- parallel knowledge retrieval before each agent turn."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from flydesk.knowledge.graph import Entity, KnowledgeGraph
from flydesk.knowledge.models import RetrievalResult
from flydesk.knowledge.retriever import KnowledgeRetriever
from flydesk.processes.repository import ProcessRepository


@dataclass
class EnrichedContext:
    """Assembled context for a single agent turn."""

    relevant_entities: list[Entity] = field(default_factory=list)
    knowledge_snippets: list[RetrievalResult] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    relevant_processes: list[Any] = field(default_factory=list)
    user_memories: list[Any] = field(default_factory=list)


class ContextEnricher:
    """Enriches the agent's context before each turn.

    Runs knowledge graph entity search and knowledge base (RAG) retrieval
    in parallel via ``asyncio.gather`` for minimal latency.
    """

    def __init__(
        self,
        *,
        knowledge_graph: KnowledgeGraph,
        retriever: KnowledgeRetriever,
        process_repo: ProcessRepository | None = None,
        memory_repo: Any | None = None,
        entity_limit: int = 5,
        retrieval_top_k: int = 3,
    ) -> None:
        self._knowledge_graph = knowledge_graph
        self._retriever = retriever
        self._process_repo = process_repo
        self._memory_repo = memory_repo
        self._entity_limit = entity_limit
        self._retrieval_top_k = retrieval_top_k

    async def enrich(
        self,
        message: str,
        *,
        conversation_history: list[dict[str, str]] | None = None,
        knowledge_tag_filter: list[str] | None = None,
        user_id: str | None = None,
    ) -> EnrichedContext:
        """Build an enriched context for the given user message.

        Runs knowledge graph search and RAG retrieval concurrently.

        Args:
            message: The current user message to enrich context for.
            conversation_history: Optional prior conversation turns.
                When a conversation memory store is available this will
                be fetched automatically; for now callers may pass it in.
            knowledge_tag_filter: When set, only retrieval results from
                documents whose tags overlap with this list are included.
            user_id: When set, user memories matching the message are
                included in the enriched context.

        Returns:
            A fully populated ``EnrichedContext``.
        """
        try:
            async with asyncio.timeout(10):
                entities, snippets, processes, memories = await asyncio.gather(
                    self._knowledge_graph.find_relevant_entities(
                        message, limit=self._entity_limit
                    ),
                    self._retriever.retrieve(
                        message,
                        top_k=self._retrieval_top_k,
                        tag_filter=knowledge_tag_filter,
                    ),
                    self._search_processes(message),
                    self._search_memories(message, user_id),
                )
        except (TimeoutError, Exception):
            # Context enrichment is non-fatal; return empty context rather
            # than blocking the agent response indefinitely.
            entities = []
            snippets = []
            processes = []
            memories = []

        return EnrichedContext(
            relevant_entities=entities,
            knowledge_snippets=snippets,
            conversation_history=conversation_history or [],
            relevant_processes=processes,
            user_memories=memories,
        )

    async def _search_processes(self, message: str) -> list[Any]:
        """Search for business processes matching the user message.

        Uses a simple text-match approach similar to the built-in
        ``search_processes`` tool.  Returns an empty list when no
        :class:`ProcessRepository` is configured.
        """
        if self._process_repo is None:
            return []

        try:
            processes = await self._process_repo.list()
        except Exception:
            return []

        query_lower = message.lower()
        matches: list[tuple[float, Any]] = []
        for proc in processes:
            score = 0.0
            if query_lower in proc.name.lower():
                score += 2
            if query_lower in proc.description.lower():
                score += 1
            for step in proc.steps:
                if query_lower in step.description.lower():
                    score += 0.5
            if score > 0:
                matches.append((score, proc))

        matches.sort(key=lambda x: x[0], reverse=True)
        return [proc for _score, proc in matches[:3]]

    async def _search_memories(self, message: str, user_id: str | None) -> list[Any]:
        """Search user memories matching the message."""
        if self._memory_repo is None or user_id is None:
            return []
        try:
            return await self._memory_repo.search(user_id, message)
        except Exception:
            return []
