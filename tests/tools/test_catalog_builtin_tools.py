# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for catalog write tools: create_catalog_system, update_catalog_system, create_system_endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.tools.builtin import BuiltinToolExecutor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_system(
    system_id: str = "sys-1",
    name: str | None = None,
    status: SystemStatus = SystemStatus.ACTIVE,
    tags: list[str] | None = None,
) -> ExternalSystem:
    return ExternalSystem(
        id=system_id,
        name=name or f"System {system_id}",
        description="Test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(auth_type=AuthType.BEARER, credential_id="cred-1"),
        status=status,
        tags=tags or [],
    )


def _make_endpoint(
    endpoint_id: str = "ep-1", system_id: str = "sys-1"
) -> ServiceEndpoint:
    return ServiceEndpoint(
        id=endpoint_id,
        system_id=system_id,
        name="Get Orders",
        description="Fetch customer orders",
        method=HttpMethod.GET,
        path="/orders",
        when_to_use="When the user asks about orders",
        risk_level=RiskLevel.READ,
        required_permissions=["orders:read"],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def catalog_repo() -> MagicMock:
    mock = MagicMock()
    mock.list_systems = AsyncMock(return_value=[_make_system()])
    mock.list_endpoints = AsyncMock(return_value=[_make_endpoint()])
    mock.create_system = AsyncMock()
    mock.get_system = AsyncMock(side_effect=lambda sid: _make_system(sid) if sid == "sys-1" else None)
    mock.update_system = AsyncMock()
    mock.create_endpoint = AsyncMock()
    return mock


@pytest.fixture
def audit_logger() -> MagicMock:
    mock = MagicMock()
    mock.query = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def executor(catalog_repo, audit_logger) -> BuiltinToolExecutor:
    return BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
    )


# ---------------------------------------------------------------------------
# Tests: create_catalog_system
# ---------------------------------------------------------------------------


class TestCreateCatalogSystem:
    async def test_missing_name_returns_error(self, executor):
        """Empty name returns an error."""
        result = await executor.execute("create_catalog_system", {})
        assert "error" in result
        assert "name" in result["error"].lower()

    async def test_blank_name_returns_error(self, executor):
        """Whitespace-only name returns an error."""
        result = await executor.execute("create_catalog_system", {"name": "   "})
        assert "error" in result

    async def test_valid_input_creates_draft_system(self, executor, catalog_repo):
        """A valid name creates a DRAFT system with expected metadata."""
        result = await executor.execute(
            "create_catalog_system",
            {"name": "New CRM", "description": "Customer management", "base_url": "https://crm.example.com"},
        )
        assert "error" not in result
        assert result["status"] == "draft"
        assert result["name"] == "New CRM"
        assert result["system_id"]  # UUID assigned

        # Verify the system was passed to the repo
        catalog_repo.create_system.assert_awaited_once()
        created_system: ExternalSystem = catalog_repo.create_system.call_args[0][0]
        assert created_system.status == SystemStatus.DRAFT
        assert created_system.metadata == {"source": "agent_tool"}
        assert created_system.agent_enabled is False

    async def test_tags_parsed_from_csv(self, executor, catalog_repo):
        """Comma-separated tags string is parsed into a list."""
        await executor.execute(
            "create_catalog_system",
            {"name": "Tagged System", "tags": "crm,production, sales "},
        )
        catalog_repo.create_system.assert_awaited_once()
        created_system: ExternalSystem = catalog_repo.create_system.call_args[0][0]
        assert created_system.tags == ["crm", "production", "sales"]

    async def test_empty_tags_string_gives_empty_list(self, executor, catalog_repo):
        """Empty tags string results in empty tags list."""
        await executor.execute(
            "create_catalog_system",
            {"name": "No Tags", "tags": ""},
        )
        created_system: ExternalSystem = catalog_repo.create_system.call_args[0][0]
        assert created_system.tags == []

    async def test_auth_type_validated_invalid(self, executor):
        """Invalid auth_type returns an error listing valid values."""
        result = await executor.execute(
            "create_catalog_system",
            {"name": "Bad Auth", "auth_type": "kerberos"},
        )
        assert "error" in result
        assert "kerberos" in result["error"]
        # Should list valid values
        for valid in AuthType:
            assert valid.value in result["error"]

    async def test_auth_type_validated_valid(self, executor, catalog_repo):
        """Valid auth_type is accepted and stored."""
        await executor.execute(
            "create_catalog_system",
            {"name": "OAuth System", "auth_type": "oauth2"},
        )
        created_system: ExternalSystem = catalog_repo.create_system.call_args[0][0]
        assert created_system.auth_config.auth_type == AuthType.OAUTH2

    async def test_default_auth_type_is_none(self, executor, catalog_repo):
        """When no auth_type provided, defaults to 'none'."""
        await executor.execute(
            "create_catalog_system",
            {"name": "Default Auth"},
        )
        created_system: ExternalSystem = catalog_repo.create_system.call_args[0][0]
        assert created_system.auth_config.auth_type == AuthType.NONE


# ---------------------------------------------------------------------------
# Tests: update_catalog_system
# ---------------------------------------------------------------------------


