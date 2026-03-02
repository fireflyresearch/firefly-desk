"""Repository for model routing configuration with in-memory cache."""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

from sqlalchemy import select

from flydesk.agent.router.models import RoutingConfig
from flydesk.models.routing import ModelRoutingConfigRow

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = logging.getLogger(__name__)

_DEFAULT_CACHE_TTL = 60  # seconds


class RoutingConfigRepository:
    """Database-backed routing configuration with in-memory cache."""

    def __init__(
        self,
        session_factory: Callable,
        cache_ttl: int = _DEFAULT_CACHE_TTL,
    ) -> None:
        self._session_factory = session_factory
        self._cache_ttl = cache_ttl
        self._cache: RoutingConfig | None = None
        self._cache_time: float = 0.0

    def invalidate_cache(self) -> None:
        """Force cache invalidation."""
        self._cache = None
        self._cache_time = 0.0

    async def get_config(self) -> RoutingConfig | None:
        """Return the current routing config, using cache when fresh."""
        if self._cache is not None and (time.monotonic() - self._cache_time) < self._cache_ttl:
            return self._cache

        try:
            async with self._session_factory() as session:
                stmt = select(ModelRoutingConfigRow).where(
                    ModelRoutingConfigRow.id == "default",
                )
                row = (await session.execute(stmt)).scalar_one_or_none()
                if row is None:
                    self._cache = None
                    self._cache_time = time.monotonic()
                    return None

                tier_mappings = row.tier_mappings
                if isinstance(tier_mappings, str):
                    tier_mappings = json.loads(tier_mappings)

                config = RoutingConfig(
                    enabled=row.enabled,
                    classifier_model=row.classifier_model,
                    default_tier=row.default_tier,
                    tier_mappings=tier_mappings or {},
                    updated_at=row.updated_at,
                )
                self._cache = config
                self._cache_time = time.monotonic()
                return config
        except Exception:
            _logger.debug("Failed to load routing config.", exc_info=True)
            return self._cache  # Return stale cache on DB error

    async def update_config(self, config: RoutingConfig) -> RoutingConfig:
        """Persist routing config and invalidate cache."""
        from datetime import datetime, timezone

        async with self._session_factory() as session:
            stmt = select(ModelRoutingConfigRow).where(
                ModelRoutingConfigRow.id == "default",
            )
            row = (await session.execute(stmt)).scalar_one_or_none()

            if row is None:
                row = ModelRoutingConfigRow(id="default")
                session.add(row)

            row.enabled = config.enabled
            row.classifier_model = config.classifier_model
            row.default_tier = config.default_tier
            row.tier_mappings = config.tier_mappings
            row.updated_at = datetime.now(timezone.utc)

            await session.commit()

        self.invalidate_cache()
        return await self.get_config() or config
