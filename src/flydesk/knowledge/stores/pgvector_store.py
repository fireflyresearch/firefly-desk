# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""PgVector-backed VectorStore implementation.

Uses pgvector's native ``<=>`` cosine distance operator for efficient
similarity search on PostgreSQL.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.vector_store import VectorSearchResult
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


class PgVectorStore:
    """VectorStore backed by pgvector on PostgreSQL."""

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
                    embedding=embedding,
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
        async with self._session_factory() as session:
            vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
            score_expr = (1 - DocumentChunkRow.embedding.cosine_distance(vector_str)).label("score")

            stmt = (
                select(DocumentChunkRow, score_expr)
                .where(DocumentChunkRow.embedding.is_not(None))
            )

            if tag_filter:
                # Join with documents to check tags overlap
                stmt = stmt.join(
                    KnowledgeDocumentRow,
                    DocumentChunkRow.document_id == KnowledgeDocumentRow.id,
                )
                # PostgreSQL JSONB: check if any tag in the filter is present
                for tag in tag_filter:
                    stmt = stmt.where(
                        KnowledgeDocumentRow.tags.cast(Any).contains(f'"{tag}"')
                    )

            stmt = (
                stmt.order_by(DocumentChunkRow.embedding.cosine_distance(vector_str))
                .limit(top_k)
            )

            result = await session.execute(stmt)
            rows = result.all()

        results: list[VectorSearchResult] = []
        for chunk, score in rows:
            if score <= 0:
                continue
            metadata = chunk.metadata_
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            results.append(
                VectorSearchResult(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    score=float(score),
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
