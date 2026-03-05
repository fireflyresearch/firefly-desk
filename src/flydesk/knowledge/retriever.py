# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Retrieve relevant knowledge via hybrid semantic + keyword search.

Uses pgvector's native cosine distance operator (``<=>``) for PostgreSQL,
or in-memory cosine similarity for SQLite, combined with TF-weighted keyword
search via reciprocal-rank fusion (RRF).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
from collections import Counter
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flydesk.knowledge.cache import KnowledgeCache

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.indexer import EmbeddingProvider
from flydesk.knowledge.models import DocumentChunk, RetrievalResult
from flydesk.knowledge.scoring import (
    STOP_WORDS,
    deduplicate_results,
    normalize_scores,
    reciprocal_rank_fusion,
    simple_stem,
)
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
        vector_store: Any | None = None,
        cache: KnowledgeCache | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._vector_store = vector_store
        self._cache = cache

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
        top_k: int = 5,
        tag_filter: list[str] | None = None,
    ) -> list[RetrievalResult]:
        """Find the most relevant document chunks for a query.

        Uses hybrid search: semantic and keyword searches run in parallel,
        then results are merged via reciprocal-rank fusion (RRF).

        When no real embedding provider is configured (zero-vector embeddings),
        falls back to keyword-only search.

        Args:
            query: The search query text.
            top_k: Maximum number of results to return.
            tag_filter: When set, only return chunks from documents whose tags
                overlap with this list.  ``None`` disables filtering.
        """
        # 0. Check cache before running the search
        query_hash: str | None = None
        if self._cache is not None:
            query_hash = hashlib.md5(query.encode()).hexdigest()  # noqa: S324
            cached = await self._cache.get_retrieval(query_hash)
            if cached is not None:
                _logger.debug("Cache hit for query hash %s", query_hash)
                return [RetrievalResult.model_validate(r) for r in cached]

        # 1. Embed the query
        embeddings = await self._embedding_provider.embed([query])
        query_embedding = embeddings[0]

        # Detect zero-vector embeddings (no real provider configured)
        use_keywords_only = all(v == 0.0 for v in query_embedding)

        # 2. Delegate to vector store if available (external vector store path)
        if self._vector_store is not None and not use_keywords_only:
            # Over-fetch when tag_filter is set so post-filtering can still
            # return up to top_k results.
            fetch_k = top_k * 3 if tag_filter else top_k
            vs_results = await self._vector_store.search(
                query_embedding, top_k=fetch_k,
            )
            # Build RetrievalResult objects from genai SearchResult objects
            tag_filter_set = set(tag_filter) if tag_filter else None
            results: list[RetrievalResult] = []
            async with self._session_factory() as session:
                for sr in vs_results:
                    metadata = dict(sr.document.metadata)
                    document_id = metadata.get("document_id", "")
                    chunk_index = metadata.get("chunk_index", 0)

                    # Resolve document title and apply tag filter
                    doc_row = await session.get(KnowledgeDocumentRow, document_id)
                    if doc_row is None:
                        continue

                    if tag_filter_set is not None:
                        doc_tags = doc_row.tags
                        if isinstance(doc_tags, str):
                            doc_tags = json.loads(doc_tags)
                        if not tag_filter_set.intersection(doc_tags or []):
                            continue

                    title = doc_row.title if doc_row else ""
                    results.append(
                        RetrievalResult(
                            chunk=DocumentChunk(
                                chunk_id=sr.document.id,
                                document_id=document_id,
                                content=sr.document.text,
                                chunk_index=chunk_index,
                                metadata=metadata,
                            ),
                            score=sr.score,
                            document_title=title,
                        )
                    )
                    if len(results) >= top_k:
                        break

            # Store results in cache for future queries
            if self._cache is not None and query_hash is not None and results:
                await self._cache.set_retrieval(
                    query_hash, [r.model_dump() for r in results]
                )
            return results

        # 3. Hybrid search: run semantic + keyword in parallel with RRF fusion
        # Over-fetch to leave room for dedup and tag filtering.
        fetch_k = top_k * 3 if tag_filter else top_k * 2

        if use_keywords_only:
            # No real embeddings -- keyword-only fallback
            scored = await self._keyword_search_enhanced(query, fetch_k)
        else:
            # Run semantic and keyword searches in parallel
            semantic_coro = (
                self._pgvector_search(query_embedding, fetch_k)
                if self._dialect == "postgresql"
                else self._inmemory_search(query_embedding, fetch_k)
            )
            semantic_scored, keyword_scored = await asyncio.gather(
                semantic_coro,
                self._keyword_search_enhanced(query, fetch_k),
            )

            # Convert (score, chunk_row) tuples to dicts for scoring utilities
            semantic_dicts = self._scored_to_dicts(semantic_scored)
            keyword_dicts = self._scored_to_dicts(keyword_scored)

            if semantic_dicts and keyword_dicts:
                semantic_norm = normalize_scores(semantic_dicts)
                keyword_norm = normalize_scores(keyword_dicts)
                fused = reciprocal_rank_fusion(
                    semantic_norm, keyword_norm, weights=[0.7, 0.3],
                )
                deduped = deduplicate_results(fused, top_k=fetch_k)
                scored = self._dicts_to_scored(deduped)
            elif semantic_dicts:
                scored = semantic_scored
            elif keyword_dicts:
                scored = keyword_scored
            else:
                scored = []

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

        if use_keywords_only and results:
            _logger.debug(
                "Keyword fallback returned %d results for query: %.60s",
                len(results), query,
            )

        # Store results in cache for future queries
        if self._cache is not None and query_hash is not None and results:
            await self._cache.set_retrieval(
                query_hash, [r.model_dump() for r in results]
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

    async def _keyword_search_enhanced(
        self, query: str, top_k: int
    ) -> list[tuple[float, DocumentChunkRow]]:
        """TF-weighted keyword search with stemming and stop-word removal.

        For each query term (stemmed), counts occurrences in each chunk's
        content and normalises by the maximum term frequency in that chunk.
        The final score is the mean of per-term TF weights across all query
        terms that appear in the chunk.
        """
        async with self._session_factory() as session:
            result = await session.execute(select(DocumentChunkRow))
            chunks = result.scalars().all()

        if not chunks:
            return []

        # Tokenise, remove stop words, and stem
        words = re.findall(r"\w+", query.lower())
        stemmed_terms = [
            simple_stem(w) for w in words
            if w not in STOP_WORDS and len(w) >= 2
        ]
        if not stemmed_terms:
            return []

        scored: list[tuple[float, DocumentChunkRow]] = []
        for chunk in chunks:
            content_lower = chunk.content.lower()
            content_words = re.findall(r"\w+", content_lower)
            if not content_words:
                continue

            # Build stemmed term-frequency map for this chunk
            stemmed_content = [simple_stem(w) for w in content_words]
            tf_counter = Counter(stemmed_content)
            max_tf = max(tf_counter.values())  # guaranteed > 0

            # Score: mean of normalised TF for matching query terms
            term_scores: list[float] = []
            for term in stemmed_terms:
                freq = tf_counter.get(term, 0)
                if freq > 0:
                    term_scores.append(freq / max_tf)

            if term_scores:
                score = sum(term_scores) / len(stemmed_terms)
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]

    # ------------------------------------------------------------------
    # Conversion helpers for hybrid scoring
    # ------------------------------------------------------------------

    @staticmethod
    def _scored_to_dicts(
        scored: list[tuple[float, DocumentChunkRow]],
    ) -> list[dict[str, Any]]:
        """Convert ``(score, chunk_row)`` tuples to dicts for scoring utilities."""
        return [
            {"chunk_id": chunk_row.id, "score": score, "_chunk_row": chunk_row}
            for score, chunk_row in scored
        ]

    @staticmethod
    def _dicts_to_scored(
        dicts: list[dict[str, Any]],
    ) -> list[tuple[float, DocumentChunkRow]]:
        """Convert scoring-utility dicts back to ``(score, chunk_row)`` tuples."""
        return [(d["score"], d["_chunk_row"]) for d in dicts if "_chunk_row" in d]

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
