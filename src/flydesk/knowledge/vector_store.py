# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""VectorStore protocol and shared types for vector storage backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class VectorSearchResult:
    """A single result from a vector similarity search."""

    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    score: float
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for pluggable vector storage backends.

    Implementations handle chunk embedding storage and similarity search.
    Document metadata (``KnowledgeDocumentRow``) remains in SQLAlchemy.
    """

    async def store(
        self,
        doc_id: str,
        chunks: list[tuple[str, str, list[float], dict]],
    ) -> None:
        """Store chunks for a document.

        Each tuple contains ``(chunk_id, content, embedding, metadata)``.
        The *metadata* dict should carry at least ``chunk_index``.
        """
        ...

    async def search(
        self,
        embedding: list[float],
        top_k: int,
        tag_filter: list[str] | None = None,
    ) -> list[VectorSearchResult]:
        """Search for similar chunks by embedding vector.

        Returns results ordered by descending similarity score.
        When *tag_filter* is provided, only chunks belonging to documents
        whose tags overlap with the filter are considered.
        """
        ...

    async def delete(self, doc_id: str) -> None:
        """Delete all chunks belonging to *doc_id*."""
        ...

    async def close(self) -> None:
        """Release resources held by the store."""
        ...
