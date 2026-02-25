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

    async def get_all_users(self, offset: int = 0, limit: int = 100) -> list[LocalUserRow]:
        """Return a paginated list of all local users ordered by creation date."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(LocalUserRow)
                .offset(offset)
                .limit(limit)
                .order_by(LocalUserRow.created_at.desc())
            )
            return list(result.scalars().all())

    async def update_user(self, user_id: str, **kwargs: object) -> LocalUserRow | None:
        """Update user fields by ID. Returns the updated row or None if not found."""
        async with self._session_factory() as session:
            user = await session.get(LocalUserRow, user_id)
            if not user:
                return None
            for key, value in kwargs.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)
            await session.commit()
            await session.refresh(user)
            return user

    async def deactivate_user(self, user_id: str) -> bool:
        """Set a user's is_active flag to False. Returns True if the user existed."""
        async with self._session_factory() as session:
            user = await session.get(LocalUserRow, user_id)
            if not user:
                return False
            user.is_active = False
            await session.commit()
            return True

    async def update_password(self, user_id: str, password_hash: str) -> bool:
        """Replace a user's password hash. Returns True if the user existed."""
        async with self._session_factory() as session:
            user = await session.get(LocalUserRow, user_id)
            if not user:
                return False
            user.password_hash = password_hash
            await session.commit()
            return True
