# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""pgvector-backed vector store implementing genai's BaseVectorStore.

Maps genai :class:`VectorDocument` objects to/from
:class:`~flydesk.models.knowledge_base.DocumentChunkRow` and delegates
similarity search to PostgreSQL's ``<=>`` cosine distance operator via
pgvector.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from fireflyframework_genai.vectorstores import (
    BaseVectorStore,
    SearchFilter,
    SearchResult,
    VectorDocument,
)
from flydesk.models.knowledge_base import DocumentChunkRow

_logger = logging.getLogger(__name__)


class PgVectorGenAIStore(BaseVectorStore):
    """Vector store backed by pgvector on PostgreSQL.

    Implements the three abstract methods required by
    :class:`~fireflyframework_genai.vectorstores.BaseVectorStore`:
    ``_upsert``, ``_search``, and ``_delete``.

    Parameters:
        session_factory: An async SQLAlchemy session factory for database access.
        embedder: Optional embedder passed to the base class for auto-embedding.
        **kwargs: Forwarded to :class:`BaseVectorStore`.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Abstract method implementations
    # ------------------------------------------------------------------

    async def _upsert(self, documents: list[VectorDocument], namespace: str) -> None:
        """Insert or update document chunks in the database."""
        async with self._session_factory() as session:
            for doc in documents:
                existing = await session.get(DocumentChunkRow, doc.id)
                if existing:
                    existing.content = doc.text
                    if doc.embedding is not None:
                        existing.embedding = doc.embedding
                    if doc.metadata:
                        existing.metadata_ = json.dumps(doc.metadata)
                else:
                    row = DocumentChunkRow(
                        id=doc.id,
                        document_id=doc.metadata.get("document_id", ""),
                        content=doc.text,
                        chunk_index=doc.metadata.get("chunk_index", 0),
                        embedding=doc.embedding,
                        metadata_=json.dumps(doc.metadata) if doc.metadata else "{}",
                    )
                    session.add(row)
            await session.commit()

    async def _search(
        self,
        query_embedding: list[float],
        top_k: int,
        namespace: str,
        filters: list[SearchFilter] | None,
    ) -> list[SearchResult]:
        """Execute cosine similarity search using pgvector's ``<=>`` operator."""
        async with self._session_factory() as session:
            embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

            query = text(
                """
                SELECT id, document_id, content, chunk_index, metadata,
                       1 - (embedding <=> :embedding) AS score
                FROM kb_chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :embedding
                LIMIT :top_k
                """
            )

            result = await session.execute(
                query, {"embedding": embedding_str, "top_k": top_k}
            )

            results: list[SearchResult] = []
            for row in result.fetchall():
                metadata = json.loads(row.metadata) if row.metadata else {}
                metadata["document_id"] = row.document_id
                metadata["chunk_index"] = row.chunk_index

                doc = VectorDocument(
                    id=row.id,
                    text=row.content,
                    metadata=metadata,
                )
                results.append(SearchResult(document=doc, score=float(row.score)))

            return results

    async def _delete(self, ids: list[str], namespace: str) -> None:
        """Delete document chunks by their IDs."""
        async with self._session_factory() as session:
            stmt = delete(DocumentChunkRow).where(DocumentChunkRow.id.in_(ids))
            await session.execute(stmt)
            await session.commit()
