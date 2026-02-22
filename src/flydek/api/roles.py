# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Roles admin REST API -- CRUD for RBAC roles and permission listing."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from flydek.rbac.guards import AdminRoles
from flydek.rbac.models import Role
from flydek.rbac.permissions import Permission
from flydek.rbac.repository import RoleRepository

router = APIRouter(tags=["roles"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_role_repo() -> RoleRepository:
    """Provide a RoleRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_role_repo must be overridden via app.dependency_overrides"
    )


RoleRepo = Annotated[RoleRepository, Depends(get_role_repo)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateRoleRequest(BaseModel):
    """Body for POST /api/admin/roles."""

    name: str
    display_name: str
    description: str = ""
    permissions: list[str] = Field(default_factory=list)


class UpdateRoleRequest(BaseModel):
    """Body for PUT /api/admin/roles/{role_id}."""

    display_name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None


class PermissionInfo(BaseModel):
    """A single permission entry with its description."""

    value: str
    name: str
    resource: str
    action: str


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminRoles
# ---------------------------------------------------------------------------


@router.get("/api/admin/roles", dependencies=[AdminRoles])
async def list_roles(repo: RoleRepo) -> list[dict]:
    """List all roles."""
    roles = await repo.list_roles()
    return [_role_to_dict(r) for r in roles]


@router.post("/api/admin/roles", status_code=201, dependencies=[AdminRoles])
async def create_role(body: CreateRoleRequest, repo: RoleRepo) -> dict:
    """Create a custom role."""
    # Check for duplicate name
    existing = await repo.get_role_by_name(body.name)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Role with name '{body.name}' already exists",
        )

    role = Role(
        id=f"role-{uuid.uuid4().hex[:12]}",
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        permissions=body.permissions,
        is_builtin=False,
    )
    created = await repo.create_role(role)
    return _role_to_dict(created)


@router.get("/api/admin/roles/{role_id}", dependencies=[AdminRoles])
async def get_role(role_id: str, repo: RoleRepo) -> dict:
    """Get role details."""
    role = await repo.get_role(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found")
    return _role_to_dict(role)


@router.put("/api/admin/roles/{role_id}", dependencies=[AdminRoles])
async def update_role(role_id: str, body: UpdateRoleRequest, repo: RoleRepo) -> dict:
    """Update role permissions, display_name, or description."""
    # Build kwargs from non-None fields
    kwargs: dict = {}
    if body.display_name is not None:
        kwargs["display_name"] = body.display_name
    if body.description is not None:
        kwargs["description"] = body.description
    if body.permissions is not None:
        kwargs["permissions"] = body.permissions

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await repo.update_role(role_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found")
    return _role_to_dict(updated)


@router.delete("/api/admin/roles/{role_id}", status_code=204, dependencies=[AdminRoles])
async def delete_role(role_id: str, repo: RoleRepo) -> Response:
    """Delete a custom role. Refuses to delete built-in roles."""
    try:
        deleted = await repo.delete_role(role_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Role '{role_id}' not found")
    return Response(status_code=204)


@router.get("/api/admin/permissions", dependencies=[AdminRoles])
async def list_permissions() -> list[dict]:
    """List all available permission strings with descriptions."""
    result: list[dict] = []
    for perm in Permission:
        resource, action = perm.value.split(":", 1)
        result.append({
            "value": perm.value,
            "name": perm.name,
            "resource": resource,
            "action": action,
        })
    return result


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _role_to_dict(role: Role) -> dict:
    return {
        "id": role.id,
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "permissions": role.permissions,
        "is_builtin": role.is_builtin,
        "created_at": role.created_at.isoformat() if role.created_at else None,
        "updated_at": role.updated_at.isoformat() if role.updated_at else None,
    }
