# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Database engine factory and session management."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine_from_url(
    url: str,
    *,
    pool_size: int = 10,
    max_overflow: int = 20,
    echo: bool = False,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine.

    Args:
        url: Database connection URL (must use an async driver).
        pool_size: Maximum number of permanent connections.
        max_overflow: Maximum number of overflow connections beyond pool_size.
        echo: If True, log all SQL statements.

    Returns:
        An :class:`~sqlalchemy.ext.asyncio.AsyncEngine` instance.
    """
    # SQLite doesn't support pool settings
    kwargs: dict = {"echo": echo}
    if "sqlite" not in url:
        kwargs["pool_size"] = pool_size
        kwargs["max_overflow"] = max_overflow
    return create_async_engine(url, **kwargs)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create a session factory bound to the given engine.

    Args:
        engine: The async engine to bind sessions to.

    Returns:
        An :class:`~sqlalchemy.ext.asyncio.async_sessionmaker` instance.
    """
    return async_sessionmaker(engine, expire_on_commit=False)
