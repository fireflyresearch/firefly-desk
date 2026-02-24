# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Custom tools admin REST API -- CRUD and test-execute for custom tool definitions."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from flydesk.rbac.guards import AdminSettings
from flydesk.tools.custom_models import CustomTool, ToolSource
from flydesk.tools.custom_repository import CustomToolRepository
from flydesk.tools.sandbox import SandboxExecutor

router = APIRouter(tags=["custom-tools"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_custom_tool_repo() -> CustomToolRepository:
    """Provide a CustomToolRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_custom_tool_repo must be overridden via app.dependency_overrides"
    )


def get_sandbox_executor() -> SandboxExecutor:
    """Provide a SandboxExecutor instance.

    In production this is wired in server.py.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_sandbox_executor must be overridden via app.dependency_overrides"
    )


CustomToolRepo = Annotated[CustomToolRepository, Depends(get_custom_tool_repo)]
Sandbox = Annotated[SandboxExecutor, Depends(get_sandbox_executor)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateCustomToolRequest(BaseModel):
    """Body for POST /api/admin/custom-tools."""

    name: str
    description: str = ""
    python_code: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    source: ToolSource = ToolSource.MANUAL
    timeout_seconds: int = 30
    max_memory_mb: int = 256


class UpdateCustomToolRequest(BaseModel):
    """Body for PUT /api/admin/custom-tools/{tool_id}."""

    name: str | None = None
    description: str | None = None
    python_code: str | None = None
    parameters: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    active: bool | None = None
    timeout_seconds: int | None = None
    max_memory_mb: int | None = None


class TestExecuteRequest(BaseModel):
    """Body for POST /api/admin/custom-tools/{tool_id}/test."""

    params: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSettings
# ---------------------------------------------------------------------------


@router.get("/api/admin/custom-tools", dependencies=[AdminSettings])
async def list_custom_tools(
    repo: CustomToolRepo,
    source: ToolSource | None = Query(None, description="Filter by tool source"),
) -> list[dict]:
    """List all custom tools, optionally filtered by source."""
    tools = await repo.list(source=source)
    return [_tool_to_dict(t) for t in tools]


@router.post("/api/admin/custom-tools", status_code=201, dependencies=[AdminSettings])
async def create_custom_tool(body: CreateCustomToolRequest, repo: CustomToolRepo) -> dict:
    """Create a new custom tool."""
    tool = CustomTool(
        id=f"ctool-{uuid.uuid4().hex[:12]}",
        name=body.name,
        description=body.description,
        python_code=body.python_code,
        parameters=body.parameters,
        output_schema=body.output_schema,
        active=body.active,
        source=body.source,
        timeout_seconds=body.timeout_seconds,
        max_memory_mb=body.max_memory_mb,
    )
    created = await repo.create(tool)
    return _tool_to_dict(created)


@router.get("/api/admin/custom-tools/{tool_id}", dependencies=[AdminSettings])
async def get_custom_tool(tool_id: str, repo: CustomToolRepo) -> dict:
    """Get custom tool details."""
    tool = await repo.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")
    return _tool_to_dict(tool)


@router.put("/api/admin/custom-tools/{tool_id}", dependencies=[AdminSettings])
async def update_custom_tool(
    tool_id: str, body: UpdateCustomToolRequest, repo: CustomToolRepo,
) -> dict:
    """Update a custom tool."""
    existing = await repo.get(tool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")

    kwargs: dict[str, Any] = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description
    if body.python_code is not None:
        kwargs["python_code"] = body.python_code
    if body.parameters is not None:
        kwargs["parameters"] = body.parameters
    if body.output_schema is not None:
        kwargs["output_schema"] = body.output_schema
    if body.active is not None:
        kwargs["active"] = body.active
    if body.timeout_seconds is not None:
        kwargs["timeout_seconds"] = body.timeout_seconds
    if body.max_memory_mb is not None:
        kwargs["max_memory_mb"] = body.max_memory_mb

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Apply updates to the existing model
    updated_tool = existing.model_copy(update=kwargs)
    updated = await repo.update(updated_tool)
    return _tool_to_dict(updated)


@router.delete("/api/admin/custom-tools/{tool_id}", status_code=204, dependencies=[AdminSettings])
async def delete_custom_tool(tool_id: str, repo: CustomToolRepo) -> Response:
    """Delete a custom tool. Builtin tools cannot be deleted."""
    existing = await repo.get(tool_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")
    if existing.source == ToolSource.BUILTIN:
        raise HTTPException(status_code=403, detail="Built-in tools cannot be deleted")
    deleted = await repo.delete(tool_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")
    return Response(status_code=204)


@router.post("/api/admin/custom-tools/{tool_id}/test", dependencies=[AdminSettings])
async def test_execute_custom_tool(
    tool_id: str,
    body: TestExecuteRequest,
    repo: CustomToolRepo,
    sandbox: Sandbox,
) -> dict:
    """Test-execute a custom tool with sample parameters."""
    tool = await repo.get(tool_id)
    if tool is None:
        raise HTTPException(status_code=404, detail=f"Custom tool '{tool_id}' not found")

    result = await sandbox.execute(
        tool.python_code, body.params, timeout=tool.timeout_seconds,
    )
    return {
        "success": result.success,
        "data": result.data,
        "error": result.error,
    }


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _tool_to_dict(tool: CustomTool) -> dict:
    return {
        "id": tool.id,
        "name": tool.name,
        "description": tool.description,
        "python_code": tool.python_code,
        "parameters": tool.parameters,
        "output_schema": tool.output_schema,
        "active": tool.active,
        "source": tool.source.value,
        "timeout_seconds": tool.timeout_seconds,
        "max_memory_mb": tool.max_memory_mb,
        "created_by": tool.created_by,
        "created_at": tool.created_at.isoformat() if tool.created_at else None,
        "updated_at": tool.updated_at.isoformat() if tool.updated_at else None,
    }
