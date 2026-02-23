# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Processes REST API -- discovery, CRUD, and verification for business processes."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel

from flydesk.processes.models import (
    BusinessProcess,
    ProcessStatus,
    ProcessStep,
)
from flydesk.processes.repository import ProcessRepository
from flydesk.rbac.guards import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/processes", tags=["processes"])

# Permission guards
ProcessRead = require_permission("processes:read")
ProcessWrite = require_permission("processes:write")


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_process_repo() -> ProcessRepository:
    """Provide a ProcessRepository instance (wired via dependency_overrides)."""
    raise NotImplementedError(
        "get_process_repo must be overridden via app.dependency_overrides"
    )


ProcessRepo = Annotated[ProcessRepository, Depends(get_process_repo)]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class DiscoverRequest(BaseModel):
    """Body for triggering process discovery."""

    trigger: str = ""


class StepUpdate(BaseModel):
    """Body for updating an individual process step."""

    name: str
    description: str = ""
    step_type: str = ""
    system_id: str | None = None
    endpoint_id: str | None = None
    order: int = 0
    inputs: list[str] = []
    outputs: list[str] = []


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _process_to_dict(process: BusinessProcess) -> dict:
    """Convert a BusinessProcess domain model to a JSON-friendly dict."""
    return {
        "id": process.id,
        "name": process.name,
        "description": process.description,
        "category": process.category,
        "source": process.source.value,
        "confidence": process.confidence,
        "status": process.status.value,
        "tags": process.tags,
        "steps": [_step_to_dict(s) for s in process.steps],
        "dependencies": [
            {
                "source_step_id": d.source_step_id,
                "target_step_id": d.target_step_id,
                "condition": d.condition,
            }
            for d in process.dependencies
        ],
        "created_at": process.created_at.isoformat() if process.created_at else None,
        "updated_at": process.updated_at.isoformat() if process.updated_at else None,
    }


def _step_to_dict(step: ProcessStep) -> dict:
    """Convert a ProcessStep domain model to a JSON-friendly dict."""
    return {
        "id": step.id,
        "name": step.name,
        "description": step.description,
        "step_type": step.step_type,
        "system_id": step.system_id,
        "endpoint_id": step.endpoint_id,
        "order": step.order,
        "inputs": step.inputs,
        "outputs": step.outputs,
    }


def _process_summary(process: BusinessProcess) -> dict:
    """Convert a BusinessProcess to a summary dict (no steps/dependencies)."""
    return {
        "id": process.id,
        "name": process.name,
        "description": process.description,
        "category": process.category,
        "source": process.source.value,
        "confidence": process.confidence,
        "status": process.status.value,
        "tags": process.tags,
        "step_count": len(process.steps),
        "created_at": process.created_at.isoformat() if process.created_at else None,
        "updated_at": process.updated_at.isoformat() if process.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", dependencies=[ProcessRead])
async def list_processes(
    repo: ProcessRepo,
    category: str | None = Query(None, description="Filter by category"),
    status: str | None = Query(None, description="Filter by status"),
    tag: str | None = Query(None, description="Filter by tag"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List business processes with optional filters."""
    status_enum: ProcessStatus | None = None
    if status is not None:
        try:
            status_enum = ProcessStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. "
                f"Must be one of: {', '.join(s.value for s in ProcessStatus)}",
            )

    processes = await repo.list(
        category=category,
        status=status_enum,
        tag=tag,
        limit=limit,
        offset=offset,
    )
    return [_process_summary(p) for p in processes]


@router.get("/{process_id}", dependencies=[ProcessRead])
async def get_process(process_id: str, repo: ProcessRepo) -> dict:
    """Get details of a specific process including steps and dependencies."""
    process = await repo.get(process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return _process_to_dict(process)


@router.put("/{process_id}", dependencies=[ProcessWrite])
async def update_process(
    process_id: str, body: BusinessProcess, repo: ProcessRepo
) -> dict:
    """Update an existing business process (user corrections)."""
    existing = await repo.get(process_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Process not found")

    # Ensure the ID in the path matches the body
    body.id = process_id
    updated = await repo.update(body)
    return _process_to_dict(updated)


@router.delete("/{process_id}", dependencies=[ProcessWrite], status_code=204)
async def delete_process(process_id: str, repo: ProcessRepo) -> Response:
    """Archive or delete a business process."""
    deleted = await repo.delete(process_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Process not found")
    return Response(status_code=204)


@router.post("/discover", dependencies=[ProcessWrite])
async def trigger_discovery(request: Request, body: DiscoverRequest | None = None) -> dict:
    """Trigger process discovery analysis (returns a job ID for tracking)."""
    engine = getattr(request.app.state, "discovery_engine", None)
    if engine is None:
        raise HTTPException(
            status_code=503, detail="Discovery engine not available"
        )
    job_runner = getattr(request.app.state, "job_runner", None)
    if job_runner is None:
        raise HTTPException(
            status_code=503, detail="Job runner not available"
        )

    trigger = body.trigger if body else ""
    job = await engine.discover(trigger, job_runner)
    return {"job_id": job.id, "status": job.status.value}


@router.put("/{process_id}/steps/{step_id}", dependencies=[ProcessWrite])
async def update_step(
    process_id: str, step_id: str, body: StepUpdate, repo: ProcessRepo
) -> dict:
    """Update an individual step within a process."""
    existing = await repo.get(process_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Process not found")

    step = ProcessStep(
        id=step_id,
        name=body.name,
        description=body.description,
        step_type=body.step_type,
        system_id=body.system_id,
        endpoint_id=body.endpoint_id,
        order=body.order,
        inputs=body.inputs,
        outputs=body.outputs,
    )
    result = await repo.update_step(process_id, step)
    if result is None:
        raise HTTPException(status_code=404, detail="Process not found")
    return _step_to_dict(result)


@router.post("/{process_id}/verify", dependencies=[ProcessWrite])
async def verify_process(process_id: str, repo: ProcessRepo) -> dict:
    """Mark a process as verified by a user."""
    process = await repo.get(process_id)
    if process is None:
        raise HTTPException(status_code=404, detail="Process not found")

    process.status = ProcessStatus.VERIFIED
    updated = await repo.update(process)
    return _process_to_dict(updated)
