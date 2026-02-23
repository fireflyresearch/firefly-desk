# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the ContextEnricher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.context import ContextEnricher, EnrichedContext
from flydesk.knowledge.graph import Entity, KnowledgeGraph
from flydesk.knowledge.models import DocumentChunk, RetrievalResult
from flydesk.knowledge.retriever import KnowledgeRetriever


@pytest.fixture
def sample_entities() -> list[Entity]:
    return [
        Entity(
            id="e-1",
            entity_type="customer",
            name="Acme Corp",
            properties={"industry": "tech"},
            source_system="crm",
            confidence=0.95,
            mention_count=12,
        ),
        Entity(
            id="e-2",
            entity_type="product",
            name="Widget Pro",
            properties={},
            source_system="catalog",
            confidence=0.88,
            mention_count=3,
        ),
    ]


@pytest.fixture
def sample_retrieval_results() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            chunk=DocumentChunk(
                chunk_id="c-1",
                document_id="doc-1",
                content="Refund policy requires manager approval for amounts over $500.",
                chunk_index=0,
                metadata={"section": "refunds"},
            ),
            score=0.92,
            document_title="Refund Policy",
        ),
        RetrievalResult(
            chunk=DocumentChunk(
                chunk_id="c-2",
                document_id="doc-2",
                content="Escalation procedure: contact tier-2 support within 24 hours.",
                chunk_index=1,
                metadata={"section": "escalation"},
            ),
            score=0.85,
            document_title="Support Procedures",
        ),
    ]


@pytest.fixture
def knowledge_graph(sample_entities: list[Entity]) -> KnowledgeGraph:
    mock = MagicMock(spec=KnowledgeGraph)
    mock.find_relevant_entities = AsyncMock(return_value=sample_entities)
    return mock


@pytest.fixture
def retriever(sample_retrieval_results: list[RetrievalResult]) -> KnowledgeRetriever:
    mock = MagicMock(spec=KnowledgeRetriever)
    mock.retrieve = AsyncMock(return_value=sample_retrieval_results)
    return mock


@pytest.fixture
def enricher(
    knowledge_graph: KnowledgeGraph,
    retriever: KnowledgeRetriever,
) -> ContextEnricher:
    return ContextEnricher(knowledge_graph=knowledge_graph, retriever=retriever)


class TestEnrichedContext:
    """Tests for the EnrichedContext dataclass."""

    def test_defaults_to_empty_lists(self):
        ctx = EnrichedContext()
        assert ctx.relevant_entities == []
        assert ctx.knowledge_snippets == []
        assert ctx.conversation_history == []

    def test_populated_fields(self, sample_entities, sample_retrieval_results):
        history = [{"role": "user", "content": "hello"}]
        ctx = EnrichedContext(
            relevant_entities=sample_entities,
            knowledge_snippets=sample_retrieval_results,
            conversation_history=history,
        )
        assert len(ctx.relevant_entities) == 2
        assert len(ctx.knowledge_snippets) == 2
        assert ctx.conversation_history == history


class TestContextEnricher:
    """Tests for the ContextEnricher."""

    async def test_enrich_returns_enriched_context(self, enricher):
        result = await enricher.enrich("refund for Acme Corp")
        assert isinstance(result, EnrichedContext)

    async def test_enrich_populates_entities(
        self, enricher, sample_entities
    ):
        result = await enricher.enrich("refund for Acme Corp")
        assert result.relevant_entities == sample_entities

    async def test_enrich_populates_knowledge_snippets(
        self, enricher, sample_retrieval_results
    ):
        result = await enricher.enrich("refund for Acme Corp")
        assert result.knowledge_snippets == sample_retrieval_results

    async def test_enrich_conversation_history_empty_by_default(self, enricher):
        result = await enricher.enrich("anything")
        assert result.conversation_history == []

    async def test_enrich_passes_message_to_knowledge_graph(
        self, enricher, knowledge_graph
    ):
        await enricher.enrich("lookup Widget Pro")
        knowledge_graph.find_relevant_entities.assert_awaited_once_with(
            "lookup Widget Pro", limit=5
        )

    async def test_enrich_passes_message_to_retriever(
        self, enricher, retriever
    ):
        await enricher.enrich("refund policy details")
        retriever.retrieve.assert_awaited_once_with(
            "refund policy details", top_k=3, tag_filter=None,
        )

    async def test_enrich_with_custom_entity_limit(
        self, knowledge_graph, retriever
    ):
        enricher = ContextEnricher(
            knowledge_graph=knowledge_graph,
            retriever=retriever,
            entity_limit=10,
        )
        await enricher.enrich("big query")
        knowledge_graph.find_relevant_entities.assert_awaited_once_with(
            "big query", limit=10
        )

    async def test_enrich_with_custom_top_k(
        self, knowledge_graph, retriever
    ):
        enricher = ContextEnricher(
            knowledge_graph=knowledge_graph,
            retriever=retriever,
            retrieval_top_k=7,
        )
        await enricher.enrich("deep search")
        retriever.retrieve.assert_awaited_once_with("deep search", top_k=7, tag_filter=None)

    async def test_enrich_with_conversation_history(
        self, knowledge_graph, retriever
    ):
        history = [
            {"role": "user", "content": "What is the refund policy?"},
            {"role": "assistant", "content": "The refund policy states..."},
        ]
        enricher = ContextEnricher(
            knowledge_graph=knowledge_graph, retriever=retriever
        )
        result = await enricher.enrich("follow up question", conversation_history=history)
        assert result.conversation_history == history

    async def test_enrich_runs_graph_and_retriever_concurrently(
        self, knowledge_graph, retriever
    ):
        """Both calls are awaited (via asyncio.gather), verifying concurrency intent."""
        enricher = ContextEnricher(
            knowledge_graph=knowledge_graph, retriever=retriever
        )
        result = await enricher.enrich("concurrent test")

        # Both should have been called exactly once
        knowledge_graph.find_relevant_entities.assert_awaited_once()
        retriever.retrieve.assert_awaited_once()

        # And the result should be properly assembled
        assert len(result.relevant_entities) > 0
        assert len(result.knowledge_snippets) > 0

    async def test_enrich_handles_empty_graph_results(self, retriever):
        graph = MagicMock(spec=KnowledgeGraph)
        graph.find_relevant_entities = AsyncMock(return_value=[])
        enricher = ContextEnricher(knowledge_graph=graph, retriever=retriever)

        result = await enricher.enrich("unknown topic")
        assert result.relevant_entities == []
        assert len(result.knowledge_snippets) > 0

    async def test_enrich_handles_empty_retriever_results(self, knowledge_graph):
        ret = MagicMock(spec=KnowledgeRetriever)
        ret.retrieve = AsyncMock(return_value=[])
        enricher = ContextEnricher(knowledge_graph=knowledge_graph, retriever=ret)

        result = await enricher.enrich("obscure query")
        assert len(result.relevant_entities) > 0
        assert result.knowledge_snippets == []

    async def test_enrich_handles_both_empty(self):
        graph = MagicMock(spec=KnowledgeGraph)
        graph.find_relevant_entities = AsyncMock(return_value=[])
        ret = MagicMock(spec=KnowledgeRetriever)
        ret.retrieve = AsyncMock(return_value=[])
        enricher = ContextEnricher(knowledge_graph=graph, retriever=ret)

        result = await enricher.enrich("nothing matches")
        assert result.relevant_entities == []
        assert result.knowledge_snippets == []
        assert result.conversation_history == []
