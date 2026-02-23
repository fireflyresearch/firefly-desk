# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Index knowledge documents into chunks for retrieval."""

from __future__ import annotations

import json
import uuid
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.knowledge.models import DocumentChunk, KnowledgeDocument
from flydesk.models.knowledge_base import DocumentChunkRow, KnowledgeDocumentRow


def _serialize_embedding(embedding: list[float], dialect_name: str) -> Any:
    """Serialize an embedding vector for storage.

    PostgreSQL with pgvector accepts the list directly.
    SQLite stores the vector as a JSON string.
    """
    if dialect_name == "sqlite":
        return json.dumps(embedding)
    return embedding


class EmbeddingProvider(Protocol):
    """Protocol for embedding generation."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def _to_json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)


class KnowledgeIndexer:
    """Index documents into chunks with embeddings."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def index_document(self, document: KnowledgeDocument) -> list[DocumentChunk]:
        """Index a document: store it, chunk it, embed chunks, persist chunks."""
        # 1. Store the document
        async with self._session_factory() as session:
            doc_row = KnowledgeDocumentRow(
                id=document.id,
                title=document.title,
                content=document.content,
                document_type=str(document.document_type),
                source=document.source,
                tags=_to_json(document.tags),
                metadata_=_to_json(document.metadata),
            )
            session.add(doc_row)
            await session.commit()

        # 2. Chunk the content
        chunks = self._chunk_text(document.id, document.content)

        # 3. Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = await self._embedding_provider.embed(texts)

        # 4. Store chunks with embeddings
        async with self._session_factory() as session:
            dialect = session.bind.dialect.name if session.bind else "sqlite"
            for chunk, embedding in zip(chunks, embeddings):
                row = DocumentChunkRow(
                    id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    content=chunk.content,
                    chunk_index=chunk.chunk_index,
                    embedding=_serialize_embedding(embedding, dialect),
                    metadata_=_to_json(chunk.metadata),
                )
                session.add(row)
            await session.commit()

        return chunks

    def _chunk_text(self, document_id: str, text: str) -> list[DocumentChunk]:
        """Split text into overlapping chunks."""
        chunks: list[DocumentChunk] = []
        start = 0
        index = 0
        while start < len(text):
            end = start + self._chunk_size
            chunk_content = text[start:end]
            chunks.append(
                DocumentChunk(
                    chunk_id=str(uuid.uuid4()),
                    document_id=document_id,
                    content=chunk_content,
                    chunk_index=index,
                )
            )
            start += self._chunk_size - self._chunk_overlap
            index += 1
        return chunks

    async def delete_document(self, document_id: str) -> None:
        """Delete a document and all its chunks."""
        from sqlalchemy import delete

        async with self._session_factory() as session:
            await session.execute(
                delete(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id)
            )
            await session.execute(
                delete(KnowledgeDocumentRow).where(KnowledgeDocumentRow.id == document_id)
            )
            await session.commit()
