# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Vector store factory -- instantiates genai-compatible vector store backends."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from fireflyframework_genai.vectorstores import BaseVectorStore
    from flydesk.config import DeskConfig


def create_genai_vector_store(
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    embedder: Any | None = None,
) -> BaseVectorStore:
    """Create a genai :class:`BaseVectorStore` based on *config.vector_store*.

    Parameters:
        config: Application configuration.
        session_factory: Required for the ``pgvector`` backend.
        embedder: A genai ``BaseEmbedder`` for auto-embedding within the store.
    """
    match config.vector_store:
        case "pgvector":
            from flydesk.knowledge.stores.pgvector_genai import PgVectorGenAIStore

            if session_factory is None:
                raise ValueError("session_factory is required for the pgvector backend")
            return PgVectorGenAIStore(session_factory=session_factory, embedder=embedder)

        case "sqlite" | "memory":
            from fireflyframework_genai.vectorstores import InMemoryVectorStore

            return InMemoryVectorStore(embedder=embedder)

        case "chromadb":
            from fireflyframework_genai.vectorstores import ChromaVectorStore

            return ChromaVectorStore(collection_name="flydesk", embedder=embedder)

        case "pinecone":
            from fireflyframework_genai.vectorstores import PineconeVectorStore

            return PineconeVectorStore(
                index_name=config.pinecone_index_name,
                api_key=config.pinecone_api_key or None,
                embedder=embedder,
            )

        case _:
            from fireflyframework_genai.vectorstores import InMemoryVectorStore

            return InMemoryVectorStore(embedder=embedder)
