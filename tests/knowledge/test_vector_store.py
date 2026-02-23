# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SQLite and PgVector VectorStore implementations."""

from __future__ import annotations

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.stores.sqlite_store import SqliteVectorStore
from flydesk.knowledge.vector_store import VectorSearchResult, VectorStore
from flydesk.models.base import Base
from flydesk.models.knowledge_base import KnowledgeDocumentRow


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def sqlite_store(session_factory) -> SqliteVectorStore:
    return SqliteVectorStore(session_factory)


async def _seed_document(session_factory, doc_id: str, title: str, tags: list[str]) -> None:
    """Insert a KnowledgeDocumentRow so tag filtering can resolve documents."""
    async with session_factory() as session:
        row = KnowledgeDocumentRow(
            id=doc_id,
            title=title,
            content="test content",
            document_type="other",
            tags=json.dumps(tags),
            metadata_="{}",
        )
        session.add(row)
        await session.commit()


class TestSqliteVectorStoreProtocol:
    def test_implements_protocol(self, sqlite_store: SqliteVectorStore):
        """SqliteVectorStore satisfies the VectorStore protocol."""
        assert isinstance(sqlite_store, VectorStore)


class TestSqliteVectorStoreBasicFlow:
    async def test_store_and_search(self, sqlite_store: SqliteVectorStore, session_factory):
        """Chunks can be stored and then found by vector similarity."""
        await _seed_document(session_factory, "doc-1", "Test Doc", [])

        chunks = [
            ("c1", "alpha content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta content", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 1}),
        ]
        await sqlite_store.store("doc-1", chunks)

        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) >= 1
        assert results[0].chunk_id == "c1"
        assert results[0].document_id == "doc-1"
        assert results[0].score > 0

    async def test_search_returns_correct_order(self, sqlite_store: SqliteVectorStore, session_factory):
        """Results are ordered by descending similarity."""
        await _seed_document(session_factory, "doc-1", "Test Doc", [])

        chunks = [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta", [0.7, 0.7, 0.0, 0.0], {"chunk_index": 1}),
            ("c3", "gamma", [0.0, 0.0, 1.0, 0.0], {"chunk_index": 2}),
        ]
        await sqlite_store.store("doc-1", chunks)

        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=3)
        assert len(results) >= 2
        # c1 should be first (exact match), c2 second (partial match)
        assert results[0].chunk_id == "c1"
        assert results[0].score >= results[1].score

    async def test_search_respects_top_k(self, sqlite_store: SqliteVectorStore, session_factory):
        """Only top_k results are returned."""
        await _seed_document(session_factory, "doc-1", "Test Doc", [])

        chunks = [
            ("c1", "a", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "b", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 1}),
            ("c3", "c", [0.8, 0.2, 0.0, 0.0], {"chunk_index": 2}),
        ]
        await sqlite_store.store("doc-1", chunks)

        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1

    async def test_search_empty_store(self, sqlite_store: SqliteVectorStore):
        """Search on an empty store returns an empty list."""
        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []


class TestSqliteVectorStoreDelete:
    async def test_delete_removes_chunks(self, sqlite_store: SqliteVectorStore, session_factory):
        """Delete removes all chunks for a document."""
        await _seed_document(session_factory, "doc-1", "Test Doc", [])

        chunks = [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 1}),
        ]
        await sqlite_store.store("doc-1", chunks)

        await sqlite_store.delete("doc-1")

        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []

    async def test_delete_only_affects_target_document(
        self, sqlite_store: SqliteVectorStore, session_factory
    ):
        """Deleting one document does not affect chunks from other documents."""
        await _seed_document(session_factory, "doc-1", "Doc 1", [])
        await _seed_document(session_factory, "doc-2", "Doc 2", [])

        await sqlite_store.store("doc-1", [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
        ])
        await sqlite_store.store("doc-2", [
            ("c2", "beta", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 0}),
        ])

        await sqlite_store.delete("doc-1")

        results = await sqlite_store.search([0.0, 1.0, 0.0, 0.0], top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "c2"


class TestSqliteVectorStoreTagFilter:
    async def test_tag_filter_includes_matching(
        self, sqlite_store: SqliteVectorStore, session_factory
    ):
        """Tag filter only returns chunks from matching documents."""
        await _seed_document(session_factory, "doc-1", "HR Doc", ["hr"])
        await _seed_document(session_factory, "doc-2", "Finance Doc", ["finance"])

        await sqlite_store.store("doc-1", [
            ("c1", "hr content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0, "tags": ["hr"]}),
        ])
        await sqlite_store.store("doc-2", [
            ("c2", "finance content", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 0, "tags": ["finance"]}),
        ])

        results = await sqlite_store.search(
            [1.0, 0.0, 0.0, 0.0], top_k=5, tag_filter=["hr"]
        )
        assert len(results) == 1
        assert results[0].document_id == "doc-1"

    async def test_tag_filter_no_match_returns_empty(
        self, sqlite_store: SqliteVectorStore, session_factory
    ):
        """No matching tags returns an empty result set."""
        await _seed_document(session_factory, "doc-1", "HR Doc", ["hr"])

        await sqlite_store.store("doc-1", [
            ("c1", "hr content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
        ])

        results = await sqlite_store.search(
            [1.0, 0.0, 0.0, 0.0], top_k=5, tag_filter=["finance"]
        )
        assert results == []

    async def test_no_tag_filter_returns_all(
        self, sqlite_store: SqliteVectorStore, session_factory
    ):
        """Without tag filter, all documents are returned."""
        await _seed_document(session_factory, "doc-1", "HR Doc", ["hr"])
        await _seed_document(session_factory, "doc-2", "Finance Doc", ["finance"])

        await sqlite_store.store("doc-1", [
            ("c1", "hr content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
        ])
        await sqlite_store.store("doc-2", [
            ("c2", "finance content", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 0}),
        ])

        results = await sqlite_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert len(results) == 2


class TestSqliteVectorStoreClose:
    async def test_close_is_noop(self, sqlite_store: SqliteVectorStore):
        """Close does not raise."""
        await sqlite_store.close()


class TestVectorSearchResult:
    def test_dataclass_fields(self):
        result = VectorSearchResult(
            chunk_id="c1",
            document_id="d1",
            content="test",
            chunk_index=0,
            score=0.95,
            metadata={"key": "value"},
        )
        assert result.chunk_id == "c1"
        assert result.document_id == "d1"
        assert result.score == 0.95
        assert result.metadata == {"key": "value"}

    def test_default_metadata(self):
        result = VectorSearchResult(
            chunk_id="c1",
            document_id="d1",
            content="test",
            chunk_index=0,
            score=0.5,
        )
        assert result.metadata == {}
