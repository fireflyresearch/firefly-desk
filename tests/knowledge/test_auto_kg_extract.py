# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for auto-KG extraction after document indexing."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import KnowledgeDocument


def test_indexer_accepts_kg_params():
    """KnowledgeIndexer should accept auto_kg_extract and kg_extractor params."""
    indexer = KnowledgeIndexer(
        session_factory=MagicMock(),
        embedding_provider=AsyncMock(),
        auto_kg_extract=True,
        kg_extractor=AsyncMock(),
    )
    assert indexer._auto_kg_extract is True
    assert indexer._kg_extractor is not None


def test_indexer_defaults_kg_off():
    """KG extraction should be off by default."""
    indexer = KnowledgeIndexer(
        session_factory=MagicMock(),
        embedding_provider=AsyncMock(),
    )
    assert indexer._auto_kg_extract is False
    assert indexer._kg_extractor is None


@pytest.mark.asyncio
async def test_index_document_triggers_kg_extraction(tmp_path):
    """When auto_kg_extract is True and kg_extractor is provided, extraction runs."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from flydesk.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    embedding_provider = AsyncMock()
    embedding_provider.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

    kg_extractor = AsyncMock()
    kg_extractor.extract_from_document.return_value = ([], [])

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=5000,
        auto_kg_extract=True,
        kg_extractor=kg_extractor,
    )

    doc = KnowledgeDocument(
        id="doc-1",
        title="Test Doc",
        content="Hello world",
    )

    await indexer.index_document(doc)

    kg_extractor.extract_from_document.assert_awaited_once_with(
        "Hello world", "Test Doc",
    )

    await engine.dispose()


@pytest.mark.asyncio
async def test_index_document_no_trigger_when_disabled(tmp_path):
    """When auto_kg_extract is False, extraction should not run."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from flydesk.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    embedding_provider = AsyncMock()
    embedding_provider.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

    kg_extractor = AsyncMock()

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=5000,
        auto_kg_extract=False,
        kg_extractor=kg_extractor,
    )

    doc = KnowledgeDocument(
        id="doc-2",
        title="Test Doc",
        content="Hello world",
    )

    await indexer.index_document(doc)

    kg_extractor.extract_from_document.assert_not_awaited()

    await engine.dispose()


@pytest.mark.asyncio
async def test_index_document_no_trigger_when_no_extractor(tmp_path):
    """When auto_kg_extract is True but kg_extractor is None, no extraction."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from flydesk.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    embedding_provider = AsyncMock()
    embedding_provider.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=5000,
        auto_kg_extract=True,
        kg_extractor=None,
    )

    doc = KnowledgeDocument(
        id="doc-3",
        title="Test Doc",
        content="Hello world",
    )

    # Should not raise even though auto_kg_extract is True
    chunks = await indexer.index_document(doc)
    assert len(chunks) > 0

    await engine.dispose()


@pytest.mark.asyncio
async def test_kg_extraction_failure_is_non_fatal(tmp_path):
    """If KG extraction raises, indexing should still succeed."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from flydesk.models.base import Base

    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    embedding_provider = AsyncMock()
    embedding_provider.embed.return_value = [[0.1, 0.2, 0.3, 0.4]]

    kg_extractor = AsyncMock()
    kg_extractor.extract_from_document.side_effect = RuntimeError("LLM down")

    indexer = KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=embedding_provider,
        chunk_size=5000,
        auto_kg_extract=True,
        kg_extractor=kg_extractor,
    )

    doc = KnowledgeDocument(
        id="doc-4",
        title="Test Doc",
        content="Hello world",
    )

    # Should NOT raise despite KG extraction failing
    chunks = await indexer.index_document(doc)
    assert len(chunks) > 0

    kg_extractor.extract_from_document.assert_awaited_once()

    await engine.dispose()
