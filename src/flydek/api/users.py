# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""User Management REST API -- user list and profile endpoints."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydek.models.audit import AuditEventRow
from flydek.models.conversation import ConversationRow
from flydek.rbac.guards import AdminUsers
from flydek.config import get_config
from flydek.settings.models import UserSettings
from flydek.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["users"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Provide the database session factory."""
    raise NotImplementedError(
        "get_session_factory must be overridden via app.dependency_overrides"
    )


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance."""
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserSummary(BaseModel):
    """Summary of a user derived from activity logs."""

    user_id: str
    display_name: str | None = None
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
    conversation_count: int = 0
    last_active: str | None = None


class UserProfile(BaseModel):
    """Current user's profile information."""

    user_id: str
    email: str
    display_name: str
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    picture_url: str | None = None
    department: str | None = None
    title: str | None = None
    dev_mode: bool = False


class UpdatePreferencesRequest(BaseModel):
    """Request body for updating user preferences."""

    theme: str | None = None
    language: str | None = None
    default_model: str | None = None
    notifications_enabled: bool | None = None


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@router.get("/api/admin/users", dependencies=[AdminUsers])
async def list_users(session_factory: SessionFactory) -> list[UserSummary]:
    """List users derived from conversation and audit activity.

    In dev mode, users are gathered from distinct user_ids in conversations
    and audit events since there is no dedicated user table.
    """
    users: dict[str, UserSummary] = {}

    try:
        async with session_factory() as session:
            # Gather distinct user_ids from conversations
            result = await session.execute(
                select(
                    ConversationRow.user_id,
                    func.count(ConversationRow.id).label("conv_count"),
                    func.max(ConversationRow.updated_at).label("last_active"),
                ).group_by(ConversationRow.user_id)
            )
            for row in result.all():
                user_id = row[0]
                users[user_id] = UserSummary(
                    user_id=user_id,
                    conversation_count=row[1],
                    last_active=row[2].isoformat() if row[2] else None,
                )

            # Gather distinct user_ids from audit events
            result = await session.execute(
                select(
                    AuditEventRow.user_id,
                    func.max(AuditEventRow.created_at).label("last_active"),
                ).group_by(AuditEventRow.user_id)
            )
            for row in result.all():
                user_id = row[0]
                if user_id not in users:
                    users[user_id] = UserSummary(
                        user_id=user_id,
                        last_active=row[1].isoformat() if row[1] else None,
                    )
                elif row[1]:
                    # Update last_active if audit event is more recent
                    existing_last = users[user_id].last_active
                    audit_last = row[1].isoformat()
                    if existing_last is None or audit_last > existing_last:
                        users[user_id].last_active = audit_last
    except Exception:
        logger.debug("Failed to query users from database.", exc_info=True)

    return list(users.values())


# ---------------------------------------------------------------------------
# Profile endpoints (any authenticated user)
# ---------------------------------------------------------------------------


@router.get("/api/profile")
async def get_profile(request: Request) -> UserProfile:
    """Return the current user's profile information."""
    user_session = getattr(request.state, "user_session", None)
    if user_session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return UserProfile(
        user_id=user_session.user_id,
        email=user_session.email,
        display_name=user_session.display_name,
        roles=user_session.roles,
        permissions=user_session.permissions,
        picture_url=user_session.picture_url,
        department=user_session.department,
        title=user_session.title,
        dev_mode=get_config().dev_mode,
    )


@router.put("/api/profile/preferences")
async def update_preferences(
    request: Request,
    body: UpdatePreferencesRequest,
    settings_repo: SettingsRepo,
) -> UserSettings:
    """Update the current user's preferences."""
    user_session = getattr(request.state, "user_session", None)
    if user_session is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Get existing settings
    current = await settings_repo.get_user_settings(user_session.user_id)

    # Merge only provided fields
    updates = body.model_dump(exclude_none=True)
    settings_data = current.model_dump()
    settings_data.update(updates)
    updated_settings = UserSettings(**settings_data)

    await settings_repo.update_user_settings(user_session.user_id, updated_settings)
    return updated_settings
