# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ChromaDB VectorStore implementation.

Skipped when ``chromadb`` is not installed.
"""

from __future__ import annotations

import pytest

chromadb = pytest.importorskip("chromadb")

from flydesk.knowledge.stores.chroma_store import ChromaDBStore
from flydesk.knowledge.vector_store import VectorStore


@pytest.fixture
def chroma_store() -> ChromaDBStore:
    """Create an ephemeral (in-memory) ChromaDB store for testing."""
    return ChromaDBStore()


class TestChromaDBStoreProtocol:
    def test_implements_protocol(self, chroma_store: ChromaDBStore):
        assert isinstance(chroma_store, VectorStore)


class TestChromaDBStoreBasicFlow:
    async def test_store_and_search(self, chroma_store: ChromaDBStore):
        chunks = [
            ("c1", "alpha content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta content", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 1}),
        ]
        await chroma_store.store("doc-1", chunks)

        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert len(results) >= 1
        assert results[0].chunk_id == "c1"
        assert results[0].document_id == "doc-1"
        assert results[0].score > 0

    async def test_search_returns_correct_order(self, chroma_store: ChromaDBStore):
        chunks = [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta", [0.7, 0.7, 0.0, 0.0], {"chunk_index": 1}),
            ("c3", "gamma", [0.0, 0.0, 1.0, 0.0], {"chunk_index": 2}),
        ]
        await chroma_store.store("doc-1", chunks)

        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=3)
        assert len(results) >= 2
        assert results[0].chunk_id == "c1"
        assert results[0].score >= results[1].score

    async def test_search_respects_top_k(self, chroma_store: ChromaDBStore):
        chunks = [
            ("c1", "a", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "b", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 1}),
            ("c3", "c", [0.8, 0.2, 0.0, 0.0], {"chunk_index": 2}),
        ]
        await chroma_store.store("doc-1", chunks)

        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=1)
        assert len(results) == 1

    async def test_search_empty_store(self, chroma_store: ChromaDBStore):
        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []


class TestChromaDBStoreDelete:
    async def test_delete_removes_chunks(self, chroma_store: ChromaDBStore):
        chunks = [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
        ]
        await chroma_store.store("doc-1", chunks)
        await chroma_store.delete("doc-1")

        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []

    async def test_delete_only_affects_target_document(self, chroma_store: ChromaDBStore):
        await chroma_store.store("doc-1", [
            ("c1", "alpha", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
        ])
        await chroma_store.store("doc-2", [
            ("c2", "beta", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 0}),
        ])

        await chroma_store.delete("doc-1")

        results = await chroma_store.search([0.0, 1.0, 0.0, 0.0], top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "c2"


class TestChromaDBStoreTagFilter:
    async def test_tag_filter_includes_matching(self, chroma_store: ChromaDBStore):
        await chroma_store.store("doc-1", [
            ("c1", "hr content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0, "tags": ["hr"]}),
        ])
        await chroma_store.store("doc-2", [
            ("c2", "finance content", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 0, "tags": ["finance"]}),
        ])

        results = await chroma_store.search(
            [1.0, 0.0, 0.0, 0.0], top_k=5, tag_filter=["hr"]
        )
        assert len(results) == 1
        assert results[0].document_id == "doc-1"

    async def test_no_tag_filter_returns_all(self, chroma_store: ChromaDBStore):
        await chroma_store.store("doc-1", [
            ("c1", "hr content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0, "tags": ["hr"]}),
        ])
        await chroma_store.store("doc-2", [
            ("c2", "finance content", [0.9, 0.1, 0.0, 0.0], {"chunk_index": 0, "tags": ["finance"]}),
        ])

        results = await chroma_store.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert len(results) == 2


class TestChromaDBStoreClose:
    async def test_close_is_noop(self, chroma_store: ChromaDBStore):
        await chroma_store.close()
