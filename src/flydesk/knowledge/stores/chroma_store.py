# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""ChromaDB-backed VectorStore implementation.

Requires the optional ``chromadb`` package (``pip install chromadb``).
Supports persistent, HTTP, and ephemeral client modes.
"""

from __future__ import annotations

from typing import Any

from flydesk.knowledge.vector_store import VectorSearchResult


class ChromaDBStore:
    """VectorStore backed by ChromaDB."""

    def __init__(
        self,
        path: str | None = None,
        url: str | None = None,
    ) -> None:
        import chromadb

        if url:
            self._client = chromadb.HttpClient(host=url)
        elif path:
            self._client = chromadb.PersistentClient(path=path)
        else:
            self._client = chromadb.Client()  # ephemeral

        self._collection = self._client.get_or_create_collection(
            "flydesk_knowledge",
            metadata={"hnsw:space": "cosine"},
        )

    async def store(
        self,
        doc_id: str,
        chunks: list[tuple[str, str, list[float], dict]],
    ) -> None:
        if not chunks:
            return

        ids: list[str] = []
        documents: list[str] = []
        embeddings: list[list[float]] = []
        metadatas: list[dict[str, Any]] = []

        for chunk_id, content, embedding, metadata in chunks:
            ids.append(chunk_id)
            documents.append(content)
            embeddings.append(embedding)
            # ChromaDB metadata values must be str, int, float, or bool.
            # Flatten complex fields into JSON strings where needed.
            meta: dict[str, Any] = {
                "document_id": doc_id,
                "chunk_index": metadata.get("chunk_index", 0),
            }
            # Store tags as a comma-separated string for filtering
            tags = metadata.get("tags")
            if tags and isinstance(tags, list):
                meta["tags"] = ",".join(tags)
            metadatas.append(meta)

        self._collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        tag_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        where: dict[str, Any] | None = None
        if tag_filter:
            # Match documents where the tags field contains any of the filter values
            if len(tag_filter) == 1:
                where = {"tags": {"$contains": tag_filter[0]}}
            else:
                where = {
                    "$or": [{"tags": {"$contains": tag}} for tag in tag_filter],
                }

        query_result = self._collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        results: list[VectorSearchResult] = []
        if not query_result["ids"] or not query_result["ids"][0]:
            return results

        ids = query_result["ids"][0]
        documents = query_result["documents"][0] if query_result.get("documents") else [""] * len(ids)
        metadatas = query_result["metadatas"][0] if query_result.get("metadatas") else [{}] * len(ids)
        distances = query_result["distances"][0] if query_result.get("distances") else [0.0] * len(ids)

        for chunk_id, content, meta, distance in zip(ids, documents, metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity: 1 - distance
            score = 1.0 - distance
            if score <= 0:
                continue
            results.append(
                VectorSearchResult(
                    chunk_id=chunk_id,
                    document_id=meta.get("document_id", ""),
                    content=content or "",
                    chunk_index=int(meta.get("chunk_index", 0)),
                    score=score,
                    metadata=dict(meta) if meta else {},
                )
            )

        return results

    async def delete(self, doc_id: str) -> None:
        self._collection.delete(where={"document_id": doc_id})

    async def close(self) -> None:
        """ChromaDB client does not require explicit cleanup."""
