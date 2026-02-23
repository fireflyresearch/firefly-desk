# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tools Management admin REST API -- browse, test, and configure tools."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flydesk.catalog.models import ServiceEndpoint
from flydesk.catalog.repository import CatalogRepository
from flydesk.rbac.guards import AdminSettings
from flydesk.settings.repository import SettingsRepository

router = APIRouter(prefix="/api/admin/tools", tags=["tools-admin"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_catalog_repo() -> CatalogRepository:
    """Provide a CatalogRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_catalog_repo must be overridden via app.dependency_overrides"
    )


def get_settings_repo() -> SettingsRepository:
    """Provide a SettingsRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden via app.dependency_overrides.
    """
    raise NotImplementedError(
        "get_settings_repo must be overridden via app.dependency_overrides"
    )


CatalogRepo = Annotated[CatalogRepository, Depends(get_catalog_repo)]
SettingsRepo = Annotated[SettingsRepository, Depends(get_settings_repo)]


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------


class ToolSummary(BaseModel):
    """Summary of a tool (service endpoint) for the list view."""

    id: str
    name: str
    description: str
    system_id: str
    method: str
    path: str
    risk_level: str
    required_permissions: list[str]
    enabled: bool = True


class ToolDetail(BaseModel):
    """Full detail for a single tool."""

    id: str
    name: str
    description: str
    system_id: str
    method: str
    path: str
    risk_level: str
    required_permissions: list[str]
    when_to_use: str
    examples: list[str]
    path_params: dict[str, Any] | None = None
    query_params: dict[str, Any] | None = None
    request_body: dict[str, Any] | None = None
    response_schema: dict[str, Any] | None = None
    timeout_seconds: float = 30.0
    tags: list[str] = Field(default_factory=list)
    enabled: bool = True
    config_overrides: dict[str, Any] = Field(default_factory=dict)


class ToolTestRequest(BaseModel):
    """Body for POST /api/admin/tools/{endpoint_id}/test."""

    params: dict[str, Any] = Field(default_factory=dict)


class ToolTestResult(BaseModel):
    """Preview of what a tool call would look like."""

    endpoint_id: str
    method: str
    path: str
    resolved_path: str
    query_params: dict[str, Any]
    body: dict[str, Any] | None
    risk_level: str
    would_require_permissions: list[str]
    preview: bool = True


class ToolConfigUpdate(BaseModel):
    """Body for PUT /api/admin/tools/{endpoint_id}/config."""

    enabled: bool | None = None
    required_permissions: list[str] | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOOL_CONFIG_CATEGORY = "tool_config"


async def _get_tool_config(
    settings_repo: SettingsRepository, endpoint_id: str
) -> dict[str, Any]:
    """Load tool config overrides from the settings repo."""
    raw = await settings_repo.get_app_setting(f"tool_config:{endpoint_id}")
    if raw is None:
        return {}
    return json.loads(raw)


def _endpoint_to_summary(
    endpoint: ServiceEndpoint, config: dict[str, Any]
) -> ToolSummary:
    """Convert a ServiceEndpoint + config overrides to a ToolSummary."""
    return ToolSummary(
        id=endpoint.id,
        name=endpoint.name,
        description=endpoint.description,
        system_id=endpoint.system_id,
        method=endpoint.method.value if hasattr(endpoint.method, "value") else str(endpoint.method),
        path=endpoint.path,
        risk_level=endpoint.risk_level.value if hasattr(endpoint.risk_level, "value") else str(endpoint.risk_level),
        required_permissions=config.get("required_permissions", endpoint.required_permissions),
        enabled=config.get("enabled", True),
    )


def _endpoint_to_detail(
    endpoint: ServiceEndpoint, config: dict[str, Any]
) -> ToolDetail:
    """Convert a ServiceEndpoint + config overrides to a ToolDetail."""
    # Serialize param schemas to dicts if they are pydantic models
    def _params_to_dict(params):
        if params is None:
            return None
        if isinstance(params, dict):
            result = {}
            for k, v in params.items():
                result[k] = v.model_dump() if hasattr(v, "model_dump") else v
            return result
        return params

    return ToolDetail(
        id=endpoint.id,
        name=endpoint.name,
        description=endpoint.description,
        system_id=endpoint.system_id,
        method=endpoint.method.value if hasattr(endpoint.method, "value") else str(endpoint.method),
        path=endpoint.path,
        risk_level=endpoint.risk_level.value if hasattr(endpoint.risk_level, "value") else str(endpoint.risk_level),
        required_permissions=config.get("required_permissions", endpoint.required_permissions),
        when_to_use=endpoint.when_to_use,
        examples=endpoint.examples,
        path_params=_params_to_dict(endpoint.path_params),
        query_params=_params_to_dict(endpoint.query_params),
        request_body=endpoint.request_body,
        response_schema=endpoint.response_schema,
        timeout_seconds=endpoint.timeout_seconds,
        tags=endpoint.tags,
        enabled=config.get("enabled", True),
        config_overrides=config,
    )


# ---------------------------------------------------------------------------
# Endpoints -- all guarded by AdminSettings
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AdminSettings])
async def list_tools(
    catalog_repo: CatalogRepo, settings_repo: SettingsRepo
) -> list[ToolSummary]:
    """List all tools (service endpoints) with metadata and config overrides."""
    endpoints = await catalog_repo.list_active_endpoints()
    results: list[ToolSummary] = []
    for ep in endpoints:
        config = await _get_tool_config(settings_repo, ep.id)
        results.append(_endpoint_to_summary(ep, config))
    return results


@router.get("/{endpoint_id}", dependencies=[AdminSettings])
async def get_tool(
    endpoint_id: str, catalog_repo: CatalogRepo, settings_repo: SettingsRepo
) -> ToolDetail:
    """Get detailed information for a specific tool."""
    endpoint = await catalog_repo.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Tool endpoint '{endpoint_id}' not found"
        )
    config = await _get_tool_config(settings_repo, endpoint_id)
    return _endpoint_to_detail(endpoint, config)


@router.post("/{endpoint_id}/test", dependencies=[AdminSettings])
async def test_tool(
    endpoint_id: str,
    body: ToolTestRequest,
    catalog_repo: CatalogRepo,
) -> ToolTestResult:
    """Test execution preview -- validates params and returns what would be called.

    For safety, this does NOT actually execute the tool call.  It resolves
    path parameters, separates query params from body params, and returns
    a preview of the request that would be made.
    """
    endpoint = await catalog_repo.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Tool endpoint '{endpoint_id}' not found"
        )

    # Resolve path parameters
    resolved_path = endpoint.path
    query_params: dict[str, Any] = {}
    body_params: dict[str, Any] | None = None

    path_param_names = set()
    if endpoint.path_params:
        path_param_names = set(endpoint.path_params.keys())

    query_param_names = set()
    if endpoint.query_params:
        query_param_names = set(endpoint.query_params.keys())

    for key, value in body.params.items():
        if key in path_param_names:
            resolved_path = resolved_path.replace(f"{{{key}}}", str(value))
        elif key in query_param_names:
            query_params[key] = value
        else:
            if body_params is None:
                body_params = {}
            body_params[key] = value

    method = endpoint.method.value if hasattr(endpoint.method, "value") else str(endpoint.method)
    risk_level = endpoint.risk_level.value if hasattr(endpoint.risk_level, "value") else str(endpoint.risk_level)

    return ToolTestResult(
        endpoint_id=endpoint.id,
        method=method,
        path=endpoint.path,
        resolved_path=resolved_path,
        query_params=query_params,
        body=body_params,
        risk_level=risk_level,
        would_require_permissions=endpoint.required_permissions,
    )


@router.put("/{endpoint_id}/config", dependencies=[AdminSettings])
async def update_tool_config(
    endpoint_id: str,
    body: ToolConfigUpdate,
    catalog_repo: CatalogRepo,
    settings_repo: SettingsRepo,
) -> dict[str, Any]:
    """Update tool configuration overrides (enabled, custom permissions).

    Overrides are stored as app settings with category ``tool_config``.
    """
    endpoint = await catalog_repo.get_endpoint(endpoint_id)
    if endpoint is None:
        raise HTTPException(
            status_code=404, detail=f"Tool endpoint '{endpoint_id}' not found"
        )

    # Load existing config
    config = await _get_tool_config(settings_repo, endpoint_id)

    # Apply updates
    if body.enabled is not None:
        config["enabled"] = body.enabled
    if body.required_permissions is not None:
        config["required_permissions"] = body.required_permissions

    # Persist
    await settings_repo.set_app_setting(
        f"tool_config:{endpoint_id}",
        json.dumps(config),
        category=_TOOL_CONFIG_CATEGORY,
    )

    return {
        "endpoint_id": endpoint_id,
        "config": config,
    }
