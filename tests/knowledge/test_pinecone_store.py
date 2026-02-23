# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for Pinecone VectorStore implementation (fully mocked)."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# Build a mock pinecone module so PineconeStore can import it without
# the real package being installed.
_mock_pinecone_module = types.ModuleType("pinecone")


class _FakePinecone:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._indexes: dict[str, MagicMock] = {}

    def Index(self, name: str) -> MagicMock:
        if name not in self._indexes:
            self._indexes[name] = MagicMock()
        return self._indexes[name]


_mock_pinecone_module.Pinecone = _FakePinecone  # type: ignore[attr-defined]
sys.modules.setdefault("pinecone", _mock_pinecone_module)


from flydesk.knowledge.stores.pinecone_store import PineconeStore
from flydesk.knowledge.vector_store import VectorStore


@pytest.fixture
def mock_index() -> MagicMock:
    """Return the mock Pinecone index used by the store."""
    store = PineconeStore(api_key="test-key", index_name="test-index")
    return store._index


@pytest.fixture
def pinecone_store() -> PineconeStore:
    return PineconeStore(api_key="test-key", index_name="test-index")


class TestPineconeStoreProtocol:
    def test_implements_protocol(self, pinecone_store: PineconeStore):
        assert isinstance(pinecone_store, VectorStore)


class TestPineconeStoreStore:
    async def test_store_calls_upsert(self, pinecone_store: PineconeStore):
        chunks = [
            ("c1", "alpha content", [1.0, 0.0, 0.0, 0.0], {"chunk_index": 0}),
            ("c2", "beta content", [0.0, 1.0, 0.0, 0.0], {"chunk_index": 1}),
        ]
        await pinecone_store.store("doc-1", chunks)

        pinecone_store._index.upsert.assert_called_once()
        call_kwargs = pinecone_store._index.upsert.call_args
        vectors = call_kwargs[1]["vectors"] if "vectors" in call_kwargs[1] else call_kwargs[0][0]
        assert len(vectors) == 2
        assert vectors[0]["id"] == "c1"
        assert vectors[0]["values"] == [1.0, 0.0, 0.0, 0.0]
        assert vectors[0]["metadata"]["document_id"] == "doc-1"
        assert vectors[0]["metadata"]["content"] == "alpha content"

    async def test_store_empty_chunks_is_noop(self, pinecone_store: PineconeStore):
        await pinecone_store.store("doc-1", [])
        pinecone_store._index.upsert.assert_not_called()

    async def test_store_includes_tags_in_metadata(self, pinecone_store: PineconeStore):
        chunks = [
            ("c1", "content", [1.0, 0.0], {"chunk_index": 0, "tags": ["hr", "policy"]}),
        ]
        await pinecone_store.store("doc-1", chunks)

        call_kwargs = pinecone_store._index.upsert.call_args
        vectors = call_kwargs[1]["vectors"]
        assert vectors[0]["metadata"]["tags"] == ["hr", "policy"]


class TestPineconeStoreSearch:
    async def test_search_calls_query(self, pinecone_store: PineconeStore):
        pinecone_store._index.query.return_value = {
            "matches": [
                {
                    "id": "c1",
                    "score": 0.95,
                    "metadata": {
                        "document_id": "doc-1",
                        "content": "alpha content",
                        "chunk_index": 0,
                    },
                },
            ]
        }

        results = await pinecone_store.search([1.0, 0.0, 0.0, 0.0], top_k=3)

        pinecone_store._index.query.assert_called_once_with(
            vector=[1.0, 0.0, 0.0, 0.0],
            top_k=3,
            filter=None,
            include_metadata=True,
        )
        assert len(results) == 1
        assert results[0].chunk_id == "c1"
        assert results[0].document_id == "doc-1"
        assert results[0].content == "alpha content"
        assert results[0].score == 0.95

    async def test_search_with_tag_filter(self, pinecone_store: PineconeStore):
        pinecone_store._index.query.return_value = {"matches": []}

        await pinecone_store.search(
            [1.0, 0.0, 0.0, 0.0], top_k=3, tag_filter=["hr", "policy"]
        )

        pinecone_store._index.query.assert_called_once_with(
            vector=[1.0, 0.0, 0.0, 0.0],
            top_k=3,
            filter={"tags": {"$in": ["hr", "policy"]}},
            include_metadata=True,
        )

    async def test_search_filters_zero_score(self, pinecone_store: PineconeStore):
        pinecone_store._index.query.return_value = {
            "matches": [
                {"id": "c1", "score": 0.9, "metadata": {"document_id": "d1", "content": "a", "chunk_index": 0}},
                {"id": "c2", "score": 0.0, "metadata": {"document_id": "d1", "content": "b", "chunk_index": 1}},
            ]
        }

        results = await pinecone_store.search([1.0, 0.0], top_k=5)
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    async def test_search_empty_matches(self, pinecone_store: PineconeStore):
        pinecone_store._index.query.return_value = {"matches": []}

        results = await pinecone_store.search([1.0, 0.0], top_k=5)
        assert results == []


class TestPineconeStoreDelete:
    async def test_delete_calls_index_delete(self, pinecone_store: PineconeStore):
        await pinecone_store.delete("doc-1")

        pinecone_store._index.delete.assert_called_once_with(
            filter={"document_id": "doc-1"}
        )


class TestPineconeStoreClose:
    async def test_close_is_noop(self, pinecone_store: PineconeStore):
        await pinecone_store.close()
