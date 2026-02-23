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

from flydesk.knowledge.graph import Entity, KnowledgeGraph
from flydesk.knowledge.models import RetrievalResult
from flydesk.knowledge.retriever import KnowledgeRetriever


@dataclass
class EnrichedContext:
    """Assembled context for a single agent turn."""

    relevant_entities: list[Entity] = field(default_factory=list)
    knowledge_snippets: list[RetrievalResult] = field(default_factory=list)
    conversation_history: list[dict[str, str]] = field(default_factory=list)


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
        entity_limit: int = 5,
        retrieval_top_k: int = 3,
    ) -> None:
        self._knowledge_graph = knowledge_graph
        self._retriever = retriever
        self._entity_limit = entity_limit
        self._retrieval_top_k = retrieval_top_k

    async def enrich(
        self,
        message: str,
        *,
        conversation_history: list[dict[str, str]] | None = None,
        knowledge_tag_filter: list[str] | None = None,
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

        Returns:
            A fully populated ``EnrichedContext``.
        """
        entities, snippets = await asyncio.gather(
            self._knowledge_graph.find_relevant_entities(
                message, limit=self._entity_limit
            ),
            self._retriever.retrieve(
                message,
                top_k=self._retrieval_top_k,
                tag_filter=knowledge_tag_filter,
            ),
        )

        return EnrichedContext(
            relevant_entities=entities,
            knowledge_snippets=snippets,
            conversation_history=conversation_history or [],
        )
