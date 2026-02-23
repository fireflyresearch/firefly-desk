# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Prompt template admin REST API -- list, view, and override prompt templates."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

router = APIRouter(tags=["prompts"])

# Directory where the built-in .j2 templates reside
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "prompts" / "templates"

_PROMPT_CATEGORY = "prompt_override"


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class TemplateInfo(BaseModel):
    """Summary of a prompt template."""

    name: str
    has_override: bool = False


class TemplateDetail(BaseModel):
    """Full template content."""

    name: str
    source: str
    has_override: bool = False


class UpdateTemplateRequest(BaseModel):
    """Body for PUT /api/admin/prompts/templates/{name}."""

    source: str


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSettings
# ---------------------------------------------------------------------------


@router.get("/api/admin/prompts/templates", dependencies=[AdminSettings])
async def list_templates(repo: Repo) -> list[dict]:
    """List all .j2 template files from the templates directory."""
    templates: list[dict] = []

    # Get all overrides from DB to flag which templates have been customized
    overrides = await repo.get_all_app_settings(category=_PROMPT_CATEGORY)

    if _TEMPLATES_DIR.exists():
        for f in sorted(_TEMPLATES_DIR.glob("*.j2")):
            override_key = f"prompt:{f.stem}"
            # Empty string override means "reset to default", not a real override
            has_override = override_key in overrides and bool(overrides[override_key])
            templates.append({
                "name": f.stem,
                "has_override": has_override,
            })

    return templates


@router.get("/api/admin/prompts/templates/{name}", dependencies=[AdminSettings])
async def get_template(name: str, repo: Repo) -> dict:
    """Read template content. Returns DB override if one exists, otherwise the file content."""
    # Check for DB override first
    override_key = f"prompt:{name}"
    override = await repo.get_app_setting(override_key)

    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    if override is not None and override != "":
        return {
            "name": name,
            "source": override,
            "has_override": True,
        }

    source = template_file.read_text(encoding="utf-8")
    return {
        "name": name,
        "source": source,
        "has_override": False,
    }


@router.put("/api/admin/prompts/templates/{name}", dependencies=[AdminSettings])
async def update_template(name: str, body: UpdateTemplateRequest, repo: Repo) -> dict:
    """Store a prompt override in the DB via the settings repository."""
    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    override_key = f"prompt:{name}"
    await repo.set_app_setting(override_key, body.source, category=_PROMPT_CATEGORY)

    return {
        "name": name,
        "source": body.source,
        "has_override": True,
    }


@router.delete("/api/admin/prompts/templates/{name}/override", dependencies=[AdminSettings])
async def delete_template_override(name: str, repo: Repo) -> dict:
    """Remove a prompt override, reverting to the built-in template."""
    template_file = _TEMPLATES_DIR / f"{name}.j2"
    if not template_file.exists():
        raise HTTPException(
            status_code=404, detail=f"Template '{name}' not found"
        )

    override_key = f"prompt:{name}"
    # Set to empty string effectively removes it; we use set_app_setting
    # to overwrite. A proper delete would be better but we reuse the settings repo.
    override = await repo.get_app_setting(override_key)
    if override is None:
        return {
            "name": name,
            "source": template_file.read_text(encoding="utf-8"),
            "has_override": False,
        }

    # Clear the override by setting to empty -- on next read the file content is returned
    # Actually, just set it to the original file content to effectively "reset"
    await repo.set_app_setting(override_key, "", category=_PROMPT_CATEGORY)

    source = template_file.read_text(encoding="utf-8")
    return {
        "name": name,
        "source": source,
        "has_override": False,
    }
