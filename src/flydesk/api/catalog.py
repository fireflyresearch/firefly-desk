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

from fastapi import APIRouter, Depends, HTTPException, Response

from flydesk.catalog.enums import SystemStatus
from flydesk.catalog.models import ExternalSystem, ServiceEndpoint
from flydesk.catalog.repository import CatalogRepository
from flydesk.rbac.guards import CatalogDelete, CatalogRead, CatalogWrite
from flydesk.triggers.auto_trigger import AutoTriggerService

VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active"},
    "active": {"disabled", "deprecated", "degraded"},
    "disabled": {"active", "deprecated"},
    "deprecated": set(),  # terminal state
    "degraded": {"active", "disabled"},
}

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_catalog_repo() -> CatalogRepository:
    """Provide a CatalogRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_catalog_repo must be overridden via app.dependency_overrides"
    )


def get_auto_trigger() -> AutoTriggerService | None:
    """Provide the AutoTriggerService instance (or None if not wired).

    In production this is wired via the lifespan.
    In tests the dependency is overridden with a mock.
    """
    return None


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
async def list_systems(repo: Repo) -> list[ExternalSystem]:
    """Return every registered external system."""
    return await repo.list_systems()


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


@router.put("/systems/{system_id}/status", dependencies=[CatalogWrite])
async def update_system_status(system_id: str, body: dict, repo: Repo) -> dict:
    """Transition a system's status according to the state machine."""
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")
    try:
        target = SystemStatus(new_status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status '{new_status}'")

    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail="System not found")

    current = system.status.value if hasattr(system.status, "value") else str(system.status)
    allowed = VALID_TRANSITIONS.get(current, set())
    if target.value not in allowed:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot transition from '{current}' to '{target.value}'. "
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
