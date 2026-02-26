# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for built-in tools (registry and executor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.enums import HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.processes.models import BusinessProcess, ProcessStep
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
    mock.list_systems = AsyncMock(return_value=([_make_system()], 1))
    mock.list_endpoints = AsyncMock(return_value=[_make_endpoint()])
    mock.list_active_endpoints = AsyncMock(return_value=[_make_endpoint()])
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
def process_repo() -> MagicMock:
    mock = MagicMock()
    mock.list = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def executor(catalog_repo, audit_logger, knowledge_retriever, process_repo) -> BuiltinToolExecutor:
    return BuiltinToolExecutor(
        catalog_repo=catalog_repo,
        audit_logger=audit_logger,
        knowledge_retriever=knowledge_retriever,
        process_repo=process_repo,
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
        assert "search_processes" in names

    def test_viewer_gets_platform_status_and_transform_tools(self):
        """User with no special permissions gets platform status + memory + transform tools."""
        tools = BuiltinToolRegistry.get_tool_definitions([])
        names = {t.name for t in tools}
        assert names == {
            "get_platform_status",
            "save_memory",
            "recall_memories",
            "grep_result",
            "parse_json",
            "filter_rows",
            "transform_data",
        }

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

    def test_processes_permission_grants_search(self):
        """processes:read permission grants search_processes tool."""
        tools = BuiltinToolRegistry.get_tool_definitions(["processes:read"])
        names = {t.name for t in tools}
        assert "search_processes" in names
        assert "get_platform_status" in names
        assert "list_catalog_systems" not in names

    def test_all_tools_use_builtin_system_id(self):
        """All built-in tools have the __flydesk__ system ID."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.system_id == BUILTIN_SYSTEM_ID

    def test_all_tools_are_read_or_low_write_risk(self):
        """All built-in tools are READ or LOW_WRITE risk level."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.risk_level in (RiskLevel.READ, RiskLevel.LOW_WRITE)

    def test_knowledge_read_grants_document_read_not_write(self):
        """knowledge:read grants document_read and document_convert but NOT document_create or document_modify."""
        tools = BuiltinToolRegistry.get_tool_definitions(["knowledge:read"])
        names = {t.name for t in tools}
        assert "document_read" in names
        assert "document_convert" in names
        assert "document_create" not in names
        assert "document_modify" not in names

    def test_knowledge_write_grants_document_write(self):
        """knowledge:write grants document_create and document_modify."""
        tools = BuiltinToolRegistry.get_tool_definitions(["knowledge:write"])
        names = {t.name for t in tools}
        assert "document_create" in names
        assert "document_modify" in names

    def test_knowledge_read_and_write_grants_all_document_tools(self):
        """Both knowledge:read and knowledge:write together grant all 4 document tools."""
        tools = BuiltinToolRegistry.get_tool_definitions(["knowledge:read", "knowledge:write"])
        names = {t.name for t in tools}
        assert "document_read" in names
        assert "document_convert" in names
        assert "document_create" in names
        assert "document_modify" in names


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
        catalog_repo.list_systems.return_value = ([], 0)
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
        catalog_repo.list_endpoints.assert_awaited_once_with("sys-1")

    async def test_filters_by_system_id(self, executor, catalog_repo):
        """Filtering is done at the DB level via system_id argument."""
        catalog_repo.list_endpoints.return_value = []
        result = await executor.execute(
            "list_system_endpoints", {"system_id": "sys-other"}
        )
        assert result["count"] == 0
        catalog_repo.list_endpoints.assert_awaited_once_with("sys-other")

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
        catalog_repo.list_active_endpoints.assert_awaited_once()


# ---------------------------------------------------------------------------
# Search Processes tests
# ---------------------------------------------------------------------------


def _make_process(
    process_id: str = "proc-1",
    name: str = "Order Fulfillment",
    description: str = "End-to-end order processing workflow",
    steps: list[ProcessStep] | None = None,
) -> BusinessProcess:
    if steps is None:
        steps = [
            ProcessStep(id="s1", name="Validate Order", description="Check order details and inventory"),
            ProcessStep(id="s2", name="Process Payment", description="Charge the customer credit card"),
            ProcessStep(id="s3", name="Ship Order", description="Send the package via courier"),
        ]
    return BusinessProcess(
        id=process_id,
        name=name,
        description=description,
        steps=steps,
    )


class TestSearchProcesses:
    async def test_requires_query(self, executor):
        """Empty query returns error."""
        result = await executor.execute("search_processes", {})
        assert "error" in result

    async def test_no_repo_returns_error(self, catalog_repo, audit_logger, knowledge_retriever):
        """When process_repo is None, returns an error."""
        executor = BuiltinToolExecutor(
            catalog_repo=catalog_repo,
            audit_logger=audit_logger,
            knowledge_retriever=knowledge_retriever,
            process_repo=None,
        )
        result = await executor.execute("search_processes", {"query": "order"})
        assert "error" in result
        assert "not configured" in result["error"]

    async def test_returns_matching_processes(self, executor, process_repo):
        """Processes matching the query are returned with scores."""
        process_repo.list.return_value = [
            _make_process("proc-1", "Order Fulfillment", "End-to-end order processing"),
            _make_process(
                "proc-2", "Customer Onboarding", "New customer setup workflow",
                steps=[ProcessStep(id="s1", name="Welcome", description="Send welcome email")],
            ),
        ]
        result = await executor.execute("search_processes", {"query": "order"})
        assert result["total_matches"] == 1
        assert len(result["processes"]) == 1
        assert result["processes"][0]["name"] == "Order Fulfillment"

    async def test_name_match_scores_higher_than_description(self, executor, process_repo):
        """A name match (score +2) ranks above a description-only match (score +1)."""
        process_repo.list.return_value = [
            _make_process("proc-1", "Invoice Generator", "Creates invoices for orders"),
            _make_process("proc-2", "Order Fulfillment", "End-to-end processing"),
        ]
        result = await executor.execute("search_processes", {"query": "order"})
        assert result["total_matches"] == 2
        # "Order Fulfillment" has name match (score=2), "Invoice Generator" has description match (score=1)
        assert result["processes"][0]["name"] == "Order Fulfillment"
        assert result["processes"][1]["name"] == "Invoice Generator"

    async def test_step_description_contributes_to_score(self, executor, process_repo):
        """Step descriptions add 0.5 to the score per matching step."""
        process_repo.list.return_value = [
            _make_process(
                "proc-1",
                "Generic Workflow",
                "A generic workflow",
                steps=[
                    ProcessStep(id="s1", name="Step 1", description="Ship the package"),
                    ProcessStep(id="s2", name="Step 2", description="Ship the backup"),
                ],
            ),
        ]
        result = await executor.execute("search_processes", {"query": "ship"})
        assert result["total_matches"] == 1
        # Two step matches = 0.5 + 0.5 = 1.0
        assert result["processes"][0]["confidence"] == 1.0

    async def test_limits_to_three_results(self, executor, process_repo):
        """At most 3 processes are returned."""
        process_repo.list.return_value = [
            _make_process(f"proc-{i}", f"Order Process {i}", "Handles orders")
            for i in range(10)
        ]
        result = await executor.execute("search_processes", {"query": "order"})
        assert result["total_matches"] == 10
        assert len(result["processes"]) == 3

    async def test_no_matches_returns_empty(self, executor, process_repo):
        """When no processes match, empty list is returned."""
        process_repo.list.return_value = [
            _make_process("proc-1", "Order Fulfillment", "End-to-end order processing"),
        ]
        result = await executor.execute("search_processes", {"query": "payroll"})
        assert result["total_matches"] == 0
        assert result["processes"] == []

    async def test_returns_step_details(self, executor, process_repo):
        """Each result includes step name, description, and endpoint_id."""
        proc = _make_process()
        proc.steps[0].endpoint_id = "ep-validate"
        process_repo.list.return_value = [proc]
        result = await executor.execute("search_processes", {"query": "order"})
        steps = result["processes"][0]["steps"]
        assert len(steps) == 3
        assert steps[0]["name"] == "Validate Order"
        assert steps[0]["endpoint_id"] == "ep-validate"
        assert steps[1]["name"] == "Process Payment"
