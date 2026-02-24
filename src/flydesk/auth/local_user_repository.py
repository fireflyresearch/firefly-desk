# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for local user accounts."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.local_user import LocalUserRow


class LocalUserRepository:
    """CRUD operations for local user accounts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_user(
        self,
        *,
        username: str,
        email: str,
        display_name: str,
        password_hash: str,
        role: str = "admin",
    ) -> LocalUserRow:
        """Persist a new local user."""
        row = LocalUserRow(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            display_name=display_name,
            password_hash=password_hash,
            role=role,
        )
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return row

    async def get_by_username(self, username: str) -> LocalUserRow | None:
        """Retrieve a local user by username."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LocalUserRow).where(LocalUserRow.username == username)
            )
            return result.scalars().first()

    async def get_by_email(self, email: str) -> LocalUserRow | None:
        """Retrieve a local user by email address (case-insensitive)."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LocalUserRow).where(
                    func.lower(LocalUserRow.email) == email.lower()
                )
            )
            return result.scalars().first()

    async def get_by_id(self, user_id: str) -> LocalUserRow | None:
        """Retrieve a local user by ID."""
        async with self._session_factory() as session:
            return await session.get(LocalUserRow, user_id)

    async def has_any_user(self) -> bool:
        """Return True if at least one local user exists."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(LocalUserRow)
            )
            return (result.scalar() or 0) > 0

    async def count_users(self) -> int:
        """Return the total number of local users."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).select_from(LocalUserRow)
            )
            return result.scalar() or 0
