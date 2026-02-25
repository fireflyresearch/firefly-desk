# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""User Management REST API -- user list, profile, and CRUD endpoints."""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.auth.local_user_repository import LocalUserRepository
from flydesk.auth.password import hash_password
from flydesk.models.audit import AuditEventRow
from flydesk.models.conversation import ConversationRow
from flydesk.rbac.guards import AdminUsers
from flydesk.config import get_config
from flydesk.settings.models import UserSettings
from flydesk.settings.repository import SettingsRepository

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


def get_local_user_repo() -> LocalUserRepository:
    """Provide a LocalUserRepository instance."""
    raise NotImplementedError(
        "get_local_user_repo must be overridden via app.dependency_overrides"
    )


SessionFactory = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]
SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]
LocalUserRepo = Annotated[LocalUserRepository, Depends(get_local_user_repo)]


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


class UpdateUserRolesRequest(BaseModel):
    """Request body for assigning roles to a user."""

    role_ids: list[str] = Field(default_factory=list)


class CreateUserRequest(BaseModel):
    """Request body for creating a new local user."""

    username: str
    email: str
    display_name: str
    password: str
    role: str = "user"


class UpdateUserRequest(BaseModel):
    """Request body for updating an existing local user."""

    email: str | None = None
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class ResetPasswordRequest(BaseModel):
    """Request body for resetting a user's password."""

    password: str


class LocalUserResponse(BaseModel):
    """Response schema for a local user (never exposes password_hash)."""

    id: str
    username: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: str
    updated_at: str
    last_login_at: str | None = None


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


def _row_to_response(row) -> LocalUserResponse:
    """Convert a LocalUserRow ORM instance to an API response."""
    return LocalUserResponse(
        id=row.id,
        username=row.username,
        email=row.email,
        display_name=row.display_name,
        role=row.role,
        is_active=row.is_active,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
        last_login_at=row.last_login_at.isoformat() if row.last_login_at else None,
    )


@router.get("/api/admin/users", dependencies=[AdminUsers])
async def list_users(
    session_factory: SessionFactory,
    local_user_repo: LocalUserRepo,
) -> list[UserSummary]:
    """List users by merging local_users with activity-derived users.

    Local users are always included. Activity-derived users (from conversations
    and audit events) that do not correspond to a local user are appended.
    In dev mode the synthetic dev user is included when no local users exist.
    """
    users: dict[str, UserSummary] = {}

    # 1. Include all local users
    try:
        local_users = await local_user_repo.get_all_users()
        for lu in local_users:
            users[lu.id] = UserSummary(
                user_id=lu.id,
                display_name=lu.display_name,
                email=lu.email,
                roles=[lu.role],
                last_active=lu.last_login_at.isoformat() if lu.last_login_at else (
                    lu.updated_at.isoformat() if lu.updated_at else None
                ),
            )
    except Exception:
        logger.debug("Failed to query local users.", exc_info=True)

    # 2. Show dev user when in dev mode and no local users
    config = get_config()
    if config.dev_mode and not users:
        users["dev-user-001"] = UserSummary(
            user_id="dev-user-001",
            display_name="Dev Admin",
            email="admin@localhost",
            roles=["admin"],
        )

    # 3. Merge activity-derived users
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
                if user_id in users:
                    users[user_id].conversation_count = row[1]
                    if row[2]:
                        activity_ts = row[2].isoformat()
                        if users[user_id].last_active is None or activity_ts > users[user_id].last_active:
                            users[user_id].last_active = activity_ts
                else:
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

    # Enrich with role assignments
    try:
        from flydesk.models.user_role import UserRoleRow

        async with session_factory() as session:
            result = await session.execute(
                select(UserRoleRow.user_id, UserRoleRow.role_id)
            )
            for row in result.all():
                uid, rid = row[0], row[1]
                if uid in users:
                    users[uid].roles.append(rid)
    except Exception:
        logger.debug("Failed to load role assignments", exc_info=True)

    return list(users.values())


@router.get("/api/admin/users/{user_id}/roles", dependencies=[AdminUsers])
async def get_user_roles(user_id: str, session_factory: SessionFactory) -> list[str]:
    """Get role IDs assigned to a user."""
    from flydesk.models.user_role import UserRoleRow

    async with session_factory() as session:
        result = await session.execute(
            select(UserRoleRow.role_id).where(UserRoleRow.user_id == user_id)
        )
        return [row[0] for row in result.all()]


@router.put("/api/admin/users/{user_id}/roles", dependencies=[AdminUsers])
async def update_user_roles(
    user_id: str, body: UpdateUserRolesRequest, session_factory: SessionFactory
) -> list[str]:
    """Replace all role assignments for a user."""
    from flydesk.models.user_role import UserRoleRow

    async with session_factory() as session:
        # Delete existing assignments
        await session.execute(
            delete(UserRoleRow).where(UserRoleRow.user_id == user_id)
        )
        # Insert new assignments
        for role_id in body.role_ids:
            session.add(UserRoleRow(
                id=str(uuid.uuid4()),
                user_id=user_id,
                role_id=role_id,
            ))
        await session.commit()

        # Return the updated role IDs
        result = await session.execute(
            select(UserRoleRow.role_id).where(UserRoleRow.user_id == user_id)
        )
        return [row[0] for row in result.all()]


# ---------------------------------------------------------------------------
# User CRUD endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/api/admin/users",
    dependencies=[AdminUsers],
    status_code=201,
)
async def create_user(
    body: CreateUserRequest,
    local_user_repo: LocalUserRepo,
) -> LocalUserResponse:
    """Create a new local user account."""
    # Check for duplicate username
    existing = await local_user_repo.get_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    hashed = hash_password(body.password)
    row = await local_user_repo.create_user(
        username=body.username,
        email=body.email,
        display_name=body.display_name,
        password_hash=hashed,
        role=body.role,
    )
    return _row_to_response(row)


@router.get("/api/admin/users/{user_id}", dependencies=[AdminUsers])
async def get_user(
    user_id: str,
    local_user_repo: LocalUserRepo,
) -> LocalUserResponse:
    """Get a local user by ID."""
    row = await local_user_repo.get_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_response(row)


@router.put("/api/admin/users/{user_id}", dependencies=[AdminUsers])
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    local_user_repo: LocalUserRepo,
) -> LocalUserResponse:
    """Update an existing local user's fields."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        # Nothing to update -- just return the current user
        row = await local_user_repo.get_by_id(user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return _row_to_response(row)

    row = await local_user_repo.update_user(user_id, **updates)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return _row_to_response(row)


@router.delete(
    "/api/admin/users/{user_id}",
    dependencies=[AdminUsers],
    status_code=204,
)
async def delete_user(
    user_id: str,
    local_user_repo: LocalUserRepo,
) -> Response:
    """Deactivate a local user (soft-delete)."""
    ok = await local_user_repo.deactivate_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return Response(status_code=204)


@router.post("/api/admin/users/{user_id}/reset-password", dependencies=[AdminUsers])
async def reset_password(
    user_id: str,
    body: ResetPasswordRequest,
    local_user_repo: LocalUserRepo,
) -> dict[str, str]:
    """Reset a local user's password."""
    hashed = hash_password(body.password)
    ok = await local_user_repo.update_password(user_id, hashed)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "Password updated"}


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
