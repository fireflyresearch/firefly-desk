# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Settings REST API -- user preferences and app-wide configuration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from flydesk.rbac.guards import AdminSettings
from flydesk.settings.models import UserSettings
from flydesk.settings.repository import SettingsRepository

router = APIRouter(prefix="/api/settings", tags=["settings"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# User Settings
# ---------------------------------------------------------------------------


@router.get("/user")
async def get_user_settings(request: Request, repo: Repo) -> UserSettings:
    """Return the current user's settings (defaults if none saved)."""
    user = getattr(request.state, "user_session", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await repo.get_user_settings(user.user_id)


@router.put("/user")
async def update_user_settings(
    request: Request, settings: UserSettings, repo: Repo
) -> UserSettings:
    """Update the current user's settings."""
    user = getattr(request.state, "user_session", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    await repo.update_user_settings(user.user_id, settings)
    return settings


# ---------------------------------------------------------------------------
# App Settings (admin only)
# ---------------------------------------------------------------------------


@router.get("/app", dependencies=[AdminSettings])
async def get_app_settings(repo: Repo) -> dict[str, str]:
    """Return all application-wide settings."""
    return await repo.get_all_app_settings()


@router.put("/app", dependencies=[AdminSettings])
async def update_app_settings(
    settings: dict[str, str], repo: Repo
) -> dict[str, str]:
    """Update application-wide settings (key-value pairs)."""
    for key, value in settings.items():
        await repo.set_app_setting(key, value)
    return settings
