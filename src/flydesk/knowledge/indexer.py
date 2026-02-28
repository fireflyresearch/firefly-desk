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
import logging
import re
import uuid
from typing import Any, Protocol

_logger = logging.getLogger(__name__)

from sqlalchemy import select
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
        chunking_mode: str = "auto",
        vector_store: Any | None = None,
        auto_kg_extract: bool = False,
        kg_extractor: Any | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_provider = embedding_provider
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._chunking_mode: str = chunking_mode
        self._vector_store = vector_store
        self._auto_kg_extract = auto_kg_extract
        self._kg_extractor = kg_extractor

    async def index_document(self, document: KnowledgeDocument) -> list[DocumentChunk]:
        """Index a document: store it, chunk it, embed chunks, persist chunks."""
        # 1. Store the document metadata via SQLAlchemy
        async with self._session_factory() as session:
            doc_row = KnowledgeDocumentRow(
                id=document.id,
                title=document.title,
                content=document.content,
                document_type=str(document.document_type),
                source=document.source,
                workspace_ids=_to_json(document.workspace_ids),
                tags=_to_json(document.tags),
                metadata_=_to_json(document.metadata),
            )
            session.add(doc_row)
            await session.commit()

        # 2. Chunk the content (routes through structural/fixed/auto mode)
        chunks = self.chunk_document(document.id, document.content)

        # 3. Generate embeddings
        texts = [c.content for c in chunks]
        embeddings = await self._embedding_provider.embed(texts)

        # 4. Store chunks with embeddings
        if self._vector_store is not None:
            from fireflyframework_genai.vectorstores import VectorDocument

            docs = [
                VectorDocument(
                    id=chunk.chunk_id,
                    text=chunk.content,
                    embedding=embedding,
                    metadata={
                        "document_id": document.id,
                        "chunk_index": chunk.chunk_index,
                        "tags": document.tags,
                        **chunk.metadata,
                    },
                )
                for chunk, embedding in zip(chunks, embeddings)
            ]
            await self._vector_store.upsert(docs)
        else:
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

        # Auto-trigger KG extraction (non-fatal)
        if self._auto_kg_extract and self._kg_extractor:
            try:
                await self._kg_extractor.extract_from_document(
                    document.content, document.title,
                )
            except Exception:
                _logger.debug(
                    "Auto KG extraction failed for %s", document.id,
                )

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

    @staticmethod
    def _split_by_headings(text: str) -> list[dict[str, str]]:
        """Split Markdown text on H1 and H2 ATX headings.

        Returns a list of dicts with ``heading_path`` (the heading text
        including ``#`` prefix) and ``content`` (the body below that heading).
        Content appearing before the first heading is preserved with an empty
        heading_path.
        """
        # Match lines that start with "# " or "## " (H1 / H2 ATX headings).
        # We do NOT split on H3+ (### …).
        pattern = re.compile(r"^(#{1,2})\s+(.+)$", re.MULTILINE)

        sections: list[dict[str, str]] = []
        last_end = 0
        current_heading = ""

        for match in pattern.finditer(text):
            # Capture content before this heading
            content_before = text[last_end : match.start()].strip()
            if content_before or sections:
                # Only add a section if there is content, or if we already
                # started collecting (to avoid empty leading sections).
                if not sections and content_before:
                    # Content before the first heading
                    sections.append({"heading_path": "", "content": content_before})
                elif sections:
                    sections[-1]["content"] = content_before

            current_heading = match.group(0).strip()
            sections.append({"heading_path": current_heading, "content": ""})
            last_end = match.end()

        # Remaining content after the last heading
        trailing = text[last_end:].strip()
        if sections:
            sections[-1]["content"] = trailing
        else:
            # No headings found at all
            sections.append({"heading_path": "", "content": text.strip()})

        return sections

    def _chunk_text_structural(
        self, document_id: str, text: str
    ) -> list[DocumentChunk]:
        """Chunk text respecting Markdown heading structure.

        Each H1/H2 section becomes one or more chunks.  Sections smaller than
        ``chunk_size * 2`` are kept as a single chunk; larger sections are
        sub-chunked using the fixed sliding-window strategy.  Every chunk
        receives ``metadata = {"section_path": heading_path}``.
        """
        sections = self._split_by_headings(text)

        # Fall back to fixed chunking when there is no meaningful structure
        if len(sections) <= 1:
            return self._chunk_text(document_id, text)

        chunks: list[DocumentChunk] = []
        index = 0

        for section in sections:
            heading_path = section["heading_path"]
            content = section["content"]

            # Prepend heading to content so it appears in the chunk text
            full_text = f"{heading_path}\n{content}".strip() if heading_path else content
            if not full_text:
                continue

            if len(full_text) > self._chunk_size * 2:
                # Sub-chunk large sections with the fixed strategy
                sub_chunks = self._chunk_text(document_id, full_text)
                for sc in sub_chunks:
                    sc.chunk_index = index
                    sc.metadata = {"section_path": heading_path}
                    chunks.append(sc)
                    index += 1
            else:
                chunks.append(
                    DocumentChunk(
                        chunk_id=str(uuid.uuid4()),
                        document_id=document_id,
                        content=full_text,
                        chunk_index=index,
                        metadata={"section_path": heading_path},
                    )
                )
                index += 1

        return chunks

    def chunk_document(
        self,
        document_id: str,
        text: str,
        mode: str | None = None,
    ) -> list[DocumentChunk]:
        """Public entry point for chunking a document.

        Parameters:
            document_id: Identifier for the parent document.
            text: The full document text.
            mode: ``"fixed"``, ``"structural"``, or ``"auto"``.  Falls back
                to ``self._chunking_mode`` when *None*.

        ``"auto"`` mode detects Markdown H1/H2 headings and uses structural
        chunking when found, fixed otherwise.
        """
        effective_mode = mode or self._chunking_mode
        if effective_mode == "auto":
            effective_mode = "structural" if re.search(r"^#{1,2}\s+", text, re.MULTILINE) else "fixed"
        if effective_mode == "structural":
            return self._chunk_text_structural(document_id, text)
        return self._chunk_text(document_id, text)

    async def index_document_async(
        self,
        document: KnowledgeDocument,
        producer: Any,
    ) -> None:
        """Publish the document to the indexing queue for background processing.

        Parameters:
            document: The document to index.
            producer: An ``IndexingQueueProducer`` instance.
        """
        from flydesk.knowledge.queue import IndexingTask

        task = IndexingTask(
            document_id=document.id,
            title=document.title,
            content=document.content,
            document_type=str(document.document_type),
            source=document.source or "",
            tags=document.tags,
            metadata=document.metadata,
            workspace_ids=document.workspace_ids,
        )
        await producer.enqueue(task)

    async def delete_document(self, document_id: str) -> None:
        """Delete a document and all its chunks."""
        from sqlalchemy import delete

        # Delete chunks via vector store if available, otherwise via SQLAlchemy
        if self._vector_store is not None:
            # genai's delete() expects a list of chunk IDs, so look them up first
            async with self._session_factory() as session:
                result = await session.execute(
                    select(DocumentChunkRow.id).where(
                        DocumentChunkRow.document_id == document_id
                    )
                )
                chunk_ids = list(result.scalars().all())
            if chunk_ids:
                await self._vector_store.delete(chunk_ids)
        else:
            async with self._session_factory() as session:
                await session.execute(
                    delete(DocumentChunkRow).where(DocumentChunkRow.document_id == document_id)
                )
                await session.commit()

        # Always delete the document metadata via SQLAlchemy
        async with self._session_factory() as session:
            await session.execute(
                delete(KnowledgeDocumentRow).where(KnowledgeDocumentRow.id == document_id)
            )
            await session.commit()
