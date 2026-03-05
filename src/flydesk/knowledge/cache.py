# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Database-backed knowledge cache with in-memory LRU."""

from __future__ import annotations

import json
import logging
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select

from flydesk.models.cache_entry import CacheEntryRow

logger = logging.getLogger(__name__)


class KnowledgeCache:
    """Two-tier cache: in-memory LRU backed by database storage.

    The in-memory layer provides fast access for hot items while the
    database ensures durability and cross-process visibility.

    Parameters
    ----------
    session_factory:
        An async SQLAlchemy session factory (``async_sessionmaker``).
    max_memory_items:
        Upper bound on in-memory entries.  When exceeded the least-recently
        used item is evicted from memory (it remains in the DB).
    """

    NAMESPACE_EMBEDDING = "embedding"
    NAMESPACE_RETRIEVAL = "retrieval"

    def __init__(self, session_factory: Any, *, max_memory_items: int = 500) -> None:
        self._session_factory = session_factory
        self._max_memory_items = max_memory_items
        # OrderedDict used as LRU: key = "{namespace}:{cache_key}",
        # value = (data, expires_at_timestamp)
        self._memory: OrderedDict[str, tuple[Any, float]] = OrderedDict()

    # ------------------------------------------------------------------
    # Public API -- Embeddings
    # ------------------------------------------------------------------

    async def get_embedding(self, text_hash: str) -> list[float] | None:
        """Look up a cached embedding vector by text hash."""
        return await self._get(self.NAMESPACE_EMBEDDING, text_hash)

    async def set_embedding(
        self, text_hash: str, embedding: list[float], ttl: int = 3600
    ) -> None:
        """Cache an embedding vector."""
        await self._set(self.NAMESPACE_EMBEDDING, text_hash, embedding, ttl)

    # ------------------------------------------------------------------
    # Public API -- Search results
    # ------------------------------------------------------------------

    async def get_retrieval(self, query_hash: str) -> list[dict] | None:
        """Look up cached search results by query hash."""
        return await self._get(self.NAMESPACE_RETRIEVAL, query_hash)

    async def set_retrieval(
        self, query_hash: str, results: list[dict], ttl: int = 300
    ) -> None:
        """Cache search results."""
        await self._set(self.NAMESPACE_RETRIEVAL, query_hash, results, ttl)

    # ------------------------------------------------------------------
    # Invalidation
    # ------------------------------------------------------------------

    async def invalidate_document(self, document_id: str) -> None:
        """Invalidate all cached search results.

        When a document changes, any cached result may be stale.
        Embeddings are per-chunk-hash and are unaffected.
        """
        prefix = f"{self.NAMESPACE_RETRIEVAL}:"

        # Clear from memory
        keys_to_remove = [k for k in self._memory if k.startswith(prefix)]
        for key in keys_to_remove:
            del self._memory[key]

        # Clear from DB
        try:
            async with self._session_factory() as session:
                stmt = delete(CacheEntryRow).where(
                    CacheEntryRow.namespace == self.NAMESPACE_RETRIEVAL
                )
                await session.execute(stmt)
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to invalidate cached results in DB for document %s",
                document_id,
            )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def cleanup_expired(self) -> int:
        """Remove expired entries from memory and database.

        Returns the number of database rows deleted.
        """
        now = datetime.now(timezone.utc).timestamp()

        # Evict expired entries from memory
        expired_keys = [
            k for k, (_, exp) in self._memory.items() if exp <= now
        ]
        for key in expired_keys:
            del self._memory[key]

        # Evict expired entries from database
        db_deleted = 0
        try:
            async with self._session_factory() as session:
                stmt = delete(CacheEntryRow).where(
                    CacheEntryRow.expires_at <= datetime.now(timezone.utc)
                )
                result = await session.execute(stmt)
                await session.commit()
                db_deleted = result.rowcount  # type: ignore[assignment]
        except Exception:
            logger.exception("Failed to cleanup expired cache entries in DB")

        return db_deleted

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get(self, namespace: str, key: str) -> Any | None:
        """Look up a value: memory first, then DB."""
        # 1. Check memory
        value = self._get_from_memory(namespace, key)
        if value is not None:
            return value

        # 2. Check database
        try:
            async with self._session_factory() as session:
                stmt = select(CacheEntryRow).where(
                    CacheEntryRow.namespace == namespace,
                    CacheEntryRow.cache_key == key,
                )
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row is None:
                    return None

                # Check expiry
                row_expires = row.expires_at
                if row_expires.tzinfo is None:
                    row_expires = row_expires.replace(tzinfo=timezone.utc)
                if row_expires <= datetime.now(timezone.utc):
                    return None

                data = json.loads(row.value_json)

                # Promote to memory
                self._store_in_memory(
                    namespace, key, data, row_expires.timestamp()
                )
                return data
        except Exception:
            logger.exception(
                "Failed to read cache entry from DB: %s:%s", namespace, key
            )
            return None

    async def _set(self, namespace: str, key: str, value: Any, ttl: int) -> None:
        """Store a value in both memory and database (upsert)."""
        now = datetime.now(timezone.utc)
        expires_at = now.timestamp() + ttl

        # Store in memory
        self._store_in_memory(namespace, key, value, expires_at)

        # Store in database (upsert)
        try:
            async with self._session_factory() as session:
                expires_dt = datetime.fromtimestamp(expires_at, tz=timezone.utc)
                mem_key = f"{namespace}:{key}"
                row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, mem_key))

                stmt = select(CacheEntryRow).where(
                    CacheEntryRow.namespace == namespace,
                    CacheEntryRow.cache_key == key,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()

                if existing is not None:
                    existing.value_json = json.dumps(value)
                    existing.expires_at = expires_dt
                    existing.created_at = now
                else:
                    session.add(
                        CacheEntryRow(
                            id=row_id,
                            namespace=namespace,
                            cache_key=key,
                            value_json=json.dumps(value),
                            expires_at=expires_dt,
                            created_at=now,
                        )
                    )
                await session.commit()
        except Exception:
            logger.exception(
                "Failed to write cache entry to DB: %s:%s", namespace, key
            )

    def _get_from_memory(self, namespace: str, key: str) -> Any | None:
        """Direct memory lookup.  Returns *None* on miss or expiry."""
        mem_key = f"{namespace}:{key}"
        entry = self._memory.get(mem_key)
        if entry is None:
            return None

        data, expires_at = entry
        if expires_at <= datetime.now(timezone.utc).timestamp():
            # Expired -- evict
            del self._memory[mem_key]
            return None

        # Move to end (most-recently used)
        self._memory.move_to_end(mem_key)
        return data

    def _store_in_memory(
        self, namespace: str, key: str, value: Any, expires_at: float
    ) -> None:
        """Insert/update a memory entry, evicting LRU if over capacity."""
        mem_key = f"{namespace}:{key}"

        if mem_key in self._memory:
            # Update existing -- move to end
            self._memory[mem_key] = (value, expires_at)
            self._memory.move_to_end(mem_key)
        else:
            # Evict oldest if at capacity
            while len(self._memory) >= self._max_memory_items:
                self._memory.popitem(last=False)
            self._memory[mem_key] = (value, expires_at)
