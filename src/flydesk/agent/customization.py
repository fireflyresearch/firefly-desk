# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Agent customization: profile model and service for loading agent identity from DB settings."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from flydesk.settings.repository import SettingsRepository

_logger = logging.getLogger(__name__)


class AgentProfile(BaseModel):
    """Fully resolved agent identity used at runtime.

    This model combines database-stored :class:`AgentSettings` with
    any environment-level overrides.  The prompt builder and API
    endpoints consume this rather than raw settings.
    """

    name: str = "Ember"
    display_name: str = "Ember"
    avatar_url: str = ""
    personality: str = "warm, professional, knowledgeable"
    tone: str = "friendly yet precise"
    greeting: str = "Hello! I'm {name}, your intelligent assistant."
    behavior_rules: list[str] = []
    custom_instructions: str = ""
    language: str = "en"


# Default Ember profile -- used when no DB settings exist.
_EMBER_DEFAULTS = AgentProfile()


class AgentCustomizationService:
    """Loads and caches the active :class:`AgentProfile` from the settings DB.

    Falls back to Ember defaults when no agent settings have been persisted.
    """

    def __init__(self, settings_repo: SettingsRepository) -> None:
        self._settings_repo = settings_repo
        self._cached_profile: AgentProfile | None = None

    async def get_profile(self) -> AgentProfile:
        """Return the current agent profile, loading from DB if not cached."""
        if self._cached_profile is not None:
            return self._cached_profile

        try:
            settings = await self._settings_repo.get_agent_settings()
            self._cached_profile = AgentProfile(
                name=settings.name,
                display_name=settings.display_name,
                avatar_url=settings.avatar_url,
                personality=settings.personality,
                tone=settings.tone,
                greeting=settings.greeting,
                behavior_rules=settings.behavior_rules,
                custom_instructions=settings.custom_instructions,
                language=settings.language,
            )
        except Exception:
            _logger.warning(
                "Failed to load agent settings from DB; using Ember defaults.",
                exc_info=True,
            )
            self._cached_profile = _EMBER_DEFAULTS

        return self._cached_profile

    async def update_profile(self, profile: AgentProfile) -> AgentProfile:
        """Persist an updated profile and invalidate the cache."""
        from flydesk.settings.models import AgentSettings

        settings = AgentSettings(
            name=profile.name,
            display_name=profile.display_name,
            avatar_url=profile.avatar_url,
            personality=profile.personality,
            tone=profile.tone,
            greeting=profile.greeting,
            behavior_rules=profile.behavior_rules,
            custom_instructions=profile.custom_instructions,
            language=profile.language,
        )
        await self._settings_repo.set_agent_settings(settings)
        self._cached_profile = profile
        return profile

    def invalidate_cache(self) -> None:
        """Clear the cached profile so the next ``get_profile()`` re-reads from DB."""
        self._cached_profile = None
