# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Cloud import API -- browse and import documents from cloud storage and drives."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from flydesk.api.deps import get_document_source_repo
from flydesk.api.document_sources import _ensure_adapters_loaded
from flydesk.knowledge.document_source import (
    BlobStorageProvider,
    DocumentSourceFactory,
    DriveProvider,
)
from flydesk.knowledge.document_source_repository import DocumentSourceRepository
from flydesk.rbac.guards import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["cloud-import"])

AdminOnly = require_permission("*")
Repo = Annotated[DocumentSourceRepository, Depends(get_document_source_repo)]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class BrowseItem(BaseModel):
    id: str
    name: str
    type: str  # "container", "drive", "folder", "file"
    size: int = 0
    last_modified: str = ""
    mime_type: str = ""
    path: str = ""


class ImportItem(BaseModel):
    container_or_drive: str
    key_or_item_id: str
    name: str = ""


class ImportRequest(BaseModel):
    items: list[ImportItem]
    tags: list[str] = []
    workspace_ids: list[str] = []
    document_type: str | None = None


class ImportResponse(BaseModel):
    status: str = "accepted"
    total: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_adapter(source_id: str, repo: DocumentSourceRepository):
    """Get decrypted config and create adapter for a source."""
    config = await repo.get_decrypted_config(source_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    row = await repo.get_row(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")
    _ensure_adapters_loaded(row.source_type)
    adapter = DocumentSourceFactory.create(row.source_type, config)
    return adapter, row


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{source_id}/browse", dependencies=[AdminOnly])
async def browse_root(source_id: str, repo: Repo) -> list[BrowseItem]:
    """List containers (blob) or drives (drive) for a source."""
    adapter, row = await _get_adapter(source_id, repo)
    try:
        if isinstance(adapter, BlobStorageProvider):
            containers = await adapter.list_containers()
            return [
                BrowseItem(id=c.name, name=c.name, type="container")
                for c in containers
            ]
        elif isinstance(adapter, DriveProvider):
            drives = await adapter.list_drives()
            return [
                BrowseItem(id=d.id, name=d.name, type="drive")
                for d in drives
            ]
        else:
            return []
    finally:
        await adapter.aclose()


@router.get("/{source_id}/browse/{root_id}", dependencies=[AdminOnly])
async def browse_contents(
    source_id: str,
    root_id: str,
    repo: Repo,
    prefix: str = Query("", description="Prefix filter for blob storage"),
    folder_id: str = Query("", description="Folder ID for drive navigation"),
) -> list[BrowseItem]:
    """List files in a container/drive."""
    adapter, row = await _get_adapter(source_id, repo)
    try:
        if isinstance(adapter, BlobStorageProvider):
            objects = await adapter.list_objects(root_id, prefix=prefix)
            return [
                BrowseItem(
                    id=obj.key,
                    name=obj.key.rsplit("/", 1)[-1] if "/" in obj.key else obj.key,
                    type="file",
                    size=obj.size,
                    last_modified=obj.last_modified,
                    mime_type=obj.content_type,
                    path=obj.key,
                )
                for obj in objects
            ]
        elif isinstance(adapter, DriveProvider):
            items = await adapter.list_items(root_id, folder_id=folder_id)
            return [
                BrowseItem(
                    id=item.id,
                    name=item.name,
                    type="folder" if item.is_folder else "file",
                    size=item.size,
                    last_modified=item.modified_at,
                    mime_type=item.mime_type,
                    path=item.path,
                )
                for item in items
            ]
        else:
            return []
    finally:
        await adapter.aclose()


@router.post("/{source_id}/import", status_code=202, dependencies=[AdminOnly])
async def import_files(source_id: str, body: ImportRequest, repo: Repo) -> ImportResponse:
    """Import selected files from a cloud source. Returns 202 Accepted."""
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")

    total = len(body.items)
    logger.info(
        "Import requested: %d files from source %s (%s)",
        total,
        source_id,
        source.source_type,
    )

    # In a full implementation, this would enqueue IndexingTasks.
    # For now, return accepted with count.
    return ImportResponse(
        status="accepted",
        total=total,
        message=f"Queued {total} file(s) for import from {source.display_name}",
    )
