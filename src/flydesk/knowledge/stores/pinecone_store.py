# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pinecone-backed VectorStore implementation.

Requires the optional ``pinecone`` package (``pip install pinecone``).
"""

from __future__ import annotations

from typing import Any

from flydesk.knowledge.vector_store import VectorSearchResult


class PineconeStore:
    """VectorStore backed by Pinecone."""

    def __init__(
        self,
        api_key: str,
        index_name: str,
        environment: str | None = None,
    ) -> None:
        from pinecone import Pinecone

        self._pc = Pinecone(api_key=api_key)
        self._index = self._pc.Index(index_name)

    async def store(
        self,
        doc_id: str,
        chunks: list[tuple[str, str, list[float], dict]],
    ) -> None:
        if not chunks:
            return

        vectors: list[dict[str, Any]] = []
        for chunk_id, content, embedding, metadata in chunks:
            meta: dict[str, Any] = {
                "document_id": doc_id,
                "content": content,
                "chunk_index": metadata.get("chunk_index", 0),
            }
            tags = metadata.get("tags")
            if tags and isinstance(tags, list):
                meta["tags"] = tags
            vectors.append({
                "id": chunk_id,
                "values": embedding,
                "metadata": meta,
            })

        self._index.upsert(vectors=vectors)

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        tag_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        filter_dict: dict[str, Any] | None = None
        if tag_filter:
            filter_dict = {"tags": {"$in": tag_filter}}

        response = self._index.query(
            vector=embedding,
            top_k=top_k,
            filter=filter_dict,
            include_metadata=True,
        )

        results: list[VectorSearchResult] = []
        for match in response.get("matches", []):
            meta = match.get("metadata", {})
            score = float(match.get("score", 0.0))
            if score <= 0:
                continue
            results.append(
                VectorSearchResult(
                    chunk_id=match["id"],
                    document_id=meta.get("document_id", ""),
                    content=meta.get("content", ""),
                    chunk_index=int(meta.get("chunk_index", 0)),
                    score=score,
                    metadata=meta,
                )
            )

        return results

    async def delete(self, doc_id: str) -> None:
        self._index.delete(filter={"document_id": doc_id})

    async def close(self) -> None:
        """Pinecone client does not require explicit cleanup."""
