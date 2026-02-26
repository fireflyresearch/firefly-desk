# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Catalog Admin REST API -- CRUD for systems and endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from flydesk.api.deps import get_auto_trigger, get_catalog_repo
from flydesk.catalog.enums import VALID_TRANSITIONS, SystemStatus
from flydesk.catalog.models import ExternalSystem, ServiceEndpoint
from flydesk.catalog.repository import CatalogRepository
from flydesk.rbac.guards import CatalogDelete, CatalogRead, CatalogWrite
from flydesk.triggers.auto_trigger import AutoTriggerService

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Repo = Annotated[CatalogRepository, Depends(get_catalog_repo)]
Trigger = Annotated[AutoTriggerService | None, Depends(get_auto_trigger)]


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------


@router.post("/systems", status_code=201, dependencies=[CatalogWrite])
async def create_system(
    system: ExternalSystem, repo: Repo, trigger: Trigger
) -> ExternalSystem:
    """Register a new external system."""
    await repo.create_system(system)
    if trigger is not None:
        await trigger.on_catalog_updated(system.id)
    return system


@router.get("/systems", dependencies=[CatalogRead])
async def list_systems(
    repo: Repo,
    workspace_id: str | None = Query(default=None),
    status: str | None = Query(default=None, description="Filter by status"),
    search: str | None = Query(default=None, description="Search by name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Return external systems with optional filters and pagination."""
    status_enum = None
    if status is not None:
        try:
            status_enum = SystemStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'")

    systems, total = await repo.list_systems(
        workspace_id=workspace_id,
        status=status_enum,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"items": [s.model_dump() for s in systems], "total": total}


class BulkDeleteRequest(BaseModel):
    ids: list[str]


class BulkStatusRequest(BaseModel):
    ids: list[str]
    status: str


@router.post("/systems/bulk-delete", dependencies=[CatalogDelete])
async def bulk_delete_systems(body: BulkDeleteRequest, repo: Repo) -> dict:
    """Delete multiple systems by ID."""
    deleted = await repo.bulk_delete_systems(body.ids)
    return {"deleted": deleted}


@router.post("/systems/bulk-status", dependencies=[CatalogWrite])
async def bulk_update_status(body: BulkStatusRequest, repo: Repo) -> dict:
    """Update status for multiple systems."""
    try:
        target = SystemStatus(body.status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status '{body.status}'")
    updated = await repo.bulk_update_status(body.ids, target)
    return {"updated": updated}


@router.get("/systems/{system_id}", dependencies=[CatalogRead])
async def get_system(system_id: str, repo: Repo) -> ExternalSystem:
    """Retrieve a single external system by ID."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    return system


@router.put("/systems/{system_id}", dependencies=[CatalogWrite])
async def update_system(
    system_id: str, system: ExternalSystem, repo: Repo, trigger: Trigger
) -> ExternalSystem:
    """Update an existing external system."""
    existing = await repo.get_system(system_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.update_system(system)
    if trigger is not None:
        await trigger.on_catalog_updated(system.id)
    return system


@router.delete("/systems/{system_id}", status_code=204, dependencies=[CatalogDelete])
async def delete_system(system_id: str, repo: Repo) -> Response:
    """Remove an external system."""
    existing = await repo.get_system(system_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.delete_system(system_id)
    return Response(status_code=204)


class StatusTransitionRequest(BaseModel):
    status: str


@router.put("/systems/{system_id}/status", dependencies=[CatalogWrite])
async def update_system_status(
    system_id: str, body: StatusTransitionRequest, repo: Repo
) -> dict:
    """Transition a system's status according to the state machine."""
    try:
        target = SystemStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"Invalid status '{body.status}'"
        )

    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")

    current = system.status
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from '{current}' to '{target}'. "
            f"Allowed: {', '.join(sorted(allowed)) or 'none (terminal state)'}",
        )

    updated = system.model_copy(update={"status": target})
    await repo.update_system(updated)
    return {
        "id": updated.id,
        "name": updated.name,
        "status": updated.status.value,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/systems/{system_id}/endpoints", status_code=201, dependencies=[CatalogWrite]
)
async def create_endpoint(
    system_id: str, endpoint: ServiceEndpoint, repo: Repo, trigger: Trigger
) -> ServiceEndpoint:
    """Add an endpoint to an existing system."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.create_endpoint(endpoint)
    if trigger is not None:
        await trigger.on_catalog_updated(system_id)
    return endpoint


@router.get("/systems/{system_id}/endpoints", dependencies=[CatalogRead])
async def list_endpoints(system_id: str, repo: Repo) -> list[ServiceEndpoint]:
    """List all endpoints belonging to a system."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    return await repo.list_endpoints(system_id)


@router.get("/endpoints/{endpoint_id}", dependencies=[CatalogRead])
async def get_endpoint(endpoint_id: str, repo: Repo) -> ServiceEndpoint:
    """Retrieve a single endpoint by ID."""
    endpoint = await repo.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint {endpoint_id} not found"
        )
    return endpoint


@router.put("/endpoints/{endpoint_id}", dependencies=[CatalogWrite])
async def update_endpoint(
    endpoint_id: str, endpoint: ServiceEndpoint, repo: Repo, trigger: Trigger
) -> ServiceEndpoint:
    """Update an existing service endpoint."""
    existing = await repo.get_endpoint(endpoint_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint {endpoint_id} not found"
        )
    await repo.update_endpoint(endpoint)
    if trigger is not None:
        await trigger.on_catalog_updated(endpoint.system_id)
    return endpoint


@router.delete("/endpoints/{endpoint_id}", status_code=204, dependencies=[CatalogDelete])
async def delete_endpoint(endpoint_id: str, repo: Repo) -> Response:
    """Remove a service endpoint."""
    existing = await repo.get_endpoint(endpoint_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint {endpoint_id} not found"
        )
    await repo.delete_endpoint(endpoint_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# System Discovery
# ---------------------------------------------------------------------------


class DetectRequest(BaseModel):
    """Body for triggering system detection."""

    trigger: str = ""


@router.post("/detect", dependencies=[CatalogWrite])
async def trigger_system_detection(request: Request, body: DetectRequest | None = None) -> dict:
    """Trigger system detection analysis (returns a job ID for tracking)."""
    engine = getattr(request.app.state, "system_discovery_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503, detail="System discovery engine not available"
        )
    job_runner = getattr(request.app.state, "job_runner", None)
    if job_runner is None:
        raise HTTPException(
            status_code=503, detail="Job runner not available"
        )

    trigger = body.trigger if body else ""
    job = await engine.discover(trigger, job_runner)
    return {"job_id": job.id, "status": job.status.value, "progress_pct": job.progress_pct}
