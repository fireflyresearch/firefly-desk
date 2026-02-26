# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Async repository for user memories."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.memory.models import CreateMemory, UpdateMemory, UserMemory
from flydesk.models.user_memory import UserMemoryRow


class MemoryRepository:
    """CRUD operations for user memories, all scoped by user_id."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def _row_to_model(self, row: UserMemoryRow) -> UserMemory:
        return UserMemory(
            id=row.id,
            user_id=row.user_id,
            content=row.content,
            category=row.category,
            source=row.source,
            metadata=row.metadata_,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def create(self, user_id: str, data: CreateMemory) -> UserMemory:
        row = UserMemoryRow(
            id=str(uuid.uuid4()),
            user_id=user_id,
            content=data.content,
            category=data.category,
            source=data.source,
            metadata_=data.metadata,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_model(row)

    async def get(self, user_id: str, memory_id: str) -> UserMemory | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserMemoryRow).where(
                    UserMemoryRow.id == memory_id,
                    UserMemoryRow.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            return self._row_to_model(row) if row else None

    async def list_for_user(
        self, user_id: str, *, category: str | None = None
    ) -> list[UserMemory]:
        async with self._session_factory() as session:
            stmt = select(UserMemoryRow).where(UserMemoryRow.user_id == user_id)
            if category:
                stmt = stmt.where(UserMemoryRow.category == category)
            stmt = stmt.order_by(UserMemoryRow.created_at.desc())
            result = await session.execute(stmt)
            return [self._row_to_model(r) for r in result.scalars().all()]

    async def update(
        self, user_id: str, memory_id: str, data: UpdateMemory
    ) -> UserMemory | None:
        async with self._session_factory() as session:
            result = await session.execute(
                select(UserMemoryRow).where(
                    UserMemoryRow.id == memory_id,
                    UserMemoryRow.user_id == user_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            if data.content is not None:
                row.content = data.content
            if data.category is not None:
                row.category = data.category
            await session.commit()
            await session.refresh(row)
            return self._row_to_model(row)

    async def delete(self, user_id: str, memory_id: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                delete(UserMemoryRow).where(
                    UserMemoryRow.id == memory_id,
                    UserMemoryRow.user_id == user_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def search(self, user_id: str, query: str) -> list[UserMemory]:
        """Word-level text search in memory content.

        Extracts words of 3+ characters from the query and OR-matches
        them against memory content.  At most 5 keywords are used.
        """
        from sqlalchemy import or_

        words = [w for w in query.lower().split() if len(w) >= 3]
        if not words:
            return []
        words = words[:5]

        async with self._session_factory() as session:
            conditions = [
                UserMemoryRow.content.ilike(f"%{word}%") for word in words
            ]
            stmt = (
                select(UserMemoryRow)
                .where(
                    UserMemoryRow.user_id == user_id,
                    or_(*conditions),
                )
                .order_by(UserMemoryRow.created_at.desc())
                .limit(10)
            )
            result = await session.execute(stmt)
            return [self._row_to_model(r) for r in result.scalars().all()]
