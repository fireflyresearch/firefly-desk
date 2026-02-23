# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for KnowledgeRetriever."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import KnowledgeDocument
from flydesk.knowledge.retriever import KnowledgeRetriever
from flydesk.models.base import Base


class SteerableEmbeddingProvider:
    """Embedding provider that returns pre-configured vectors.

    Maps text content to specific vectors so tests can control similarity scores.
    Falls back to a default vector for unknown texts.
    """

    def __init__(self) -> None:
        self._mapping: dict[str, list[float]] = {}
        self._default: list[float] = [0.0, 0.0, 0.0, 0.0]

    def register(self, text: str, vector: list[float]) -> None:
        self._mapping[text] = vector

    def set_default(self, vector: list[float]) -> None:
        self._default = vector

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._mapping.get(t, self._default) for t in texts]


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def embedding_provider() -> SteerableEmbeddingProvider:
    return SteerableEmbeddingProvider()


@pytest.fixture
def indexer(session_factory, embedding_provider) -> KnowledgeIndexer:
    return KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=500,  # Large enough that each small doc is one chunk
        chunk_overlap=0,
    )


@pytest.fixture
def retriever(session_factory, embedding_provider) -> KnowledgeRetriever:
    return KnowledgeRetriever(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
    )


async def _index_docs(
    indexer: KnowledgeIndexer,
    embedding_provider: SteerableEmbeddingProvider,
    docs: list[tuple[str, str, str, list[float]]],
) -> None:
    """Helper: index documents with pre-set embeddings.

    Each tuple is (id, title, content, embedding_vector).
    """
    for doc_id, title, content, vector in docs:
        embedding_provider.register(content, vector)
        await indexer.index_document(
            KnowledgeDocument(id=doc_id, title=title, content=content)
        )


async def _index_tagged_docs(
    indexer: KnowledgeIndexer,
    embedding_provider: SteerableEmbeddingProvider,
    docs: list[tuple[str, str, str, list[str], list[float]]],
) -> None:
    """Helper: index documents with tags and pre-set embeddings.

    Each tuple is (id, title, content, tags, embedding_vector).
    """
    for doc_id, title, content, tags, vector in docs:
        embedding_provider.register(content, vector)
        await indexer.index_document(
            KnowledgeDocument(id=doc_id, title=title, content=content, tags=tags)
        )


class TestKnowledgeRetriever:
    async def test_retrieve_returns_relevant_chunks(
        self, indexer, retriever, embedding_provider
    ):
        """Top-k results are returned, filtered to non-zero similarity."""
        await _index_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Doc A", "alpha content", [1.0, 0.0, 0.0, 0.0]),
                ("d2", "Doc B", "beta content", [0.5, 0.5, 0.0, 0.0]),
                ("d3", "Doc C", "gamma content", [0.1, 0.1, 0.8, 0.0]),
            ],
        )

        # Query vector is closest to d1 (dot product = 1.0 with [1,0,0,0])
        # d2 and d3 also have partial overlap so they score > 0
        embedding_provider.register("find alpha", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("find alpha", top_k=2)

        assert len(results) == 2
        assert results[0].chunk.document_id == "d1"

    async def test_retrieve_scores_correct(
        self, indexer, retriever, embedding_provider
    ):
        """Higher similarity scores rank first."""
        await _index_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Low Match", "low content", [1.0, 0.0, 0.0, 0.0]),
                ("d2", "High Match", "high content", [0.7, 0.7, 0.0, 0.0]),
                ("d3", "Mid Match", "mid content", [0.5, 0.5, 0.5, 0.0]),
            ],
        )

        # Query vector shares components with d2 most
        embedding_provider.register("mixed query", [0.7, 0.7, 0.0, 0.0])
        results = await retriever.retrieve("mixed query", top_k=3)

        assert len(results) == 3
        # d2 should be first (perfect match with query)
        assert results[0].chunk.document_id == "d2"
        # Scores should be in descending order
        assert results[0].score >= results[1].score >= results[2].score

    async def test_retrieve_includes_document_title(
        self, indexer, retriever, embedding_provider
    ):
        """Document title is resolved and included in results."""
        await _index_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Incident Playbook", "incident steps", [1.0, 0.0, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("incident query", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("incident query", top_k=1)

        assert len(results) == 1
        assert results[0].document_title == "Incident Playbook"

    async def test_retrieve_respects_top_k(
        self, indexer, retriever, embedding_provider
    ):
        """Only top_k results are returned even when more chunks exist."""
        await _index_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Doc 1", "content one", [1.0, 0.0, 0.0, 0.0]),
                ("d2", "Doc 2", "content two", [0.9, 0.1, 0.0, 0.0]),
                ("d3", "Doc 3", "content three", [0.8, 0.2, 0.0, 0.0]),
                ("d4", "Doc 4", "content four", [0.7, 0.3, 0.0, 0.0]),
                ("d5", "Doc 5", "content five", [0.6, 0.4, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("top query", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("top query", top_k=2)

        assert len(results) == 2


class TestKnowledgeRetrieverTagFilter:
    """Tests for tag_filter parameter on KnowledgeRetriever.retrieve()."""

    async def test_tag_filter_includes_matching_docs(
        self, indexer, retriever, embedding_provider
    ):
        """Only documents with overlapping tags are returned."""
        await _index_tagged_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "HR Policy", "hr policy content", ["hr"], [1.0, 0.0, 0.0, 0.0]),
                ("d2", "Finance Report", "finance report content", ["finance"], [0.9, 0.1, 0.0, 0.0]),
                ("d3", "HR Onboarding", "hr onboarding guide", ["hr", "onboarding"], [0.8, 0.2, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("find hr docs", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("find hr docs", top_k=5, tag_filter=["hr"])

        assert len(results) == 2
        doc_ids = {r.chunk.document_id for r in results}
        assert doc_ids == {"d1", "d3"}

    async def test_tag_filter_none_returns_all(
        self, indexer, retriever, embedding_provider
    ):
        """When tag_filter is None, all documents are returned."""
        await _index_tagged_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Doc A", "content a", ["hr"], [1.0, 0.0, 0.0, 0.0]),
                ("d2", "Doc B", "content b", ["finance"], [0.9, 0.1, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("get all", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("get all", top_k=5, tag_filter=None)

        assert len(results) == 2

    async def test_tag_filter_no_match_returns_empty(
        self, indexer, retriever, embedding_provider
    ):
        """When no documents match the tag filter, empty list is returned."""
        await _index_tagged_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "Doc A", "content a", ["hr"], [1.0, 0.0, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("find finance", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("find finance", top_k=5, tag_filter=["finance"])

        assert len(results) == 0

    async def test_tag_filter_respects_top_k(
        self, indexer, retriever, embedding_provider
    ):
        """tag_filter combined with top_k returns at most top_k results."""
        await _index_tagged_docs(
            indexer,
            embedding_provider,
            [
                ("d1", "HR 1", "hr content 1", ["hr"], [1.0, 0.0, 0.0, 0.0]),
                ("d2", "HR 2", "hr content 2", ["hr"], [0.9, 0.1, 0.0, 0.0]),
                ("d3", "HR 3", "hr content 3", ["hr"], [0.8, 0.2, 0.0, 0.0]),
            ],
        )

        embedding_provider.register("hr query", [1.0, 0.0, 0.0, 0.0])
        results = await retriever.retrieve("hr query", top_k=2, tag_filter=["hr"])

        assert len(results) == 2
