# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Document Source admin API -- CRUD for cloud storage and drive providers."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel

from flydesk.api.deps import get_document_source_repo
from flydesk.knowledge.document_source import DocumentSourceFactory
from flydesk.knowledge.document_source_repository import DocumentSource, DocumentSourceRepository
from flydesk.rbac.guards import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/document-sources", tags=["document-sources"])

AdminOnly = require_permission("*")
Repo = Annotated[DocumentSourceRepository, Depends(get_document_source_repo)]

_CATEGORY_MAP: dict[str, str] = {
    "s3": "blob",
    "azure_blob": "blob",
    "gcs": "blob",
    "onedrive": "drive",
    "sharepoint": "drive",
    "google_drive": "drive",
}


class DocumentSourceRequest(BaseModel):
    source_type: str
    display_name: str
    auth_method: str = "credentials"
    config: dict[str, Any] = {}
    sync_enabled: bool = False
    sync_cron: str | None = None


class DocumentSourceResponse(BaseModel):
    id: str
    source_type: str
    category: str
    display_name: str
    auth_method: str
    has_config: bool
    config_summary: dict[str, str] | None
    is_active: bool
    sync_enabled: bool
    sync_cron: str | None
    last_sync_at: str | None
    created_at: str | None
    updated_at: str | None


class TestResult(BaseModel):
    reachable: bool
    error: str | None = None


def _to_response(src: DocumentSource) -> DocumentSourceResponse:
    return DocumentSourceResponse(
        id=src.id,
        source_type=src.source_type,
        category=src.category,
        display_name=src.display_name,
        auth_method=src.auth_method,
        has_config=src.has_config,
        config_summary=src.config_summary,
        is_active=src.is_active,
        sync_enabled=src.sync_enabled,
        sync_cron=src.sync_cron,
        last_sync_at=src.last_sync_at,
        created_at=src.created_at,
        updated_at=src.updated_at,
    )


@router.get("", dependencies=[AdminOnly])
async def list_document_sources(repo: Repo) -> list[DocumentSourceResponse]:
    sources = await repo.list_all()
    return [_to_response(s) for s in sources]


@router.post("", status_code=201, dependencies=[AdminOnly])
async def create_document_source(body: DocumentSourceRequest, repo: Repo) -> DocumentSourceResponse:
    category = _CATEGORY_MAP.get(body.source_type, "blob")
    source = await repo.create(
        source_type=body.source_type,
        category=category,
        display_name=body.display_name,
        auth_method=body.auth_method,
        config=body.config,
        sync_enabled=body.sync_enabled,
        sync_cron=body.sync_cron,
    )
    return _to_response(source)


@router.get("/{source_id}", dependencies=[AdminOnly])
async def get_document_source(source_id: str, repo: Repo) -> DocumentSourceResponse:
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    return _to_response(source)


@router.put("/{source_id}", dependencies=[AdminOnly])
async def update_document_source(source_id: str, body: DocumentSourceRequest, repo: Repo) -> DocumentSourceResponse:
    source = await repo.update(
        source_id,
        display_name=body.display_name,
        auth_method=body.auth_method,
        config=body.config if body.config else None,
        sync_enabled=body.sync_enabled,
        sync_cron=body.sync_cron,
    )
    if source is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    return _to_response(source)


@router.delete("/{source_id}", status_code=204, dependencies=[AdminOnly])
async def delete_document_source(source_id: str, repo: Repo) -> Response:
    existing = await repo.get(source_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    await repo.delete(source_id)
    return Response(status_code=204)


@router.post("/{source_id}/test", dependencies=[AdminOnly])
async def test_document_source(source_id: str, repo: Repo) -> TestResult:
    config = await repo.get_decrypted_config(source_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    row = await repo.get_row(source_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Source not found")

    try:
        _ensure_adapters_loaded(row.source_type)
        adapter = DocumentSourceFactory.create(row.source_type, config)
        reachable = await adapter.validate_credentials()
        await adapter.aclose()
        return TestResult(reachable=reachable)
    except Exception as exc:
        logger.warning("Document source test failed: %s", exc)
        return TestResult(reachable=False, error=str(exc))


@router.post("/{source_id}/sync", dependencies=[AdminOnly])
async def sync_document_source(source_id: str, repo: Repo) -> dict:
    source = await repo.get(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Document source {source_id} not found")
    # Sync will be wired in Task 15/18 via JobRunner
    return {"status": "triggered", "source_id": source_id}


def _ensure_adapters_loaded(source_type: str) -> None:
    """Lazily import adapter modules to register them in the factory."""
    if source_type in DocumentSourceFactory.registered_types():
        return
    adapter_modules = {
        "s3": "flydesk.knowledge.adapters.s3",
        "azure_blob": "flydesk.knowledge.adapters.azure_blob",
        "gcs": "flydesk.knowledge.adapters.gcs",
        "onedrive": "flydesk.knowledge.adapters.onedrive",
        "sharepoint": "flydesk.knowledge.adapters.sharepoint",
        "google_drive": "flydesk.knowledge.adapters.google_drive",
    }
    module_path = adapter_modules.get(source_type)
    if module_path:
        import importlib
        importlib.import_module(module_path)