class TestUpdateCatalogSystem:
    async def test_missing_system_id_returns_error(self, executor):
        """Empty system_id returns an error."""
        result = await executor.execute("update_catalog_system", {})
        assert "error" in result
        assert "system_id" in result["error"].lower()

    async def test_blank_system_id_returns_error(self, executor):
        """Whitespace-only system_id returns an error."""
        result = await executor.execute(
            "update_catalog_system", {"system_id": "  "}
        )
        assert "error" in result

    async def test_nonexistent_system_id_returns_error(self, executor):
        """System ID not found in repo returns an error."""
        result = await executor.execute(
            "update_catalog_system",
            {"system_id": "does-not-exist", "name": "New Name"},
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    async def test_valid_update_changes_name(self, executor, catalog_repo):
        """Updating name changes only the name field."""
        result = await executor.execute(
            "update_catalog_system",
            {"system_id": "sys-1", "name": "Renamed System"},
        )
        assert "error" not in result
        assert result["name"] == "Renamed System"

        catalog_repo.update_system.assert_awaited_once()
        updated: ExternalSystem = catalog_repo.update_system.call_args[0][0]
        assert updated.name == "Renamed System"
        # Other fields unchanged
        assert updated.description == "Test system"
        assert updated.base_url == "https://api.example.com"

    async def test_valid_update_changes_description(self, executor, catalog_repo):
        """Updating description preserves other fields."""
        await executor.execute(
            "update_catalog_system",
            {"system_id": "sys-1", "description": "New description"},
        )
        updated: ExternalSystem = catalog_repo.update_system.call_args[0][0]
        assert updated.description == "New description"
        assert updated.name == "System sys-1"  # unchanged

    async def test_valid_update_changes_tags(self, executor, catalog_repo):
        """Updating tags parses CSV and replaces existing tags."""
        await executor.execute(
            "update_catalog_system",
            {"system_id": "sys-1", "tags": "new-tag, another"},
        )
        updated: ExternalSystem = catalog_repo.update_system.call_args[0][0]
        assert updated.tags == ["new-tag", "another"]

    async def test_fields_not_provided_are_unchanged(self, executor, catalog_repo):
        """When only one field is provided, other fields remain unchanged."""
        await executor.execute(
            "update_catalog_system",
            {"system_id": "sys-1", "base_url": "https://new-url.com"},
        )
        updated: ExternalSystem = catalog_repo.update_system.call_args[0][0]
        assert updated.base_url == "https://new-url.com"
        assert updated.name == "System sys-1"
        assert updated.description == "Test system"


# ---------------------------------------------------------------------------
# Tests: create_system_endpoint
# ---------------------------------------------------------------------------


class TestCreateSystemEndpoint:
    async def test_missing_system_id_returns_error(self, executor):
        """Missing system_id returns an error."""
        result = await executor.execute(
            "create_system_endpoint",
            {"name": "Ep", "method": "GET", "path": "/test"},
        )
        assert "error" in result
        assert "system_id" in result["error"].lower()

    async def test_missing_name_returns_error(self, executor):
        """Missing name returns an error."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "method": "GET", "path": "/test"},
        )
        assert "error" in result
        assert "name" in result["error"].lower()

    async def test_missing_method_returns_error(self, executor):
        """Missing method returns an error."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "name": "Ep", "path": "/test"},
        )
        assert "error" in result
        assert "method" in result["error"].lower()

    async def test_missing_path_returns_error(self, executor):
        """Missing path returns an error."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "name": "Ep", "method": "GET"},
        )
        assert "error" in result
        assert "path" in result["error"].lower()

    async def test_nonexistent_system_id_returns_error(self, executor):
        """System ID that doesn't exist returns an error."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "no-such-sys", "name": "Ep", "method": "GET", "path": "/test"},
        )
        assert "error" in result
        assert "not found" in result["error"].lower()

    async def test_valid_input_creates_endpoint(self, executor, catalog_repo):
        """Valid input creates an endpoint and returns details."""
        result = await executor.execute(
            "create_system_endpoint",
            {
                "system_id": "sys-1",
                "name": "Create User",
                "method": "POST",
                "path": "/users",
                "description": "Creates a new user",
                "when_to_use": "When a new user needs to be created",
                "risk_level": "low_write",
            },
        )
        assert "error" not in result
        assert result["name"] == "Create User"
        assert result["method"] == "POST"
        assert result["path"] == "/users"
        assert result["system_id"] == "sys-1"
        assert result["endpoint_id"]  # UUID assigned

        catalog_repo.create_endpoint.assert_awaited_once()
        created: ServiceEndpoint = catalog_repo.create_endpoint.call_args[0][0]
        assert created.system_id == "sys-1"
        assert created.name == "Create User"
        assert created.method == HttpMethod.POST
        assert created.path == "/users"
        assert created.risk_level == RiskLevel.LOW_WRITE

    async def test_invalid_method_returns_error(self, executor):
        """Invalid HTTP method returns an error listing valid methods."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "name": "Ep", "method": "INVALID", "path": "/test"},
        )
        assert "error" in result
        assert "INVALID" in result["error"]
        # Should list valid methods
        for method in HttpMethod:
            assert method.value in result["error"]

    async def test_method_case_insensitive(self, executor, catalog_repo):
        """HTTP method is normalized to uppercase."""
        result = await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "name": "Ep", "method": "get", "path": "/test"},
        )
        assert "error" not in result
        assert result["method"] == "GET"

    async def test_default_risk_level_is_read(self, executor, catalog_repo):
        """When no risk_level is provided, defaults to 'read'."""
        await executor.execute(
            "create_system_endpoint",
            {"system_id": "sys-1", "name": "Ep", "method": "GET", "path": "/test"},
        )
        created: ServiceEndpoint = catalog_repo.create_endpoint.call_args[0][0]
        assert created.risk_level == RiskLevel.READ

    async def test_invalid_risk_level_returns_error(self, executor):
        """Invalid risk_level returns an error listing valid values."""
        result = await executor.execute(
            "create_system_endpoint",
            {
                "system_id": "sys-1",
                "name": "Ep",
                "method": "GET",
                "path": "/test",
                "risk_level": "extreme",
            },
        )
        assert "error" in result
        assert "extreme" in result["error"]
        for level in RiskLevel:
            assert level.value in result["error"]
