# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""OpenAPI 3.x spec parser for catalog auto-import."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedEndpoint:
    """An endpoint extracted from an OpenAPI spec."""

    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    operation_id: str | None = None
    summary: str = ""
    description: str = ""
    parameters: list[dict[str, Any]] = field(default_factory=list)  # path + query params
    request_body_schema: dict[str, Any] | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ParsedAPI:
    """Result of parsing an OpenAPI spec."""

    title: str
    description: str = ""
    version: str = ""
    base_url: str = ""
    auth_schemes: list[dict[str, Any]] = field(default_factory=list)
    endpoints: list[ParsedEndpoint] = field(default_factory=list)


def parse_openapi_spec(spec: dict[str, Any]) -> ParsedAPI:
    """Parse an OpenAPI 3.x spec dict into a ParsedAPI.

    Args:
        spec: A parsed OpenAPI 3.x spec (from JSON or YAML).

    Returns:
        ParsedAPI with extracted system info and endpoints.

    Raises:
        ValueError: If the spec is missing required fields.
    """
    info = spec.get("info", {})
    if not info.get("title"):
        raise ValueError("OpenAPI spec missing 'info.title'")

    title = info["title"]
    description = info.get("description", "")
    version = info.get("version", "")

    # Extract base URL from servers
    servers = spec.get("servers", [])
    base_url = servers[0]["url"] if servers else ""

    # Extract auth schemes
    auth_schemes = []
    components = spec.get("components", {})
    security_schemes = components.get("securitySchemes", {})
    for scheme_name, scheme_def in security_schemes.items():
        auth_schemes.append({
            "name": scheme_name,
            "type": scheme_def.get("type", ""),
            "scheme": scheme_def.get("scheme", ""),
            "in": scheme_def.get("in", ""),
            "flows": scheme_def.get("flows", {}),
        })

    # Parse paths
    endpoints = []
    paths = spec.get("paths", {})
    for path, path_item in paths.items():
        for method in ("get", "post", "put", "delete", "patch"):
            operation = path_item.get(method)
            if operation is None:
                continue

            # Collect parameters (path-level + operation-level)
            params = []
            for p in path_item.get("parameters", []):
                params.append(_normalize_param(p))
            for p in operation.get("parameters", []):
                params.append(_normalize_param(p))

            # Request body
            body_schema = None
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema")

            endpoints.append(ParsedEndpoint(
                path=path,
                method=method.upper(),
                operation_id=operation.get("operationId"),
                summary=operation.get("summary", ""),
                description=operation.get("description", ""),
                parameters=params,
                request_body_schema=body_schema,
                tags=operation.get("tags", []),
            ))

    return ParsedAPI(
        title=title,
        description=description,
        version=version,
        base_url=base_url,
        auth_schemes=auth_schemes,
        endpoints=endpoints,
    )


def _normalize_param(param: dict[str, Any]) -> dict[str, Any]:
    """Normalize an OpenAPI parameter to a consistent structure."""
    return {
        "name": param.get("name", ""),
        "in": param.get("in", ""),  # path, query, header, cookie
        "required": param.get("required", False),
        "description": param.get("description", ""),
        "type": param.get("schema", {}).get("type", "string"),
    }
