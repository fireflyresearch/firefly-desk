# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for document reindexing."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import KnowledgeDocument
from flydesk.models.base import Base
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


class FakeEmbeddingProvider:
    """Return deterministic embeddings for testing."""

    def __init__(self, dim: int = 4) -> None:
        self._dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(i) for i in range(self._dim)] for _ in texts]


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


def _make_doc(
    doc_id: str = "doc-1", content: str = "Test content for reindexing.",
) -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        title="Test Document",
        content=content,
    )


@pytest.mark.asyncio
async def test_reindex_document_deletes_old_chunks(indexer, session_factory):
    """reindex_document should delete old chunks before re-indexing."""
    doc = _make_doc()
    original_chunks = await indexer.index_document(doc)
    assert len(original_chunks) > 0

    # Reindex the same document
    new_chunks = await indexer.reindex_document("doc-1")

    # Old chunk IDs should no longer exist; new ones should be present
    async with session_factory() as session:
        rows = (await session.execute(
            select(DocumentChunkRow).where(DocumentChunkRow.document_id == "doc-1")
        )).scalars().all()
    assert len(rows) == len(new_chunks)
    old_ids = {c.chunk_id for c in original_chunks}
    new_ids = {r.id for r in rows}
    assert old_ids.isdisjoint(new_ids), "Old chunk IDs should have been replaced"


@pytest.mark.asyncio
async def test_reindex_document_returns_empty_for_missing(indexer):
    """reindex_document should return empty list for non-existent doc."""
    result = await indexer.reindex_document("nonexistent")
    assert result == []


@pytest.mark.asyncio
async def test_reindex_document_preserves_document_row(indexer, session_factory):
    """reindex_document should keep the document metadata row intact."""
    doc = _make_doc()
    await indexer.index_document(doc)

    await indexer.reindex_document("doc-1")

    async with session_factory() as session:
        row = (await session.execute(
            select(KnowledgeDocumentRow).where(KnowledgeDocumentRow.id == "doc-1")
        )).scalar_one_or_none()
    assert row is not None
    assert row.title == "Test Document"


@pytest.mark.asyncio
async def test_reindex_all_returns_count(indexer, session_factory):
    """reindex_all should return the count of reindexed documents."""
    count = await indexer.reindex_all()
    assert count == 0


@pytest.mark.asyncio
async def test_reindex_all_reindexes_all_documents(indexer, session_factory):
    """reindex_all should reindex every document and return the count."""
    await indexer.index_document(_make_doc("d1", "First document content here."))
    await indexer.index_document(_make_doc("d2", "Second document content here."))

    count = await indexer.reindex_all()
    assert count == 2

    # Verify chunks still exist for both documents
    async with session_factory() as session:
        rows = (await session.execute(select(DocumentChunkRow))).scalars().all()
    doc_ids = {r.document_id for r in rows}
    assert doc_ids == {"d1", "d2"}


@pytest.mark.asyncio
async def test_reindex_all_with_progress_callback(indexer, session_factory):
    """reindex_all should call on_progress callback with (done, total)."""
    await indexer.index_document(_make_doc("d1", "Document one."))

    progress_calls: list[tuple[int, int]] = []
    count = await indexer.reindex_all(
        on_progress=lambda done, total: progress_calls.append((done, total))
    )
    assert count == 1
    assert (1, 1) in progress_calls
