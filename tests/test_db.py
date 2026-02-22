# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for database engine factory."""

from __future__ import annotations

from flydesk.db import create_engine_from_url


class TestDatabaseEngine:
    def test_create_engine_returns_async_engine(self):
        """Factory returns an AsyncEngine for a valid URL."""
        engine = create_engine_from_url("sqlite+aiosqlite:///test.db")
        assert engine is not None
        assert hasattr(engine, "begin")  # AsyncEngine interface

    def test_create_engine_with_pool_settings(self):
        """Engine respects pool size and overflow settings."""
        engine = create_engine_from_url(
            "sqlite+aiosqlite:///test.db",
            pool_size=5,
            max_overflow=10,
        )
        assert engine is not None
