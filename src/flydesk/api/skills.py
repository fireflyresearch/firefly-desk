# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Skills admin REST API -- CRUD for agent skill definitions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from flydesk.rbac.guards import AdminSettings
from flydesk.skills.models import Skill
from flydesk.skills.repository import SkillRepository

router = APIRouter(tags=["skills"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_skill_repo() -> SkillRepository:
    """Provide a SkillRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_skill_repo must be overridden via app.dependency_overrides"
    )


SkillRepo = Annotated[SkillRepository, Depends(get_skill_repo)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class CreateSkillRequest(BaseModel):
    """Body for POST /api/admin/skills."""

    name: str
    description: str = ""
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    active: bool = True


class UpdateSkillRequest(BaseModel):
    """Body for PUT /api/admin/skills/{skill_id}."""

    name: str | None = None
    description: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSettings
# ---------------------------------------------------------------------------


@router.get("/api/admin/skills", dependencies=[AdminSettings])
async def list_skills(repo: SkillRepo) -> list[dict]:
    """List all skills."""
    skills = await repo.list_skills()
    return [_skill_to_dict(s) for s in skills]


@router.post("/api/admin/skills", status_code=201, dependencies=[AdminSettings])
async def create_skill(body: CreateSkillRequest, repo: SkillRepo) -> dict:
    """Create a new skill."""
    skill = Skill(
        id=f"skill-{uuid.uuid4().hex[:12]}",
        name=body.name,
        description=body.description,
        content=body.content,
        tags=body.tags,
        active=body.active,
    )
    created = await repo.create_skill(skill)
    return _skill_to_dict(created)


@router.get("/api/admin/skills/{skill_id}", dependencies=[AdminSettings])
async def get_skill(skill_id: str, repo: SkillRepo) -> dict:
    """Get skill details."""
    skill = await repo.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return _skill_to_dict(skill)


@router.put("/api/admin/skills/{skill_id}", dependencies=[AdminSettings])
async def update_skill(skill_id: str, body: UpdateSkillRequest, repo: SkillRepo) -> dict:
    """Update a skill."""
    kwargs: dict = {}
    if body.name is not None:
        kwargs["name"] = body.name
    if body.description is not None:
        kwargs["description"] = body.description
    if body.content is not None:
        kwargs["content"] = body.content
    if body.tags is not None:
        kwargs["tags"] = body.tags
    if body.active is not None:
        kwargs["active"] = body.active

    if not kwargs:
        raise HTTPException(status_code=400, detail="No fields to update")

    updated = await repo.update_skill(skill_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return _skill_to_dict(updated)


@router.delete("/api/admin/skills/{skill_id}", status_code=204, dependencies=[AdminSettings])
async def delete_skill(skill_id: str, repo: SkillRepo) -> Response:
    """Delete a skill."""
    deleted = await repo.delete_skill(skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _skill_to_dict(skill: Skill) -> dict:
    return {
        "id": skill.id,
        "name": skill.name,
        "description": skill.description,
        "content": skill.content,
        "tags": skill.tags,
        "active": skill.active,
        "created_at": skill.created_at.isoformat() if skill.created_at else None,
        "updated_at": skill.updated_at.isoformat() if skill.updated_at else None,
    }
