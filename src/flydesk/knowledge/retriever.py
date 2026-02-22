# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Retrieve relevant knowledge via semantic search."""

from __future__ import annotations

import json
import math

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.indexer import EmbeddingProvider
from flydesk.knowledge.models import DocumentChunk, RetrievalResult
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


class KnowledgeRetriever:
    """Retrieve relevant document chunks via cosine similarity."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider

    async def retrieve(self, query: str, *, top_k: int = 3) -> list[RetrievalResult]:
        """Find the most relevant document chunks for a query."""
        # 1. Embed the query
        embeddings = await self._embedding_provider.embed([query])
        query_embedding = embeddings[0]

        # 2. Fetch all chunks and compute cosine similarity
        # (In production, pgvector handles this natively with an index)
        async with self._session_factory() as session:
            result = await session.execute(select(DocumentChunkRow))
            chunks = result.scalars().all()

        scored: list[tuple[float, DocumentChunkRow]] = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            chunk_embedding = json.loads(chunk.embedding)
            score = self._cosine_similarity(query_embedding, chunk_embedding)
            scored.append((score, chunk))

        # 3. Sort by score descending, take top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = scored[:top_k]

        # 4. Fetch document titles and build results
        results: list[RetrievalResult] = []
        async with self._session_factory() as session:
            for score, chunk_row in top_chunks:
                doc_row = await session.get(KnowledgeDocumentRow, chunk_row.document_id)
                title = doc_row.title if doc_row else "Unknown"
                metadata = chunk_row.metadata_
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)
                results.append(
                    RetrievalResult(
                        chunk=DocumentChunk(
                            chunk_id=chunk_row.id,
                            document_id=chunk_row.document_id,
                            content=chunk_row.content,
                            chunk_index=chunk_row.chunk_index,
                            metadata=metadata,
                        ),
                        score=score,
                        document_title=title,
                    )
                )

        return results

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
