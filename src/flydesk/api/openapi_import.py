# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""OpenAPI Import REST API -- parse specs and import as catalog systems."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import ExternalSystem, ServiceEndpoint
from flydesk.catalog.openapi_parser import parse_openapi_spec
from flydesk.catalog.repository import CatalogRepository
from flydesk.rbac.guards import CatalogWrite

router = APIRouter(prefix="/api/catalog/import/openapi", tags=["openapi-import"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_catalog_repo() -> CatalogRepository:
    """Provide a CatalogRepository instance.

    In production this is wired to the real database session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_catalog_repo must be overridden via app.dependency_overrides"
    )


Repo = Annotated[CatalogRepository, Depends(get_catalog_repo)]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ParseRequest(BaseModel):
    """Request body for the parse endpoint."""

    spec: dict[str, Any] | None = None
    url: str | None = None


class SelectedEndpoint(BaseModel):
    """An endpoint the user has selected to import."""

    path: str
    method: str
    operation_id: str | None = None
    summary: str = ""
    description: str = ""
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    request_body_schema: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    """Request body for the confirm/import endpoint."""

    parsed_spec: dict[str, Any]
    selected_endpoints: list[SelectedEndpoint]
    system_name: str | None = None
    auth_type: str = "none"


class ConfirmResponse(BaseModel):
    """Response for a successful import confirmation."""

    system_id: str
    endpoint_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


_METHOD_MAP: dict[str, HttpMethod] = {
    "GET": HttpMethod.GET,
    "POST": HttpMethod.POST,
    "PUT": HttpMethod.PUT,
    "PATCH": HttpMethod.PATCH,
    "DELETE": HttpMethod.DELETE,
}

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _risk_for_method(method: str) -> RiskLevel:
    """Derive a default risk level from the HTTP method."""
    if method == "GET":
        return RiskLevel.READ
    if method == "DELETE":
        return RiskLevel.DESTRUCTIVE
    return RiskLevel.LOW_WRITE


@router.post("/parse", dependencies=[CatalogWrite])
async def parse_spec(body: ParseRequest) -> dict[str, Any]:
    """Parse an OpenAPI spec and return a preview of the system and endpoints.

    Accepts either a raw ``spec`` dict or a ``url`` (URL support is reserved
    for a future release -- only ``spec`` is handled today).
    """
    if body.spec is None and body.url is None:
        raise HTTPException(
            status_code=400,
            detail="Either 'spec' or 'url' must be provided",
        )

    if body.url is not None and body.spec is None:
        raise HTTPException(
            status_code=501,
            detail="URL fetching is not yet supported. Please provide the spec directly.",
        )

    try:
        parsed = parse_openapi_spec(body.spec)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return asdict(parsed)


@router.post("/confirm", status_code=201, dependencies=[CatalogWrite])
async def confirm_import(body: ConfirmRequest, repo: Repo) -> ConfirmResponse:
    """Create an ExternalSystem in DRAFT status with selected endpoints.

    The caller provides the parsed spec metadata together with the endpoints
    they wish to import and optional overrides for the system name and auth
    type.
    """
    spec_info = body.parsed_spec
    if not spec_info.get("title"):
        raise HTTPException(
            status_code=400,
            detail="parsed_spec must include a 'title' field",
        )

    system_id = str(uuid.uuid4())

    # Resolve auth type
    try:
        auth_type = AuthType(body.auth_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid auth_type '{body.auth_type}'",
        )

    from flydesk.catalog.models import AuthConfig

    system = ExternalSystem(
        id=system_id,
        name=body.system_name or spec_info["title"],
        description=spec_info.get("description", ""),
        base_url=spec_info.get("base_url", ""),
        auth_config=AuthConfig(auth_type=auth_type) if auth_type != AuthType.NONE else None,
        tags=["openapi-import"],
        status=SystemStatus.DRAFT,
        metadata={
            "openapi_version": spec_info.get("version", ""),
            "import_source": "openapi",
        },
    )
    await repo.create_system(system)

    # Create selected endpoints
    for ep in body.selected_endpoints:
        method_upper = ep.method.upper()
        http_method = _METHOD_MAP.get(method_upper)
        if http_method is None:
            continue  # skip unknown methods

        # Build path and query param schemas from the parsed parameters
        path_params: dict[str, Any] = {}
        query_params: dict[str, Any] = {}
        for param in ep.parameters:
            param_schema = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
                "required": param.get("required", False),
            }
            if param.get("in") == "path":
                path_params[param["name"]] = param_schema
            elif param.get("in") == "query":
                query_params[param["name"]] = param_schema

        endpoint_id = str(uuid.uuid4())
        endpoint_name = ep.operation_id or f"{method_upper} {ep.path}"

        endpoint = ServiceEndpoint(
            id=endpoint_id,
            system_id=system_id,
            name=endpoint_name,
            description=ep.description or ep.summary or f"{method_upper} {ep.path}",
            method=http_method,
            path=ep.path,
            path_params=path_params or None,
            query_params=query_params or None,
            request_body=ep.request_body_schema,
            when_to_use=ep.summary or ep.description or f"Call {method_upper} {ep.path}",
            risk_level=_risk_for_method(method_upper),
            required_permissions=[],
            tags=ep.tags,
        )
        await repo.create_endpoint(endpoint)

    return ConfirmResponse(
        system_id=system_id,
        endpoint_count=len(body.selected_endpoints),
    )
