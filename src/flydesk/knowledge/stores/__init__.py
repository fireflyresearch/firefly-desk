# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Vector store factory -- instantiates the configured backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flydesk.knowledge.vector_store import VectorStore

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from flydesk.config import DeskConfig


def create_vector_store(
    config: DeskConfig,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> VectorStore:
    """Create a :class:`VectorStore` instance based on *config.vector_store*.

    The *session_factory* is required for the ``pgvector`` and ``sqlite``
    backends.  External backends (``chromadb``, ``pinecone``) ignore it.
    """
    match config.vector_store:
        case "pgvector":
            from flydesk.knowledge.stores.pgvector_store import PgVectorStore

            if session_factory is None:
                raise ValueError("session_factory is required for the pgvector backend")
            return PgVectorStore(session_factory)

        case "sqlite":
            from flydesk.knowledge.stores.sqlite_store import SqliteVectorStore

            if session_factory is None:
                raise ValueError("session_factory is required for the sqlite backend")
            return SqliteVectorStore(session_factory)

        case "chromadb":
            from flydesk.knowledge.stores.chroma_store import ChromaDBStore

            return ChromaDBStore(
                path=config.chroma_path or None,
                url=config.chroma_url or None,
            )

        case "pinecone":
            from flydesk.knowledge.stores.pinecone_store import PineconeStore

            return PineconeStore(
                api_key=config.pinecone_api_key,
                index_name=config.pinecone_index_name,
                environment=config.pinecone_environment or None,
            )

        case _:
            raise ValueError(f"Unknown vector_store backend: {config.vector_store!r}")
