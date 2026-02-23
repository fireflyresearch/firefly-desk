# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the genai adapter layer (CatalogToolAdapter, _build_parameter_specs, adapt_tools)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from fireflyframework_genai.exceptions import ToolError
from fireflyframework_genai.tools.base import BaseTool, ParameterSpec

from flydesk.auth.models import UserSession
from flydesk.catalog.enums import RiskLevel
from flydesk.tools.executor import ToolCall, ToolExecutor, ToolResult
from flydesk.tools.factory import ToolDefinition
from flydesk.tools.genai_adapter import (
    CatalogToolAdapter,
    _build_parameter_specs,
    _nest_arguments,
    adapt_tools,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user_session() -> UserSession:
    return UserSession(
        user_id="user-42",
        email="alice@example.com",
        display_name="Alice Smith",
        roles=["admin"],
        permissions=["orders:read", "orders:write"],
        tenant_id="tenant-1",
        session_id="sess-abc",
        token_expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        raw_claims={},
    )


@pytest.fixture
def simple_tool_def() -> ToolDefinition:
    """A minimal ToolDefinition with no parameters."""
    return ToolDefinition(
        endpoint_id="ep-1",
        name="get_order",
        description="Fetch an order by ID",
        risk_level=RiskLevel.READ,
        system_id="orders-svc",
        method="GET",
        path="/orders/{id}",
    )


@pytest.fixture
def rich_tool_def() -> ToolDefinition:
    """A ToolDefinition with path, query, and body parameters."""
    return ToolDefinition(
        endpoint_id="ep-2",
        name="update_order",
        description="Update an order",
        risk_level=RiskLevel.HIGH_WRITE,
        system_id="orders-svc",
        method="PUT",
        path="/orders/{order_id}",
        parameters={
            "path": {
                "order_id": {
                    "type": "str",
                    "description": "The order identifier",
                    "required": True,
                },
            },
            "query": {
                "dry_run": {
                    "type": "bool",
                    "description": "If true, validate without saving",
                    "required": False,
                },
            },
            "body": {
                "status": {
                    "type": "str",
                    "description": "New order status",
                    "required": True,
                },
                "notes": {
                    "type": "str",
                    "description": "Optional notes",
                    "required": False,
                },
            },
        },
    )


@pytest.fixture
def mock_executor() -> AsyncMock:
    executor = AsyncMock(spec=ToolExecutor)
    executor.execute_parallel = AsyncMock(return_value=[
        ToolResult(
            call_id="call-1",
            tool_name="get_order",
            success=True,
            data={"id": "ord-123", "status": "shipped"},
            error=None,
            duration_ms=42.0,
            status_code=200,
        ),
    ])
    return executor


# ---------------------------------------------------------------------------
# _build_parameter_specs tests
# ---------------------------------------------------------------------------


class TestBuildParameterSpecs:
    """Tests for the _build_parameter_specs helper."""

    def test_empty_parameters(self, simple_tool_def: ToolDefinition):
        specs = _build_parameter_specs(simple_tool_def)
        assert specs == []

    def test_path_params_default_required(self, rich_tool_def: ToolDefinition):
        specs = _build_parameter_specs(rich_tool_def)
        path_specs = [s for s in specs if s.name == "order_id"]
        assert len(path_specs) == 1
        assert path_specs[0].required is True
        assert path_specs[0].type_annotation == "str"
        assert path_specs[0].description == "The order identifier"

    def test_query_params_default_not_required(self, rich_tool_def: ToolDefinition):
        specs = _build_parameter_specs(rich_tool_def)
        query_specs = [s for s in specs if s.name == "dry_run"]
        assert len(query_specs) == 1
        assert query_specs[0].required is False
        assert query_specs[0].type_annotation == "bool"

    def test_body_params_extracted(self, rich_tool_def: ToolDefinition):
        specs = _build_parameter_specs(rich_tool_def)
        body_names = {s.name for s in specs if s.name in ("status", "notes")}
        assert body_names == {"status", "notes"}

    def test_body_required_param(self, rich_tool_def: ToolDefinition):
        specs = _build_parameter_specs(rich_tool_def)
        status_spec = next(s for s in specs if s.name == "status")
        assert status_spec.required is True

    def test_body_optional_param(self, rich_tool_def: ToolDefinition):
        specs = _build_parameter_specs(rich_tool_def)
        notes_spec = next(s for s in specs if s.name == "notes")
        assert notes_spec.required is False

    def test_total_count(self, rich_tool_def: ToolDefinition):
        """Should produce 4 specs: 1 path + 1 query + 2 body."""
        specs = _build_parameter_specs(rich_tool_def)
        assert len(specs) == 4

    def test_plain_string_param_info(self):
        """When a param value is a string rather than a dict, use it as description."""
        td = ToolDefinition(
            endpoint_id="ep-3",
            name="simple_tool",
            description="A tool",
            risk_level=RiskLevel.READ,
            system_id="sys-1",
            method="GET",
            path="/items",
            parameters={
                "query": {"search": "Search query string"},
            },
        )
        specs = _build_parameter_specs(td)
        assert len(specs) == 1
        assert specs[0].name == "search"
        assert specs[0].type_annotation == "str"
        assert specs[0].description == "Search query string"
        assert specs[0].required is False  # query defaults to not required

    def test_missing_sections_skipped(self):
        """Sections not present in parameters dict are ignored."""
        td = ToolDefinition(
            endpoint_id="ep-4",
            name="path_only",
            description="Only path params",
            risk_level=RiskLevel.READ,
            system_id="sys-1",
            method="GET",
            path="/items/{item_id}",
            parameters={
                "path": {
                    "item_id": {"type": "int", "description": "Item ID", "required": True},
                },
            },
        )
        specs = _build_parameter_specs(td)
        assert len(specs) == 1
        assert specs[0].name == "item_id"
        assert specs[0].type_annotation == "int"

    def test_non_dict_section_skipped(self):
        """Non-dict section values are ignored gracefully."""
        td = ToolDefinition(
            endpoint_id="ep-5",
            name="weird_params",
            description="Non-dict section",
            risk_level=RiskLevel.READ,
            system_id="sys-1",
            method="GET",
            path="/items",
            parameters={"body": "not a dict"},
        )
        specs = _build_parameter_specs(td)
        assert specs == []

    def test_defaults_type_to_str(self):
        """When type key is missing from param info dict, defaults to 'str'."""
        td = ToolDefinition(
            endpoint_id="ep-6",
            name="no_type",
            description="Missing type",
            risk_level=RiskLevel.READ,
            system_id="sys-1",
            method="GET",
            path="/items",
            parameters={
                "query": {
                    "filter": {"description": "Filter expression"},
                },
            },
        )
        specs = _build_parameter_specs(td)
        assert len(specs) == 1
        assert specs[0].type_annotation == "str"


# ---------------------------------------------------------------------------
# CatalogToolAdapter creation tests
# ---------------------------------------------------------------------------


class TestCatalogToolAdapterCreation:
    """Tests for CatalogToolAdapter construction."""

    def test_inherits_from_base_tool(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert isinstance(adapter, BaseTool)

    def test_name_from_tool_def(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert adapter.name == "get_order"

    def test_description_from_tool_def(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert adapter.description == "Fetch an order by ID"

    def test_parameters_populated(
        self, rich_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(rich_tool_def, mock_executor, user_session, "conv-1")
        assert len(adapter.parameters) == 4
        param_names = {p.name for p in adapter.parameters}
        assert param_names == {"order_id", "dry_run", "status", "notes"}

    def test_pydantic_handler_returns_callable(
        self, rich_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(rich_tool_def, mock_executor, user_session, "conv-1")
        handler = adapter.pydantic_handler()
        assert callable(handler)

    def test_pydantic_handler_has_typed_signature(
        self, rich_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(rich_tool_def, mock_executor, user_session, "conv-1")
        handler = adapter.pydantic_handler()
        sig = inspect.signature(handler)
        param_names = set(sig.parameters.keys())
        assert param_names == {"order_id", "dry_run", "status", "notes"}

    def test_no_params_handler_is_execute(
        self, simple_tool_def, mock_executor, user_session
    ):
        """Without parameters, pydantic_handler() returns the execute method directly."""
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        handler = adapter.pydantic_handler()
        assert handler == adapter.execute

    def test_stores_private_fields(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert adapter._tool_def is simple_tool_def
        assert adapter._executor is mock_executor
        assert adapter._session is user_session
        assert adapter._conversation_id == "conv-1"


# ---------------------------------------------------------------------------
# CatalogToolAdapter._execute() tests
# ---------------------------------------------------------------------------


class TestCatalogToolAdapterExecute:
    """Tests for CatalogToolAdapter._execute()."""

    async def test_execute_delegates_to_executor(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        result = await adapter._execute(order_id="ord-123")

        mock_executor.execute_parallel.assert_awaited_once()
        calls_arg, session_arg, conv_arg = mock_executor.execute_parallel.call_args[0]
        assert len(calls_arg) == 1
        assert isinstance(calls_arg[0], ToolCall)
        assert calls_arg[0].tool_name == "get_order"
        assert calls_arg[0].endpoint_id == "ep-1"
        assert session_arg is user_session
        assert conv_arg == "conv-1"

    async def test_execute_passes_kwargs_as_arguments(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        await adapter._execute(order_id="ord-456")

        calls_arg = mock_executor.execute_parallel.call_args[0][0]
        args = calls_arg[0].arguments
        assert args["order_id"] == "ord-456"
        assert args["_method"] == "GET"
        assert args["_system_id"] == "orders-svc"

    async def test_execute_returns_data_on_success(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        result = await adapter._execute(order_id="ord-123")
        assert result == {"id": "ord-123", "status": "shipped"}

    async def test_execute_raises_tool_error_on_failure(
        self, simple_tool_def, mock_executor, user_session
    ):
        mock_executor.execute_parallel.return_value = [
            ToolResult(
                call_id="call-1",
                tool_name="get_order",
                success=False,
                data=None,
                error="Not found",
                duration_ms=15.0,
                status_code=404,
            ),
        ]
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")

        with pytest.raises(ToolError, match="get_order failed: Not found"):
            await adapter._execute(order_id="ord-999")

    async def test_execute_via_public_api(
        self, simple_tool_def, mock_executor, user_session
    ):
        """Calling execute() (public) should also delegate correctly."""
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        result = await adapter.execute(order_id="ord-123")
        assert result == {"id": "ord-123", "status": "shipped"}
        mock_executor.execute_parallel.assert_awaited_once()

    async def test_execute_nests_kwargs_for_rich_tool(
        self, rich_tool_def, mock_executor, user_session
    ):
        """Verify flat LLM kwargs are re-nested into path/query/body structure."""
        adapter = CatalogToolAdapter(rich_tool_def, mock_executor, user_session, "conv-1")
        await adapter._execute(order_id="ord-1", dry_run=True, status="shipped")

        calls_arg = mock_executor.execute_parallel.call_args[0][0]
        args = calls_arg[0].arguments
        assert args["path"] == {"order_id": "ord-1"}
        assert args["query"] == {"dry_run": True}
        assert args["body"] == {"status": "shipped"}
        assert args["_method"] == "PUT"
        assert args["_system_id"] == "orders-svc"

    async def test_execute_generates_unique_call_ids(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        await adapter._execute(order_id="a")
        await adapter._execute(order_id="b")

        call_ids = [
            mock_executor.execute_parallel.call_args_list[i][0][0][0].call_id
            for i in range(2)
        ]
        assert call_ids[0] != call_ids[1]


# ---------------------------------------------------------------------------
# _nest_arguments() tests
# ---------------------------------------------------------------------------


class TestNestArguments:
    """Tests for _nest_arguments which re-nests flat LLM kwargs."""

    def test_empty_kwargs_and_params(self):
        result = _nest_arguments({}, {})
        assert result == {}

    def test_path_params_nested(self):
        params = {"path": {"order_id": {"type": "str"}}}
        result = _nest_arguments({"order_id": "ord-1"}, params)
        assert result == {"path": {"order_id": "ord-1"}}

    def test_query_params_nested(self):
        params = {"query": {"dry_run": {"type": "bool"}}}
        result = _nest_arguments({"dry_run": True}, params)
        assert result == {"query": {"dry_run": True}}

    def test_body_params_nested(self):
        params = {"body": {"status": {"type": "str"}, "notes": {"type": "str"}}}
        result = _nest_arguments({"status": "shipped", "notes": "urgent"}, params)
        assert result == {"body": {"status": "shipped", "notes": "urgent"}}

    def test_mixed_sections(self):
        params = {
            "path": {"order_id": {"type": "str"}},
            "query": {"dry_run": {"type": "bool"}},
            "body": {"status": {"type": "str"}},
        }
        result = _nest_arguments(
            {"order_id": "ord-1", "dry_run": False, "status": "cancelled"}, params,
        )
        assert result == {
            "path": {"order_id": "ord-1"},
            "query": {"dry_run": False},
            "body": {"status": "cancelled"},
        }

    def test_unclaimed_kwargs_pass_through(self):
        params = {"path": {"id": {"type": "str"}}}
        result = _nest_arguments({"id": "1", "extra": "value"}, params)
        assert result == {"path": {"id": "1"}, "extra": "value"}

    def test_missing_kwargs_skipped(self):
        params = {"path": {"id": {"type": "str"}}, "query": {"limit": {"type": "int"}}}
        result = _nest_arguments({"id": "1"}, params)
        assert result == {"path": {"id": "1"}}

    def test_non_dict_section_skipped(self):
        params = {"path": "not-a-dict", "query": {"limit": {"type": "int"}}}
        result = _nest_arguments({"limit": 10}, params)
        assert result == {"query": {"limit": 10}}


# ---------------------------------------------------------------------------
# adapt_tools() tests
# ---------------------------------------------------------------------------


class TestAdaptTools:
    """Tests for the adapt_tools convenience function."""

    def test_empty_list(self, mock_executor, user_session):
        result = adapt_tools([], mock_executor, user_session, "conv-1")
        assert result == []

    def test_creates_correct_number_of_adapters(
        self, simple_tool_def, rich_tool_def, mock_executor, user_session
    ):
        result = adapt_tools(
            [simple_tool_def, rich_tool_def], mock_executor, user_session, "conv-1",
        )
        assert len(result) == 2
        assert all(isinstance(a, CatalogToolAdapter) for a in result)

    def test_preserves_names(
        self, simple_tool_def, rich_tool_def, mock_executor, user_session
    ):
        result = adapt_tools(
            [simple_tool_def, rich_tool_def], mock_executor, user_session, "conv-1",
        )
        names = {a.name for a in result}
        assert names == {"get_order", "update_order"}

    def test_all_adapters_share_executor_and_session(
        self, simple_tool_def, rich_tool_def, mock_executor, user_session
    ):
        result = adapt_tools(
            [simple_tool_def, rich_tool_def], mock_executor, user_session, "conv-1",
        )
        for adapter in result:
            assert adapter._executor is mock_executor
            assert adapter._session is user_session
            assert adapter._conversation_id == "conv-1"

    def test_single_tool(self, simple_tool_def, mock_executor, user_session):
        result = adapt_tools([simple_tool_def], mock_executor, user_session, "conv-1")
        assert len(result) == 1
        assert result[0].name == "get_order"


# ---------------------------------------------------------------------------
# Integration: adapter works as genai BaseTool
# ---------------------------------------------------------------------------


class TestAdapterAsBaseTool:
    """Integration tests verifying the adapter satisfies BaseTool contract."""

    def test_info_returns_tool_info(
        self, rich_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(rich_tool_def, mock_executor, user_session, "conv-1")
        info = adapter.info()
        assert info.name == "update_order"
        assert info.description == "Update an order"
        assert info.parameter_count == 4

    def test_repr(self, simple_tool_def, mock_executor, user_session):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert "CatalogToolAdapter" in repr(adapter)
        assert "get_order" in repr(adapter)

    def test_tags_default_empty(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert adapter.tags == []

    def test_guards_default_empty(
        self, simple_tool_def, mock_executor, user_session
    ):
        adapter = CatalogToolAdapter(simple_tool_def, mock_executor, user_session, "conv-1")
        assert adapter.guards == []
