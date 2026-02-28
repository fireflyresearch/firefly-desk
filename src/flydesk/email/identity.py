# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Resolve email addresses to Firefly Desk users."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)


@dataclass
class ResolvedIdentity:
    """Result of resolving an email address to a user account."""

    user_id: str
    email: str
    display_name: str | None = None
    is_external: bool = False


class EmailIdentityResolver:
    """Maps email addresses to Firefly Desk user accounts."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def resolve(self, email_address: str) -> ResolvedIdentity | None:
        """Look up a user by email address.

        Returns None if no matching user is found.
        """
        from flydesk.models.local_user import LocalUserRow

        async with self._session_factory() as session:
            stmt = select(LocalUserRow).where(LocalUserRow.email == email_address)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return ResolvedIdentity(
                user_id=row.id,
                email=row.email,
                display_name=getattr(row, "display_name", None),
            )
