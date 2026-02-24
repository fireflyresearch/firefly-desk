# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the OpenAPI Import REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _sample_openapi_spec() -> dict:
    """Return a minimal valid OpenAPI 3.0 spec dict."""
    return {
        "openapi": "3.0.0",
        "info": {
            "title": "Pet Store API",
            "description": "A sample pet store API",
            "version": "1.0.0",
        },
        "servers": [{"url": "https://petstore.example.com/v1"}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                }
            }
        },
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "summary": "List all pets",
                    "description": "Returns all pets in the store",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "description": "Max items to return",
                            "schema": {"type": "integer"},
                        }
                    ],
                },
                "post": {
                    "operationId": "createPet",
                    "summary": "Create a pet",
                    "tags": ["pets"],
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                    },
                                }
                            }
                        }
                    },
                },
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "getPet",
                    "summary": "Get a pet by ID",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "description": "The pet ID",
                            "schema": {"type": "string"},
                        }
                    ],
                },
                "delete": {
                    "operationId": "deletePet",
                    "summary": "Delete a pet",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "description": "The pet ID",
                            "schema": {"type": "string"},
                        }
                    ],
                },
            },
        },
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics CatalogRepository."""
    repo = AsyncMock()
    repo.create_system = AsyncMock(return_value=None)
    repo.create_endpoint = AsyncMock(return_value=None)
    repo.get_system = AsyncMock(return_value=None)
    repo.list_systems = AsyncMock(return_value=[])
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked CatalogRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.openapi_import import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def non_admin_client(mock_repo):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.openapi_import import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        viewer_session = _make_user_session(roles=["viewer"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Parse endpoint tests
# ---------------------------------------------------------------------------


class TestParseSpec:
    """Tests for POST /api/catalog/import/openapi/parse."""

    async def test_parse_valid_spec(self, admin_client):
        spec = _sample_openapi_spec()
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={"spec": spec}
        )
        assert response.status_code == 200
        data = response.json()

        assert data["title"] == "Pet Store API"
        assert data["description"] == "A sample pet store API"
        assert data["version"] == "1.0.0"
        assert data["base_url"] == "https://petstore.example.com/v1"
        assert len(data["auth_schemes"]) == 1
        assert data["auth_schemes"][0]["name"] == "bearerAuth"

        # 4 endpoints: GET /pets, POST /pets, GET /pets/{petId}, DELETE /pets/{petId}
        assert len(data["endpoints"]) == 4

        # Check specific endpoint details
        list_pets = next(
            ep for ep in data["endpoints"]
            if ep["operation_id"] == "listPets"
        )
        assert list_pets["method"] == "GET"
        assert list_pets["path"] == "/pets"
        assert len(list_pets["parameters"]) == 1
        assert list_pets["parameters"][0]["name"] == "limit"

    async def test_parse_spec_missing_title(self, admin_client):
        spec = {
            "openapi": "3.0.0",
            "info": {},
            "paths": {},
        }
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={"spec": spec}
        )
        assert response.status_code == 400
        assert "title" in response.json()["detail"].lower()

    async def test_parse_no_spec_or_url(self, admin_client):
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={}
        )
        assert response.status_code == 400
        assert "spec" in response.json()["detail"].lower()

    async def test_parse_url_not_supported(self, admin_client):
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse",
            json={"url": "https://example.com/openapi.json"},
        )
        assert response.status_code == 501
        assert "not yet supported" in response.json()["detail"].lower()

    async def test_parse_returns_request_body_schema(self, admin_client):
        spec = _sample_openapi_spec()
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={"spec": spec}
        )
        data = response.json()
        create_pet = next(
            ep for ep in data["endpoints"]
            if ep["operation_id"] == "createPet"
        )
        assert create_pet["request_body_schema"] is not None
        assert create_pet["request_body_schema"]["type"] == "object"

    async def test_parse_returns_tags(self, admin_client):
        spec = _sample_openapi_spec()
        response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={"spec": spec}
        )
        data = response.json()
        for ep in data["endpoints"]:
            assert "pets" in ep["tags"]


# ---------------------------------------------------------------------------
# Confirm endpoint tests
# ---------------------------------------------------------------------------


class TestConfirmImport:
    """Tests for POST /api/catalog/import/openapi/confirm."""

    async def test_confirm_creates_system_and_endpoints(self, admin_client, mock_repo):
        spec = _sample_openapi_spec()

        # First parse the spec
        parse_response = await admin_client.post(
            "/api/catalog/import/openapi/parse", json={"spec": spec}
        )
        parsed = parse_response.json()

        # Select two endpoints to import
        selected = [
            {
                "path": "/pets",
                "method": "GET",
                "operation_id": "listPets",
                "summary": "List all pets",
                "description": "Returns all pets in the store",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "description": "Max items to return",
                        "type": "integer",
                    }
                ],
                "tags": ["pets"],
            },
            {
                "path": "/pets",
                "method": "POST",
                "operation_id": "createPet",
                "summary": "Create a pet",
                "tags": ["pets"],
                "request_body_schema": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                },
            },
        ]

        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": parsed,
                "selected_endpoints": selected,
                "auth_type": "bearer",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "system_id" in data
        assert data["endpoint_count"] == 2

        # Verify repo was called
        mock_repo.create_system.assert_awaited_once()
        created_system = mock_repo.create_system.call_args[0][0]
        assert created_system.status.value == "draft"
        assert created_system.name == "Pet Store API"
        assert "openapi-import" in created_system.tags

        # Two endpoints created
        assert mock_repo.create_endpoint.await_count == 2

    async def test_confirm_with_system_name_override(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {
                    "title": "Pet Store API",
                    "description": "Original description",
                    "base_url": "https://petstore.example.com",
                },
                "selected_endpoints": [
                    {
                        "path": "/pets",
                        "method": "GET",
                        "summary": "List pets",
                    }
                ],
                "system_name": "My Custom Name",
                "auth_type": "api_key",
            },
        )
        assert response.status_code == 201

        created_system = mock_repo.create_system.call_args[0][0]
        assert created_system.name == "My Custom Name"
        assert created_system.auth_config is not None
        assert created_system.auth_config.auth_type.value == "api_key"

    async def test_confirm_missing_title_in_parsed_spec(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {"description": "No title here"},
                "selected_endpoints": [],
            },
        )
        assert response.status_code == 400
        assert "title" in response.json()["detail"].lower()

    async def test_confirm_invalid_auth_type(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {"title": "Test API"},
                "selected_endpoints": [],
                "auth_type": "invalid_auth",
            },
        )
        assert response.status_code == 400
        assert "auth_type" in response.json()["detail"].lower()

    async def test_confirm_no_auth_creates_system_without_auth_config(
        self, admin_client, mock_repo
    ):
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {
                    "title": "Public API",
                    "base_url": "https://api.example.com",
                },
                "selected_endpoints": [],
                "auth_type": "none",
            },
        )
        assert response.status_code == 201

        created_system = mock_repo.create_system.call_args[0][0]
        assert created_system.auth_config is None

    async def test_confirm_endpoint_risk_levels(self, admin_client, mock_repo):
        """GET endpoints get READ risk; DELETE gets DESTRUCTIVE; POST gets LOW_WRITE."""
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {
                    "title": "Risk Test API",
                    "base_url": "https://api.example.com",
                },
                "selected_endpoints": [
                    {"path": "/items", "method": "GET", "summary": "List items"},
                    {"path": "/items", "method": "POST", "summary": "Create item"},
                    {"path": "/items/{id}", "method": "DELETE", "summary": "Delete item"},
                ],
            },
        )
        assert response.status_code == 201
        assert mock_repo.create_endpoint.await_count == 3

        endpoints_created = [
            call[0][0] for call in mock_repo.create_endpoint.call_args_list
        ]
        risk_by_method = {ep.method.value: ep.risk_level.value for ep in endpoints_created}
        assert risk_by_method["GET"] == "read"
        assert risk_by_method["POST"] == "low_write"
        assert risk_by_method["DELETE"] == "destructive"

    async def test_confirm_with_empty_endpoints(self, admin_client, mock_repo):
        """System is created even when no endpoints are selected."""
        response = await admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {
                    "title": "Empty API",
                    "base_url": "https://api.example.com",
                },
                "selected_endpoints": [],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["endpoint_count"] == 0
        mock_repo.create_system.assert_awaited_once()
        mock_repo.create_endpoint.assert_not_awaited()


# ---------------------------------------------------------------------------
# RBAC guard tests
# ---------------------------------------------------------------------------


class TestOpenAPIImportRBAC:
    """Non-admin users should be denied access."""

    async def test_non_admin_cannot_parse(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/catalog/import/openapi/parse",
            json={"spec": _sample_openapi_spec()},
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_confirm(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/catalog/import/openapi/confirm",
            json={
                "parsed_spec": {"title": "Test"},
                "selected_endpoints": [],
            },
        )
        assert response.status_code == 403
