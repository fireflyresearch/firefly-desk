# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for built-in tools (registry and executor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.enums import HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.tools.builtin import (
    BUILTIN_SYSTEM_ID,
    BuiltinToolExecutor,
    BuiltinToolRegistry,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_system(system_id: str = "sys-1") -> ExternalSystem:
    return ExternalSystem(
        id=system_id,
        name=f"System {system_id}",
        description="Test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(
            auth_type="bearer",
            credential_id="cred-1",
        ),
        status=SystemStatus.ACTIVE,
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


@pytest.fixture
def catalog_repo() -> MagicMock:
    mock = MagicMock()
    mock.list_systems = AsyncMock(return_value=[_make_system()])
    mock.list_endpoints = AsyncMock(return_value=[_make_endpoint()])
    return mock


@pytest.fixture
def audit_logger() -> MagicMock:
    mock = MagicMock()
    mock.query = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def knowledge_retriever() -> MagicMock:
    mock = MagicMock()
    mock.retrieve = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def executor(catalog_repo, audit_logger, knowledge_retriever) -> BuiltinToolExecutor:
    return BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
        knowledge_retriever=knowledge_retriever,
    )


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestBuiltinToolRegistry:
    def test_admin_gets_all_tools(self):
        """Admin user with * permission gets all built-in tools."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        names = {t.name for t in tools}
        assert "search_knowledge" in names
        assert "list_catalog_systems" in names
        assert "list_system_endpoints" in names
        assert "query_audit_log" in names
        assert "get_platform_status" in names

    def test_viewer_gets_platform_status_only(self):
        """User with no special permissions gets only platform status."""
        tools = BuiltinToolRegistry.get_tool_definitions([])
        names = {t.name for t in tools}
        assert names == {"get_platform_status"}

    def test_knowledge_permission_grants_search(self):
        """knowledge:read permission grants search_knowledge tool."""
        tools = BuiltinToolRegistry.get_tool_definitions(["knowledge:read"])
        names = {t.name for t in tools}
        assert "search_knowledge" in names
        assert "get_platform_status" in names
        assert "list_catalog_systems" not in names

    def test_catalog_permission_grants_browse(self):
        """catalog:read permission grants catalog browsing tools."""
        tools = BuiltinToolRegistry.get_tool_definitions(["catalog:read"])
        names = {t.name for t in tools}
        assert "list_catalog_systems" in names
        assert "list_system_endpoints" in names

    def test_audit_permission_grants_log_access(self):
        """audit:read permission grants audit log tool."""
        tools = BuiltinToolRegistry.get_tool_definitions(["audit:read"])
        names = {t.name for t in tools}
        assert "query_audit_log" in names

    def test_all_tools_use_builtin_system_id(self):
        """All built-in tools have the __flydesk__ system ID."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.system_id == BUILTIN_SYSTEM_ID

    def test_all_tools_are_read_risk(self):
        """All built-in tools are READ risk level."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.risk_level == RiskLevel.READ


# ---------------------------------------------------------------------------
# Executor tests
# ---------------------------------------------------------------------------


class TestBuiltinToolExecutor:
    def test_is_builtin(self, executor):
        assert executor.is_builtin("__builtin__search_knowledge") is True
        assert executor.is_builtin("__builtin__list_systems") is True
        assert executor.is_builtin("ep-1") is False
        assert executor.is_builtin("custom-endpoint") is False

    async def test_unknown_tool_returns_error(self, executor):
        result = await executor.execute("unknown_tool", {})
        assert "error" in result
        assert "Unknown" in result["error"]


class TestListSystems:
    async def test_returns_systems(self, executor, catalog_repo):
        result = await executor.execute("list_catalog_systems", {})
        assert result["count"] == 1
        assert result["systems"][0]["name"] == "System sys-1"
        assert result["systems"][0]["status"] == "active"

    async def test_empty_catalog(self, executor, catalog_repo):
        catalog_repo.list_systems.return_value = []
        result = await executor.execute("list_catalog_systems", {})
        assert result["count"] == 0
        assert result["systems"] == []


class TestListEndpoints:
    async def test_returns_endpoints_for_system(self, executor, catalog_repo):
        result = await executor.execute(
            "list_system_endpoints", {"system_id": "sys-1"}
        )
        assert result["count"] == 1
        assert result["endpoints"][0]["name"] == "Get Orders"
        assert result["endpoints"][0]["method"] == "GET"

    async def test_filters_by_system_id(self, executor, catalog_repo):
        """Endpoints from other systems are not returned."""
        result = await executor.execute(
            "list_system_endpoints", {"system_id": "sys-other"}
        )
        assert result["count"] == 0

    async def test_missing_system_id_returns_error(self, executor):
        result = await executor.execute("list_system_endpoints", {})
        assert "error" in result


class TestQueryAudit:
    async def test_returns_events(self, executor, audit_logger):
        result = await executor.execute("query_audit_log", {"limit": 10})
        assert result["count"] == 0
        assert result["events"] == []
        audit_logger.query.assert_awaited_once_with(limit=10, event_type=None)

    async def test_default_limit(self, executor, audit_logger):
        await executor.execute("query_audit_log", {})
        audit_logger.query.assert_awaited_once_with(limit=20, event_type=None)


class TestSearchKnowledge:
    async def test_requires_query(self, executor):
        result = await executor.execute("search_knowledge", {})
        assert "error" in result

    async def test_returns_results(self, executor, knowledge_retriever):
        # Set up a mock snippet
        snippet = MagicMock()
        snippet.document_title = "API Guide"
        snippet.chunk = MagicMock()
        snippet.chunk.content = "How to authenticate with the API"
        snippet.score = 0.95
        knowledge_retriever.retrieve.return_value = [snippet]

        result = await executor.execute(
            "search_knowledge", {"query": "authentication"}
        )
        assert result["count"] == 1
        assert result["results"][0]["document_title"] == "API Guide"
        assert result["results"][0]["score"] == 0.95

    async def test_no_retriever_returns_error(self, catalog_repo, audit_logger):
        executor = BuiltinToolExecutor(
            catalog_repo=catalog_repo,
            audit_logger=audit_logger,
            knowledge_retriever=None,
        )
        result = await executor.execute(
            "search_knowledge", {"query": "test"}
        )
        assert "error" in result
        assert "not configured" in result["error"]


class TestPlatformStatus:
    async def test_returns_counts(self, executor, catalog_repo):
        result = await executor.execute("get_platform_status", {})
        assert result["systems_count"] == 1
        assert result["endpoints_count"] == 1
        assert len(result["systems"]) == 1
        assert result["systems"][0]["name"] == "System sys-1"
