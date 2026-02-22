# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Export REST API -- create, list, download and manage exports."""

from __future__ import annotations

import re
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from flydesk.exports.models import ExportFormat, ExportRecord, ExportTemplate
from flydesk.exports.repository import ExportRepository
from flydesk.exports.service import ExportService
from flydesk.files.storage import FileStorageProvider
from flydesk.rbac.guards import ExportsTemplates

router = APIRouter(tags=["exports"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_export_repo() -> ExportRepository:
    """Provide an ExportRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_export_repo must be overridden via app.dependency_overrides"
    )


def get_export_service() -> ExportService:
    """Provide an ExportService instance."""
    raise NotImplementedError(
        "get_export_service must be overridden via app.dependency_overrides"
    )


def get_export_storage() -> FileStorageProvider:
    """Provide a FileStorageProvider instance for export downloads."""
    raise NotImplementedError(
        "get_export_storage must be overridden via app.dependency_overrides"
    )


ExportRepo = Annotated[ExportRepository, Depends(get_export_repo)]
ExportSvc = Annotated[ExportService, Depends(get_export_service)]
ExportStorage = Annotated[FileStorageProvider, Depends(get_export_storage)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateExportRequest(BaseModel):
    """Body for POST /api/exports."""

    format: ExportFormat
    title: str
    description: str | None = None
    template_id: str | None = None
    source_data: dict[str, Any] = Field(default_factory=dict)


class CreateTemplateRequest(BaseModel):
    """Body for POST /api/exports/templates."""

    name: str
    format: ExportFormat
    column_mapping: dict[str, str] = Field(default_factory=dict)
    header_text: str | None = None
    footer_text: str | None = None
    is_system: bool = False


# ---------------------------------------------------------------------------
# Template endpoints (MUST come before /{id} routes to avoid path conflicts)
# ---------------------------------------------------------------------------


@router.get("/api/exports/templates")
async def list_templates(repo: ExportRepo) -> list[dict]:
    """List all available export templates."""
    templates = await repo.list_templates()
    return [_template_to_dict(t) for t in templates]


@router.post("/api/exports/templates", status_code=201, dependencies=[ExportsTemplates])
async def create_template(body: CreateTemplateRequest, repo: ExportRepo) -> dict:
    """Create a new export template (admin only)."""
    template = ExportTemplate(
        id=str(uuid.uuid4()),
        name=body.name,
        format=body.format,
        column_mapping=body.column_mapping,
        header_text=body.header_text,
        footer_text=body.footer_text,
        is_system=body.is_system,
    )
    await repo.create_template(template)
    return _template_to_dict(template)


@router.delete(
    "/api/exports/templates/{template_id}",
    status_code=204,
    dependencies=[ExportsTemplates],
)
async def delete_template(template_id: str, repo: ExportRepo) -> Response:
    """Delete an export template (admin only)."""
    existing = await repo.get_template(template_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    await repo.delete_template(template_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------


@router.post("/api/exports", status_code=201)
async def create_export(
    request: Request,
    body: CreateExportRequest,
    service: ExportSvc,
) -> dict:
    """Create a new export from source data."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    record = await service.create_export(
        user_id=user_id,
        fmt=body.format,
        source_data=body.source_data,
        title=body.title,
        template_id=body.template_id,
    )
    return _export_to_dict(record)


@router.get("/api/exports")
async def list_exports(
    request: Request,
    repo: ExportRepo,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[dict]:
    """List the current user's exports."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    records = await repo.list_exports(user_id, limit=limit)
    return [_export_to_dict(r) for r in records]


@router.get("/api/exports/{export_id}")
async def get_export(export_id: str, repo: ExportRepo) -> dict:
    """Get details of a specific export."""
    record = await repo.get_export(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Export {export_id} not found")
    return _export_to_dict(record)


@router.get("/api/exports/{export_id}/download")
async def download_export(
    export_id: str,
    request: Request,
    repo: ExportRepo,
    storage: ExportStorage,
) -> Response:
    """Download an export file."""
    record = await repo.get_export(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Export {export_id} not found")

    # Ownership check -- only the owner (or admin) may download.
    user_session = getattr(request.state, "user_session", None)
    if user_session and record.user_id != user_session.user_id:
        if "admin" not in getattr(user_session, "roles", set()):
            raise HTTPException(status_code=403, detail="Not authorised to access this export")

    if not record.file_path:
        raise HTTPException(status_code=404, detail="Export file not available")

    content = await storage.retrieve(record.file_path)

    # Sanitise title for use in Content-Disposition header.
    safe_title = re.sub(r'[^\w\s\-.]', '_', record.title)[:200]

    # Determine content type and filename from the stored file extension
    if record.file_path.endswith(".csv"):
        content_type = "text/csv"
        filename = f"{safe_title}.csv"
    elif record.file_path.endswith(".json"):
        content_type = "application/json"
        filename = f"{safe_title}.json"
    elif record.file_path.endswith(".html"):
        content_type = "text/html"
        filename = f"{safe_title}.html"
    elif record.file_path.endswith(".pdf"):
        content_type = "application/pdf"
        filename = f"{safe_title}.pdf"
    else:
        content_type = "application/octet-stream"
        filename = f"{safe_title}"

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@router.delete("/api/exports/{export_id}", status_code=204)
async def delete_export(
    export_id: str,
    request: Request,
    repo: ExportRepo,
    storage: ExportStorage,
) -> Response:
    """Delete an export and its stored file."""
    record = await repo.get_export(export_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Export {export_id} not found")

    # Ownership check -- only the owner (or admin) may delete.
    user_session = getattr(request.state, "user_session", None)
    if user_session and record.user_id != user_session.user_id:
        if "admin" not in getattr(user_session, "roles", set()):
            raise HTTPException(status_code=403, detail="Not authorised to delete this export")

    # Clean up stored file if present
    if record.file_path:
        try:
            await storage.delete(record.file_path)
        except Exception:
            pass  # Best-effort cleanup

    await repo.delete_export(export_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _export_to_dict(record: ExportRecord) -> dict:
    return {
        "id": record.id,
        "user_id": record.user_id,
        "format": record.format.value,
        "template_id": record.template_id,
        "title": record.title,
        "description": record.description,
        "status": record.status.value,
        "file_path": record.file_path,
        "file_size": record.file_size,
        "row_count": record.row_count,
        "error": record.error,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "completed_at": record.completed_at.isoformat() if record.completed_at else None,
    }


def _template_to_dict(template: ExportTemplate) -> dict:
    return {
        "id": template.id,
        "name": template.name,
        "format": template.format.value,
        "column_mapping": template.column_mapping,
        "header_text": template.header_text,
        "footer_text": template.footer_text,
        "is_system": template.is_system,
        "created_at": template.created_at.isoformat() if template.created_at else None,
    }
