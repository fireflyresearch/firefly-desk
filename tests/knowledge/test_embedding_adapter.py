# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for GenAIEmbeddingAdapter."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from fireflyframework_genai.embeddings import EmbeddingResult, EmbeddingUsage

from flydesk.knowledge.embedding_adapter import GenAIEmbeddingAdapter


@pytest.fixture
def mock_embedder() -> AsyncMock:
    embedder = AsyncMock()
    embedder.embed.return_value = EmbeddingResult(
        embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
        model="text-embedding-3-small",
        usage=EmbeddingUsage(total_tokens=10),
        dimensions=3,
    )
    return embedder


@pytest.mark.asyncio
async def test_embed_delegates_to_genai(mock_embedder):
    adapter = GenAIEmbeddingAdapter(mock_embedder)
    result = await adapter.embed(["hello", "world"])
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_embedder.embed.assert_awaited_once_with(["hello", "world"])


@pytest.mark.asyncio
async def test_check_status_ok(mock_embedder):
    adapter = GenAIEmbeddingAdapter(mock_embedder)
    status = await adapter.check_status()
    assert status["status"] == "ok"
    assert status["dimensions"] == 3


@pytest.mark.asyncio
async def test_check_status_zero_vector():
    embedder = AsyncMock()
    embedder.embed.return_value = EmbeddingResult(
        embeddings=[[0.0, 0.0, 0.0]],
        model="test",
        usage=EmbeddingUsage(total_tokens=1),
        dimensions=3,
    )
    adapter = GenAIEmbeddingAdapter(embedder)
    status = await adapter.check_status()
    assert status["status"] == "warning"
    assert "Zero vector" in status["message"]


@pytest.mark.asyncio
async def test_check_status_error():
    embedder = AsyncMock()
    embedder.embed.side_effect = RuntimeError("API down")
    adapter = GenAIEmbeddingAdapter(embedder)
    status = await adapter.check_status()
    assert status["status"] == "error"
    assert "API down" in status["message"]
