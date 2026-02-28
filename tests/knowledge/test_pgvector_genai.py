# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for PgVectorGenAIStore -- pgvector adapter for genai BaseVectorStore."""

from __future__ import annotations

import json
from collections import namedtuple
from unittest.mock import AsyncMock, MagicMock

import pytest
from fireflyframework_genai.vectorstores import BaseVectorStore, SearchResult, VectorDocument

from flydesk.knowledge.stores.pgvector_genai import PgVectorGenAIStore

# Named tuple matching the raw SQL result columns used in _search.
_SearchRow = namedtuple("_SearchRow", ["id", "document_id", "content", "chunk_index", "metadata", "score"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_session():
    """Create a mock async session with context-manager support."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    # session.add() is synchronous in SQLAlchemy; keep it as a plain MagicMock
    # to avoid "coroutine never awaited" warnings from AsyncMock.
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Create a mock session factory that yields mock_session."""
    factory = MagicMock()
    factory.return_value = mock_session
    return factory


@pytest.fixture
def store(mock_session_factory):
    """Create a PgVectorGenAIStore with a mocked session factory."""
    return PgVectorGenAIStore(session_factory=mock_session_factory)


# ---------------------------------------------------------------------------
# Structural / type checks
# ---------------------------------------------------------------------------

def test_is_instance_of_base_vector_store(store):
    assert isinstance(store, BaseVectorStore)


def test_construction_with_session_factory(mock_session_factory):
    store = PgVectorGenAIStore(session_factory=mock_session_factory)
    assert store._session_factory is mock_session_factory


def test_construction_with_embedder(mock_session_factory):
    embedder = AsyncMock()
    store = PgVectorGenAIStore(session_factory=mock_session_factory, embedder=embedder)
    assert store._embedder is embedder


def test_abstract_methods_exist():
    """Verify the class implements all required abstract methods."""
    assert hasattr(PgVectorGenAIStore, "_upsert")
    assert hasattr(PgVectorGenAIStore, "_search")
    assert hasattr(PgVectorGenAIStore, "_delete")


# ---------------------------------------------------------------------------
# _upsert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_insert_new_document(store, mock_session):
    """When a document does not exist, _upsert adds a new row."""
    mock_session.get.return_value = None  # No existing row

    doc = VectorDocument(
        id="chunk-1",
        text="Hello world",
        embedding=[0.1, 0.2, 0.3],
        metadata={"document_id": "doc-1", "chunk_index": 2},
    )

    await store._upsert([doc], namespace="default")

    mock_session.get.assert_awaited_once()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()

    # Verify the row attributes
    added_row = mock_session.add.call_args[0][0]
    assert added_row.id == "chunk-1"
    assert added_row.document_id == "doc-1"
    assert added_row.content == "Hello world"
    assert added_row.chunk_index == 2
    assert added_row.embedding == [0.1, 0.2, 0.3]
    metadata = json.loads(added_row.metadata_)
    assert metadata["document_id"] == "doc-1"


@pytest.mark.asyncio
async def test_upsert_update_existing_document(store, mock_session):
    """When a document already exists, _upsert updates it in place."""
    existing = MagicMock()
    existing.content = "Old content"
    existing.embedding = [0.0, 0.0, 0.0]
    existing.metadata_ = "{}"
    mock_session.get.return_value = existing

    doc = VectorDocument(
        id="chunk-1",
        text="Updated content",
        embedding=[0.4, 0.5, 0.6],
        metadata={"document_id": "doc-1"},
    )

    await store._upsert([doc], namespace="default")

    assert existing.content == "Updated content"
    assert existing.embedding == [0.4, 0.5, 0.6]
    mock_session.add.assert_not_called()  # Should update, not add
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_upsert_defaults_document_id_and_chunk_index(store, mock_session):
    """When metadata lacks document_id and chunk_index, defaults apply."""
    mock_session.get.return_value = None

    doc = VectorDocument(
        id="chunk-2",
        text="No metadata",
        embedding=[0.1, 0.2],
        metadata={},
    )

    await store._upsert([doc], namespace="default")

    added_row = mock_session.add.call_args[0][0]
    assert added_row.document_id == ""
    assert added_row.chunk_index == 0


# ---------------------------------------------------------------------------
# _search
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_returns_search_results(store, mock_session):
    """_search executes raw SQL and returns SearchResult objects."""
    fake_row = _SearchRow(
        id="chunk-1",
        document_id="doc-1",
        content="Hello",
        chunk_index=0,
        metadata=json.dumps({"source": "test"}),
        score=0.95,
    )

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [fake_row]
    mock_session.execute.return_value = mock_result

    results = await store._search(
        query_embedding=[0.1, 0.2, 0.3],
        top_k=5,
        namespace="default",
        filters=None,
    )

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].document.id == "chunk-1"
    assert results[0].document.text == "Hello"
    assert results[0].score == 0.95
    assert results[0].document.metadata["document_id"] == "doc-1"
    assert results[0].document.metadata["source"] == "test"


@pytest.mark.asyncio
async def test_search_empty_results(store, mock_session):
    """_search returns empty list when no rows match."""
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []
    mock_session.execute.return_value = mock_result

    results = await store._search(
        query_embedding=[0.1, 0.2],
        top_k=5,
        namespace="default",
        filters=None,
    )

    assert results == []


@pytest.mark.asyncio
async def test_search_handles_null_metadata(store, mock_session):
    """_search handles rows with null/empty metadata gracefully."""
    fake_row = _SearchRow(
        id="chunk-2",
        document_id="doc-2",
        content="World",
        chunk_index=1,
        metadata=None,
        score=0.80,
    )

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [fake_row]
    mock_session.execute.return_value = mock_result

    results = await store._search(
        query_embedding=[0.1, 0.2],
        top_k=5,
        namespace="default",
        filters=None,
    )

    assert len(results) == 1
    assert results[0].document.metadata["document_id"] == "doc-2"
    assert results[0].document.metadata["chunk_index"] == 1


# ---------------------------------------------------------------------------
# _delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_executes_statement(store, mock_session):
    """_delete issues a DELETE WHERE id IN (...) and commits."""
    await store._delete(ids=["chunk-1", "chunk-2"], namespace="default")

    mock_session.execute.assert_awaited_once()
    mock_session.commit.assert_awaited_once()
