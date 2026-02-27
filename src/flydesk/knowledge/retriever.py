# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Retrieve relevant knowledge via semantic search with keyword fallback.

Uses pgvector's native cosine distance operator (``<=>``) for PostgreSQL,
or in-memory cosine similarity / keyword matching for SQLite.
"""

from __future__ import annotations

import json
import logging
import math
import re

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.indexer import EmbeddingProvider
from flydesk.knowledge.models import DocumentChunk, RetrievalResult
from flydesk.knowledge.vector_store import VectorStore
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow

_logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """Retrieve relevant document chunks via semantic or keyword search.

    When running on PostgreSQL with pgvector, uses the native ``<=>`` cosine
    distance operator for efficient vector search.  When running on SQLite
    (dev mode) or when embeddings are zero vectors, falls back to keyword
    scoring.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        vector_store: VectorStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store

        # Detect SQL dialect at init time.  AsyncSession.bind is always None
        # in SQLAlchemy 2.x so we read the engine from the session factory's
        # configuration instead.
        try:
            engine = session_factory.kw.get("bind")
            self._dialect: str = engine.dialect.name if engine else "sqlite"
        except (AttributeError, TypeError):
            self._dialect = "sqlite"

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 3,
        tag_filter: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Find the most relevant document chunks for a query.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            tag_filter: When set, only return chunks from documents whose tags
                overlap with this list.  ``None`` disables filtering.
        """
        # 1. Embed the query
        embeddings = await self._embedding_provider.embed([query])
        query_embedding = embeddings[0]

        # Detect zero-vector embeddings (no real provider configured)
        use_keywords = all(v == 0.0 for v in query_embedding)

        # 2. Delegate to vector store if available
        if self._vector_store is not None and not use_keywords:
            vs_results = await self._vector_store.search(
                query_embedding, top_k, tag_filter=tag_filter,
            )
            # Fetch document titles from SQLAlchemy for building RetrievalResult
            results: list[RetrievalResult] = []
            async with self._session_factory() as session:
                for vsr in vs_results:
                    doc_row = await session.get(KnowledgeDocumentRow, vsr.document_id)
                    title = doc_row.title if doc_row else ""
                    results.append(
                        RetrievalResult(
                            chunk=DocumentChunk(
                                chunk_id=vsr.chunk_id,
                                document_id=vsr.document_id,
                                content=vsr.content,
                                chunk_index=vsr.chunk_index,
                                metadata=vsr.metadata,
                            ),
                            score=vsr.score,
                            document_title=title,
                        )
                    )
            return results

        # 3. Determine backend and route to appropriate search strategy
        # Over-fetch when tag_filter is set so post-filtering can still
        # return up to top_k results.
        fetch_k = top_k * 3 if tag_filter else top_k

        if use_keywords:
            scored = await self._keyword_search(query, fetch_k)
        elif self._dialect == "postgresql":
            scored = await self._pgvector_search(query_embedding, fetch_k)
        else:
            scored = await self._inmemory_search(query_embedding, fetch_k)

        # 4. Fetch document titles and build results (with tag filtering)
        tag_filter_set = set(tag_filter) if tag_filter else None
        results = []
        async with self._session_factory() as session:
            for score, chunk_row in scored:
                doc_row = await session.get(KnowledgeDocumentRow, chunk_row.document_id)
                if doc_row is None:
                    continue

                # Apply tag filter: skip documents with no overlapping tags
                if tag_filter_set is not None:
                    doc_tags = doc_row.tags
                    if isinstance(doc_tags, str):
                        doc_tags = json.loads(doc_tags)
                    if not tag_filter_set.intersection(doc_tags or []):
                        continue

                title = doc_row.title
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
                if len(results) >= top_k:
                    break

        if use_keywords and results:
            _logger.debug(
                "Keyword fallback returned %d results for query: %.60s",
                len(results), query,
            )

        return results

    # ------------------------------------------------------------------
    # Search strategies
    # ------------------------------------------------------------------

    async def _pgvector_search(
        self, query_embedding: list[float], top_k: int
    ) -> list[tuple[float, DocumentChunkRow]]:
        """Use pgvector's native cosine distance operator for fast retrieval."""
        async with self._session_factory() as session:
            # pgvector <=> returns cosine DISTANCE (0 = identical, 2 = opposite).
            # Convert to similarity: 1 - distance.
            vector_str = "[" + ",".join(str(v) for v in query_embedding) + "]"
            stmt = (
                select(
                    DocumentChunkRow,
                    (1 - DocumentChunkRow.embedding.cosine_distance(vector_str)).label("score"),
                )
                .where(DocumentChunkRow.embedding.is_not(None))
                .order_by(DocumentChunkRow.embedding.cosine_distance(vector_str))
                .limit(top_k)
            )
            result = await session.execute(stmt)
            rows = result.all()

        return [(float(score), chunk) for chunk, score in rows if score > 0]

    async def _inmemory_search(
        self, query_embedding: list[float], top_k: int
    ) -> list[tuple[float, DocumentChunkRow]]:
        """In-memory cosine similarity for SQLite (dev mode)."""
        async with self._session_factory() as session:
            result = await session.execute(select(DocumentChunkRow))
            chunks = result.scalars().all()

        if not chunks:
            return []

        scored = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            # SQLite stores embeddings as JSON strings
            chunk_embedding = (
                json.loads(chunk.embedding)
                if isinstance(chunk.embedding, str)
                else list(chunk.embedding)
            )
            score = self._cosine_similarity(query_embedding, chunk_embedding)
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    async def _keyword_search(
        self, query: str, top_k: int
    ) -> list[tuple[float, DocumentChunkRow]]:
        """Score chunks by keyword overlap with the query."""
        async with self._session_factory() as session:
            result = await session.execute(select(DocumentChunkRow))
            chunks = result.scalars().all()

        if not chunks:
            return []

        scored = self._keyword_score(query, chunks)
        scored = [(s, c) for s, c in scored if s > 0]
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _keyword_score(
        query: str, chunks: list[DocumentChunkRow],
    ) -> list[tuple[float, DocumentChunkRow]]:
        """Score chunks by keyword overlap with the query.

        Extracts significant words (3+ chars) from the query, then counts
        how many appear in each chunk's content (case-insensitive). The score
        is the fraction of query terms found.
        """
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all", "can",
            "had", "her", "was", "one", "our", "out", "has", "have", "been",
            "will", "with", "this", "that", "from", "they", "what", "how",
            "when", "where", "which", "who", "whom", "why", "about", "into",
            "does", "show", "tell", "give", "help", "please", "could", "would",
            "should", "there", "their", "them", "then", "than", "some",
        }
        words = re.findall(r"\w+", query.lower())
        terms = [w for w in words if len(w) >= 3 and w not in stop_words]

        if not terms:
            return []

        scored: list[tuple[float, DocumentChunkRow]] = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            matches = sum(1 for term in terms if term in content_lower)
            if matches > 0:
                score = matches / len(terms)
                scored.append((score, chunk))

        return scored

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = math.sqrt(sum(x * x for x in a))
        mag_b = math.sqrt(sum(x * x for x in b))
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)
