"""Tests for RoutingConfigRepository."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.router.models import RoutingConfig


@pytest.fixture
def mock_session_factory():
    """Create a mock async session factory."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)

    factory = MagicMock(return_value=session)
    return factory, session


class TestRoutingConfigRepository:
    async def test_get_config_returns_none_when_empty(self, mock_session_factory):
        from flydesk.agent.router.config import RoutingConfigRepository

        factory, session = mock_session_factory
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        repo = RoutingConfigRepository(factory)
        config = await repo.get_config()
        assert config is None

    async def test_get_config_uses_cache(self, mock_session_factory):
        from flydesk.agent.router.config import RoutingConfigRepository

        factory, session = mock_session_factory
        repo = RoutingConfigRepository(factory, cache_ttl=60)

        # Manually set cache
        repo._cache = RoutingConfig(enabled=True, tier_mappings={"fast": "model:x"})
        repo._cache_time = time.monotonic()

        config = await repo.get_config()
        assert config is not None
        assert config.enabled is True
        # Should NOT have called the database
        session.execute.assert_not_called()

    async def test_cache_expires(self, mock_session_factory):
        from flydesk.agent.router.config import RoutingConfigRepository

        factory, session = mock_session_factory
        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        repo = RoutingConfigRepository(factory, cache_ttl=1)

        # Set cache that's already expired
        repo._cache = RoutingConfig(enabled=True)
        repo._cache_time = time.monotonic() - 2  # 2 seconds ago, TTL is 1

        config = await repo.get_config()
        # Should have hit DB since cache expired, and DB returns None
        assert config is None
        session.execute.assert_called_once()

    async def test_invalidate_cache(self, mock_session_factory):
        from flydesk.agent.router.config import RoutingConfigRepository

        factory, session = mock_session_factory
        repo = RoutingConfigRepository(factory)

        repo._cache = RoutingConfig(enabled=True)
        repo._cache_time = time.monotonic()

        repo.invalidate_cache()
        assert repo._cache is None
