"""Admin API endpoints for the dead-letter queue."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/dead-letter", tags=["admin"])


@router.get("")
async def list_entries(
    request: Request,
    source_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    dlq = request.app.state.dead_letter
    entries = await dlq.list_entries(source_type=source_type, limit=limit, offset=offset)
    return {
        "entries": [
            {
                "id": e.id,
                "source_type": e.source_type,
                "source_id": e.source_id,
                "error": e.error,
                "attempts": e.attempts,
                "max_attempts": e.max_attempts,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in entries
        ],
        "total": len(entries),
    }


@router.post("/{entry_id}/retry", response_model=None)
async def retry_entry(request: Request, entry_id: str) -> dict | JSONResponse:
    dlq = request.app.state.dead_letter
    entry = await dlq.retry(entry_id)
    if entry is None:
        return JSONResponse(status_code=404, content={"detail": "Entry not found"})
    return {"id": entry.id, "attempts": entry.attempts, "status": "retrying"}


@router.delete("/{entry_id}", response_model=None)
async def delete_entry(request: Request, entry_id: str) -> dict | JSONResponse:
    dlq = request.app.state.dead_letter
    removed = await dlq.remove(entry_id)
    if not removed:
        return JSONResponse(status_code=404, content={"detail": "Entry not found"})
    return {"id": entry_id, "status": "deleted"}
