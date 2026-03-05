# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for database-backed knowledge cache."""

from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def cache():
    from flydesk.knowledge.cache import KnowledgeCache

    return KnowledgeCache(AsyncMock(), max_memory_items=100)


@pytest.fixture
def small_cache():
    from flydesk.knowledge.cache import KnowledgeCache

    return KnowledgeCache(AsyncMock(), max_memory_items=2)


@pytest.mark.asyncio
async def test_set_and_get_embedding(cache):
    await cache.set_embedding("hash123", [0.1, 0.2, 0.3], ttl=3600)
    result = await cache.get_embedding("hash123")
    assert result == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_get_embedding_returns_none_for_missing(cache):
    result = await cache.get_embedding("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_set_and_get_search_results(cache):
    results = [{"chunk_id": "c1", "score": 0.9}]
    await cache.set_retrieval("query_hash", results, ttl=300)
    cached = await cache.get_retrieval("query_hash")
    assert cached == results


@pytest.mark.asyncio
async def test_invalidate_document_clears_search_cache(cache):
    await cache.set_retrieval("q1", [{"chunk_id": "c1"}], ttl=300)
    await cache.invalidate_document("doc1")
    result = await cache.get_retrieval("q1")
    assert result is None


@pytest.mark.asyncio
async def test_invalidate_preserves_embeddings(cache):
    await cache.set_embedding("h1", [0.1], ttl=3600)
    await cache.invalidate_document("doc1")
    result = await cache.get_embedding("h1")
    assert result == [0.1]


@pytest.mark.asyncio
async def test_memory_eviction(small_cache):
    await small_cache.set_embedding("h1", [0.1], ttl=3600)
    await small_cache.set_embedding("h2", [0.2], ttl=3600)
    await small_cache.set_embedding("h3", [0.3], ttl=3600)  # Should evict h1

    assert small_cache._get_from_memory("embedding", "h1") is None
    assert small_cache._get_from_memory("embedding", "h3") == [0.3]


@pytest.mark.asyncio
async def test_expired_entry_returns_none(cache):
    await cache.set_embedding("h1", [0.1], ttl=0)  # Expires immediately
    # Need a tiny delay so the timestamp comparison catches expiry
    await asyncio.sleep(0.01)
    result = cache._get_from_memory("embedding", "h1")
    assert result is None
