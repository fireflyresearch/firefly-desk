# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SQLite-backed VectorStore implementation.

Stores embeddings as JSON-serialised text and performs in-memory cosine
similarity for search.  Also supports a keyword-fallback when the query
embedding is a zero vector.
"""

from __future__ import annotations

import json
import math
import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.vector_store import VectorSearchResult
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


class SqliteVectorStore:
    """VectorStore backed by SQLite with in-memory cosine similarity."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def store(
        self,
        doc_id: str,
        chunks: list[tuple[str, str, list[float], dict]],
    ) -> None:
        async with self._session_factory() as session:
            for chunk_id, content, embedding, metadata in chunks:
                chunk_index = metadata.get("chunk_index", 0)
                row = DocumentChunkRow(
                    id=chunk_id,
                    document_id=doc_id,
                    content=content,
                    chunk_index=chunk_index,
                    embedding=json.dumps(embedding),
                    metadata_=json.dumps(metadata, default=str) if metadata else "{}",
                )
                session.add(row)
            await session.commit()

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        tag_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        use_keywords = all(v == 0.0 for v in embedding)

        async with self._session_factory() as session:
            result = await session.execute(select(DocumentChunkRow))
            chunks = result.scalars().all()

        if not chunks:
            return []

        # Build tag filter set and pre-load document tags if needed
        tag_filter_set = set(tag_filter) if tag_filter else None
        doc_tags_cache: dict[str, list[str]] = {}

        if tag_filter_set:
            async with self._session_factory() as session:
                result = await session.execute(select(KnowledgeDocumentRow))
                docs = result.scalars().all()
            for doc in docs:
                tags = doc.tags
                if isinstance(tags, str):
                    tags = json.loads(tags)
                doc_tags_cache[doc.id] = tags or []

        scored: list[tuple[float, DocumentChunkRow]] = []
        for chunk in chunks:
            # Apply tag filter
            if tag_filter_set:
                doc_tags = doc_tags_cache.get(chunk.document_id, [])
                if not tag_filter_set.intersection(doc_tags):
                    continue

            if use_keywords:
                # Cannot do keyword search without a query string; skip zero-vector
                continue

            if chunk.embedding is None:
                continue

            chunk_embedding = (
                json.loads(chunk.embedding)
                if isinstance(chunk.embedding, str)
                else list(chunk.embedding)
            )
            score = _cosine_similarity(embedding, chunk_embedding)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[VectorSearchResult] = []
        for score, chunk in scored[:top_k]:
            metadata = chunk.metadata_
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            results.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    score=score,
                    metadata=metadata or {},
                )
            )
        return results

    async def delete(self, doc_id: str) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentChunkRow).where(DocumentChunkRow.document_id == doc_id)
            )
            await session.commit()

    async def close(self) -> None:
        """No-op -- session factory is managed externally."""


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)
