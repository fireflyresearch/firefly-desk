# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Workspaces REST API -- CRUD for workspace organization."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response

from flydesk.api.deps import get_workspace_repo
from flydesk.rbac.guards import require_permission
from flydesk.workspaces.models import CreateWorkspace, UpdateWorkspace, Workspace
from flydesk.workspaces.repository import WorkspaceRepository

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

AdminOnly = require_permission("*")

Repo = Annotated[WorkspaceRepository, Depends(get_workspace_repo)]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminOnly])
async def list_workspaces(repo: Repo) -> list[Workspace]:
    """Return every workspace."""
    return await repo.list_all()


@router.post("", status_code=201, dependencies=[AdminOnly])
async def create_workspace(body: CreateWorkspace, repo: Repo) -> Workspace:
    """Create a new workspace."""
    return await repo.create(body)


@router.get("/{workspace_id}", dependencies=[AdminOnly])
async def get_workspace(workspace_id: str, repo: Repo) -> Workspace:
    """Retrieve a single workspace by ID."""
    workspace = await repo.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return workspace


@router.put("/{workspace_id}", dependencies=[AdminOnly])
async def update_workspace(workspace_id: str, body: UpdateWorkspace, repo: Repo) -> Workspace:
    """Update an existing workspace."""
    existing = await repo.get(workspace_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    if existing.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify a system workspace")
    workspace = await repo.update(workspace_id, body)
    if workspace is None:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    return workspace


@router.delete("/{workspace_id}", status_code=204, dependencies=[AdminOnly])
async def delete_workspace(workspace_id: str, repo: Repo) -> Response:
    """Remove a workspace."""
    existing = await repo.get(workspace_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Workspace {workspace_id} not found")
    if existing.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete a system workspace")
    await repo.delete(workspace_id)
    return Response(status_code=204)
