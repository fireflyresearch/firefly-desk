# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""REST endpoints for user memory management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from flydesk.memory.models import UpdateMemory
from flydesk.memory.repository import MemoryRepository

router = APIRouter(prefix="/api/memory", tags=["memory"])


def get_memory_repo() -> MemoryRepository:
    raise NotImplementedError("Dependency override required")


def _user_id(request: Request) -> str:
    session = getattr(request.state, "session", None)
    if session and hasattr(session, "user_id"):
        return session.user_id
    raise HTTPException(status_code=401, detail="Not authenticated")


@router.get("")
async def list_memories(
    request: Request,
    category: str | None = None,
    repo: MemoryRepository = Depends(get_memory_repo),
):
    user_id = _user_id(request)
    memories = await repo.list_for_user(user_id, category=category)
    return [m.model_dump() for m in memories]


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    request: Request,
    repo: MemoryRepository = Depends(get_memory_repo),
):
    user_id = _user_id(request)
    deleted = await repo.delete(user_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"status": "deleted"}


@router.patch("/{memory_id}")
async def update_memory(
    memory_id: str,
    body: UpdateMemory,
    request: Request,
    repo: MemoryRepository = Depends(get_memory_repo),
):
    user_id = _user_id(request)
    updated = await repo.update(user_id, memory_id, body)
    if not updated:
        raise HTTPException(status_code=404, detail="Memory not found")
    return updated.model_dump()
