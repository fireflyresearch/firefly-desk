# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for KnowledgeGraph entity embedding and semantic search."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.graph import Entity, KnowledgeGraph
from flydesk.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def mock_embedding_provider() -> AsyncMock:
    provider = AsyncMock()
    provider.embed.return_value = [[0.1, 0.2, 0.3]]
    return provider


@pytest.fixture
def sample_entity() -> Entity:
    return Entity(
        id="acme-corp",
        entity_type="company",
        name="Acme Corporation",
        properties={"industry": "technology"},
        source_system="crm",
        confidence=0.95,
    )


class TestKnowledgeGraphEmbeddingInit:
    """Test that KnowledgeGraph accepts embedding_provider parameter."""

    def test_accepts_embedding_provider(self, session_factory, mock_embedding_provider):
        kg = KnowledgeGraph(session_factory, embedding_provider=mock_embedding_provider)
        assert kg._embedding_provider is mock_embedding_provider

    def test_works_without_embedding_provider(self, session_factory):
        kg = KnowledgeGraph(session_factory)
        assert kg._embedding_provider is None

    def test_backward_compatible_positional_arg(self, session_factory):
        """Ensure positional-only session_factory still works."""
        kg = KnowledgeGraph(session_factory)
        assert kg._session_factory is session_factory


class TestUpsertEntityEmbedding:
    """Test that upsert_entity generates embeddings when provider is available."""

    async def test_upsert_calls_embedding_provider(
        self, session_factory, mock_embedding_provider, sample_entity
    ):
        kg = KnowledgeGraph(session_factory, embedding_provider=mock_embedding_provider)
        await kg.upsert_entity(sample_entity)

        mock_embedding_provider.embed.assert_awaited_once()
        call_args = mock_embedding_provider.embed.call_args[0][0]
        assert len(call_args) == 1
        assert "Acme Corporation" in call_args[0]
        assert "company" in call_args[0]

    async def test_upsert_works_without_embedding_provider(
        self, session_factory, sample_entity
    ):
        kg = KnowledgeGraph(session_factory)
        await kg.upsert_entity(sample_entity)

        result = await kg.get_entity("acme-corp")
        assert result is not None
        assert result.name == "Acme Corporation"

    async def test_upsert_continues_if_embedding_fails(
        self, session_factory, sample_entity
    ):
        provider = AsyncMock()
        provider.embed.side_effect = RuntimeError("API error")

        kg = KnowledgeGraph(session_factory, embedding_provider=provider)
        await kg.upsert_entity(sample_entity)

        # Entity should still be persisted despite embedding failure
        result = await kg.get_entity("acme-corp")
        assert result is not None
        assert result.name == "Acme Corporation"

    async def test_upsert_update_calls_embedding_provider(
        self, session_factory, mock_embedding_provider, sample_entity
    ):
        kg = KnowledgeGraph(session_factory, embedding_provider=mock_embedding_provider)
        await kg.upsert_entity(sample_entity)
        mock_embedding_provider.embed.reset_mock()

        # Upsert again to trigger update path
        sample_entity.name = "Acme Corp Updated"
        await kg.upsert_entity(sample_entity)

        mock_embedding_provider.embed.assert_awaited_once()
        call_args = mock_embedding_provider.embed.call_args[0][0]
        assert "Acme Corp Updated" in call_args[0]


class TestFindRelevantEntitiesEmbedding:
    """Test that find_relevant_entities uses semantic search when provider is available."""

    async def test_uses_like_without_provider(self, session_factory):
        kg = KnowledgeGraph(session_factory)
        await kg.upsert_entity(
            Entity(id="e1", entity_type="company", name="Acme Corporation")
        )
        results = await kg.find_relevant_entities("acme")
        assert len(results) == 1
        assert results[0].name == "Acme Corporation"

    async def test_calls_embedding_provider_for_semantic_search(
        self, session_factory, mock_embedding_provider
    ):
        kg = KnowledgeGraph(session_factory, embedding_provider=mock_embedding_provider)
        await kg.upsert_entity(
            Entity(id="e1", entity_type="company", name="Acme Corporation")
        )
        mock_embedding_provider.embed.reset_mock()

        # Semantic search will fail on SQLite (no pgvector), should fall back to LIKE
        results = await kg.find_relevant_entities("acme")

        # The provider should have been called for embedding the query
        mock_embedding_provider.embed.assert_awaited()

        # Despite pgvector not being available on SQLite, the LIKE fallback should work
        assert len(results) == 1
        assert results[0].name == "Acme Corporation"

    async def test_falls_back_to_like_on_embedding_error(self, session_factory):
        provider = AsyncMock()
        provider.embed.side_effect = RuntimeError("API down")

        kg = KnowledgeGraph(session_factory, embedding_provider=provider)
        await kg.upsert_entity(
            Entity(id="e1", entity_type="company", name="Acme Corporation")
        )

        # Should fall back to LIKE search when embedding fails
        results = await kg.find_relevant_entities("acme")
        assert len(results) == 1
        assert results[0].name == "Acme Corporation"

    async def test_find_by_like_direct(self, session_factory):
        """Test _find_by_like method directly."""
        kg = KnowledgeGraph(session_factory)
        await kg.upsert_entity(
            Entity(id="e1", entity_type="company", name="Acme Corporation")
        )
        await kg.upsert_entity(
            Entity(id="e2", entity_type="person", name="Alice Smith")
        )
        results = await kg._find_by_like("acme", 5)
        assert len(results) == 1
        assert results[0].id == "e1"
