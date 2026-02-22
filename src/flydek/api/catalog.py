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

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from flydek.catalog.models import ExternalSystem, ServiceEndpoint
from flydek.catalog.repository import CatalogRepository

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


async def _require_admin(request: Request) -> None:
    """Raise 403 unless the authenticated user has the 'admin' role."""
    user = getattr(request.state, "user_session", None)
    if user is None or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")


AdminGuard = Depends(_require_admin)
Repo = Annotated[CatalogRepository, Depends(get_catalog_repo)]


# ---------------------------------------------------------------------------
# Systems
# ---------------------------------------------------------------------------


@router.post("/systems", status_code=201, dependencies=[AdminGuard])
async def create_system(system: ExternalSystem, repo: Repo) -> ExternalSystem:
    """Register a new external system."""
    await repo.create_system(system)
    return system


@router.get("/systems", dependencies=[AdminGuard])
async def list_systems(repo: Repo) -> list[ExternalSystem]:
    """Return every registered external system."""
    return await repo.list_systems()


@router.get("/systems/{system_id}", dependencies=[AdminGuard])
async def get_system(system_id: str, repo: Repo) -> ExternalSystem:
    """Retrieve a single external system by ID."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    return system


@router.put("/systems/{system_id}", dependencies=[AdminGuard])
async def update_system(
    system_id: str, system: ExternalSystem, repo: Repo
) -> ExternalSystem:
    """Update an existing external system."""
    existing = await repo.get_system(system_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.update_system(system)
    return system


@router.delete("/systems/{system_id}", status_code=204, dependencies=[AdminGuard])
async def delete_system(system_id: str, repo: Repo) -> Response:
    """Remove an external system."""
    existing = await repo.get_system(system_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.delete_system(system_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/systems/{system_id}/endpoints", status_code=201, dependencies=[AdminGuard]
)
async def create_endpoint(
    system_id: str, endpoint: ServiceEndpoint, repo: Repo
) -> ServiceEndpoint:
    """Add an endpoint to an existing system."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    await repo.create_endpoint(endpoint)
    return endpoint


@router.get("/systems/{system_id}/endpoints", dependencies=[AdminGuard])
async def list_endpoints(system_id: str, repo: Repo) -> list[ServiceEndpoint]:
    """List all endpoints belonging to a system."""
    system = await repo.get_system(system_id)
    if system is None:
        raise HTTPException(status_code=404, detail=f"System {system_id} not found")
    return await repo.list_endpoints(system_id)


@router.get("/endpoints/{endpoint_id}", dependencies=[AdminGuard])
async def get_endpoint(endpoint_id: str, repo: Repo) -> ServiceEndpoint:
    """Retrieve a single endpoint by ID."""
    endpoint = await repo.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint {endpoint_id} not found"
        )
    return endpoint


@router.delete("/endpoints/{endpoint_id}", status_code=204, dependencies=[AdminGuard])
async def delete_endpoint(endpoint_id: str, repo: Repo) -> Response:
    """Remove a service endpoint."""
    existing = await repo.get_endpoint(endpoint_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Endpoint {endpoint_id} not found"
        )
    await repo.delete_endpoint(endpoint_id)
    return Response(status_code=204)
