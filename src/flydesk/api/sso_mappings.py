# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""SSO Attribute Mapping admin REST API -- CRUD for claim-to-header mappings.

Mappings are persisted via the :class:`SettingsRepository` with
``category='sso_mappings'``.  Each mapping is stored as a JSON-encoded
:class:`SSOAttributeMapping` keyed by its ``id``.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from flydesk.auth.sso_mapping import SSOAttributeMapping
from flydesk.rbac.guards import AdminSSO
from flydesk.settings.repository import SettingsRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/sso-mappings", tags=["sso-mappings"])

_SSO_MAPPING_CATEGORY = "sso_mappings"


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


class CreateSSOMapping(BaseModel):
    """Body for POST /api/admin/sso-mappings."""

    claim_path: str
    target_header: str
    target_type: Literal["header", "query_param"] = "header"
    system_filter: str | None = None
    transform: str | None = None


class UpdateSSOMapping(BaseModel):
    """Body for PUT /api/admin/sso-mappings/{mapping_id}."""

    claim_path: str
    target_header: str
    target_type: Literal["header", "query_param"] = "header"
    system_filter: str | None = None
    transform: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_all_mappings(repo: SettingsRepository) -> list[SSOAttributeMapping]:
    """Load all SSO attribute mappings from the settings store."""
    raw = await repo.get_all_app_settings(category=_SSO_MAPPING_CATEGORY)
    mappings: list[SSOAttributeMapping] = []
    for _key, value in raw.items():
        try:
            data = json.loads(value)
            mappings.append(SSOAttributeMapping(**data))
        except Exception:
            logger.warning("Skipping corrupt SSO mapping entry: %s", _key)
    return mappings


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSSO
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminSSO])
async def list_sso_mappings(repo: Repo) -> list[SSOAttributeMapping]:
    """List all SSO attribute mappings."""
    return await _load_all_mappings(repo)


@router.post("", dependencies=[AdminSSO], status_code=201)
async def create_sso_mapping(
    body: CreateSSOMapping, repo: Repo
) -> SSOAttributeMapping:
    """Create a new SSO attribute mapping."""
    mapping_id = str(uuid.uuid4())
    mapping = SSOAttributeMapping(
        id=mapping_id,
        claim_path=body.claim_path,
        target_header=body.target_header,
        target_type=body.target_type,
        system_filter=body.system_filter,
        transform=body.transform,
    )
    await repo.set_app_setting(
        f"sso_mapping:{mapping_id}",
        mapping.model_dump_json(),
        category=_SSO_MAPPING_CATEGORY,
    )
    return mapping


@router.put("/{mapping_id}", dependencies=[AdminSSO])
async def update_sso_mapping(
    mapping_id: str, body: UpdateSSOMapping, repo: Repo
) -> SSOAttributeMapping:
    """Update an existing SSO attribute mapping."""
    key = f"sso_mapping:{mapping_id}"
    existing = await repo.get_app_setting(key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"SSO mapping '{mapping_id}' not found",
        )
    mapping = SSOAttributeMapping(
        id=mapping_id,
        claim_path=body.claim_path,
        target_header=body.target_header,
        target_type=body.target_type,
        system_filter=body.system_filter,
        transform=body.transform,
    )
    await repo.set_app_setting(
        key,
        mapping.model_dump_json(),
        category=_SSO_MAPPING_CATEGORY,
    )
    return mapping


@router.delete("/{mapping_id}", dependencies=[AdminSSO])
async def delete_sso_mapping(mapping_id: str, repo: Repo) -> dict[str, str]:
    """Delete an SSO attribute mapping."""
    key = f"sso_mapping:{mapping_id}"
    existing = await repo.get_app_setting(key)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"SSO mapping '{mapping_id}' not found",
        )
    # Clear by setting to empty string (settings repo doesn't have a delete).
    # We overwrite with an empty value then rely on _load_all_mappings to skip
    # empty / corrupt entries.  A proper delete_app_setting would be cleaner
    # but we reuse the existing settings repo contract.
    await repo.set_app_setting(key, "", category=_SSO_MAPPING_CATEGORY)
    return {"detail": f"SSO mapping '{mapping_id}' deleted"}
