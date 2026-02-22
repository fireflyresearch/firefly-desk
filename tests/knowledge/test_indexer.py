# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for KnowledgeIndexer."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.knowledge.indexer import KnowledgeIndexer
from flydek.knowledge.models import KnowledgeDocument
from flydek.models.base import Base
from flydek.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


class FakeEmbeddingProvider:
    """Return deterministic embeddings based on content length for testing."""

    def __init__(self, dim: int = 4) -> None:
        self._dim = dim
        self.call_count = 0

    async def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        result: list[list[float]] = []
        for text in texts:
            # Produce a simple deterministic vector from text length
            base = len(text) % 10
            result.append([float(base + i) for i in range(self._dim)])
        return result


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def embedding_provider() -> FakeEmbeddingProvider:
    return FakeEmbeddingProvider()


@pytest.fixture
def indexer(session_factory, embedding_provider) -> KnowledgeIndexer:
    return KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=50,
        chunk_overlap=10,
    )


@pytest.fixture
def sample_document() -> KnowledgeDocument:
    return KnowledgeDocument(
        id="doc-001",
        title="Incident Response Procedure",
        content="When an incident occurs, the on-call engineer must acknowledge the alert within 5 minutes. "
        "Escalation to the team lead is required if the incident is not resolved within 30 minutes.",
        source="runbook",
        tags=["incident", "ops"],
        metadata={"version": "1.2"},
    )


class TestKnowledgeIndexer:
    async def test_index_document_stores_document(self, indexer, session_factory, sample_document):
        """Document is persisted to the database."""
        await indexer.index_document(sample_document)

        async with session_factory() as session:
            row = await session.get(KnowledgeDocumentRow, "doc-001")
            assert row is not None
            assert row.title == "Incident Response Procedure"
            assert row.source == "runbook"
            assert "incident" in row.content

    async def test_index_document_creates_chunks(self, indexer, session_factory, sample_document):
        """Chunks are created with correct indices."""
        chunks = await indexer.index_document(sample_document)

        assert len(chunks) > 1  # Content is longer than chunk_size=50

        # Verify chunk indices are sequential
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.document_id == "doc-001"

        # Verify chunks are persisted
        async with session_factory() as session:
            result = await session.execute(
                select(DocumentChunkRow).where(DocumentChunkRow.document_id == "doc-001")
            )
            db_chunks = result.scalars().all()
            assert len(db_chunks) == len(chunks)

    async def test_chunk_text_overlap(self, indexer):
        """Overlapping chunks share content at boundaries."""
        # chunk_size=50, chunk_overlap=10
        text = "A" * 100  # Exactly 100 characters

        chunks = indexer._chunk_text("test-doc", text)

        # With size=50 and overlap=10, step=40
        # Chunk 0: [0:50], Chunk 1: [40:90], Chunk 2: [80:100]
        assert len(chunks) == 3
        assert len(chunks[0].content) == 50
        assert len(chunks[1].content) == 50
        assert len(chunks[2].content) == 20  # Remaining characters

    async def test_chunks_have_embeddings(
        self, indexer, session_factory, embedding_provider, sample_document
    ):
        """Each chunk gets an embedding from the provider."""
        chunks = await indexer.index_document(sample_document)

        # Verify the embedding provider was called
        assert embedding_provider.call_count == 1

        # Verify each chunk row has a stored embedding
        async with session_factory() as session:
            for chunk in chunks:
                row = await session.get(DocumentChunkRow, chunk.chunk_id)
                assert row is not None
                assert row.embedding is not None
                embedding = json.loads(row.embedding)
                assert isinstance(embedding, list)
                assert len(embedding) == 4  # FakeEmbeddingProvider dim=4

    async def test_delete_document(self, indexer, session_factory, sample_document):
        """Document and all its chunks are removed."""
        await indexer.index_document(sample_document)

        # Verify document exists before deletion
        async with session_factory() as session:
            assert await session.get(KnowledgeDocumentRow, "doc-001") is not None

        await indexer.delete_document("doc-001")

        # Document should be gone
        async with session_factory() as session:
            assert await session.get(KnowledgeDocumentRow, "doc-001") is None

        # Chunks should be gone
        async with session_factory() as session:
            result = await session.execute(
                select(DocumentChunkRow).where(DocumentChunkRow.document_id == "doc-001")
            )
            assert result.scalars().all() == []
