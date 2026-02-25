# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for result transformation tools (grep, parse_json, filter_rows, transform_data)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.enums import RiskLevel
from flydesk.tools.builtin import BUILTIN_SYSTEM_ID, BuiltinToolRegistry
from flydesk.tools.transform_tools import (
    TransformToolExecutor,
    filter_rows_tool,
    grep_result_tool,
    parse_json_tool,
    transform_data_tool,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def executor() -> TransformToolExecutor:
    return TransformToolExecutor()


# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_grep_result_tool_definition(self):
        tool = grep_result_tool()
        assert tool.name == "grep_result"
        assert tool.risk_level == RiskLevel.READ
        assert tool.system_id == BUILTIN_SYSTEM_ID
        assert "data" in tool.parameters
        assert "pattern" in tool.parameters

    def test_parse_json_tool_definition(self):
        tool = parse_json_tool()
        assert tool.name == "parse_json"
        assert tool.risk_level == RiskLevel.READ
        assert "data" in tool.parameters

    def test_filter_rows_tool_definition(self):
        tool = filter_rows_tool()
        assert tool.name == "filter_rows"
        assert tool.risk_level == RiskLevel.READ
        assert "field" in tool.parameters
        assert "operator" in tool.parameters

    def test_transform_data_tool_definition(self):
        tool = transform_data_tool()
        assert tool.name == "transform_data"
        assert tool.risk_level == RiskLevel.READ
        assert "action" in tool.parameters


class TestRegistryIntegration:
    def test_transform_tools_always_available(self):
        """Transform tools are always available, even with no permissions."""
        tools = BuiltinToolRegistry.get_tool_definitions([])
        names = {t.name for t in tools}
        assert "grep_result" in names
        assert "parse_json" in names
        assert "filter_rows" in names
        assert "transform_data" in names

    def test_admin_gets_transform_tools(self):
        """Admin user with * permission also gets transform tools."""
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        names = {t.name for t in tools}
        assert "grep_result" in names
        assert "parse_json" in names
        assert "filter_rows" in names
        assert "transform_data" in names


class TestIsTransformTool:
    def test_recognized_tools(self):
        assert TransformToolExecutor.is_transform_tool("grep_result") is True
        assert TransformToolExecutor.is_transform_tool("parse_json") is True
        assert TransformToolExecutor.is_transform_tool("filter_rows") is True
        assert TransformToolExecutor.is_transform_tool("transform_data") is True

    def test_unrecognized_tools(self):
        assert TransformToolExecutor.is_transform_tool("search_knowledge") is False
        assert TransformToolExecutor.is_transform_tool("transform_unknown") is False


# ---------------------------------------------------------------------------
# Grep tests
# ---------------------------------------------------------------------------


class TestGrepResult:
    async def test_grep_lines(self, executor: TransformToolExecutor):
        """Grep plain text line-by-line."""
        text = "apple pie\nbanana split\napricot jam\ncherry tart"
        result = await executor.execute(
            "grep_result", {"data": text, "pattern": "ap"}
        )
        assert "error" not in result
        assert result["count"] == 2
        assert "apple pie" in result["matches"]
        assert "apricot jam" in result["matches"]

    async def test_grep_json_array(self, executor: TransformToolExecutor):
        """Grep a JSON array, matching against stringified items."""
        items = [
            {"name": "Alice", "role": "admin"},
            {"name": "Bob", "role": "user"},
            {"name": "Charlie", "role": "admin"},
        ]
        data = json.dumps(items)
        result = await executor.execute(
            "grep_result", {"data": data, "pattern": "admin"}
        )
        assert "error" not in result
        assert result["count"] == 2
        assert result["matches"][0]["name"] == "Alice"
        assert result["matches"][1]["name"] == "Charlie"

    async def test_grep_missing_data_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute("grep_result", {"pattern": "test"})
        assert "error" in result

    async def test_grep_missing_pattern_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute("grep_result", {"data": "some text"})
        assert "error" in result

    async def test_grep_invalid_regex_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "grep_result", {"data": "text", "pattern": "[invalid"}
        )
        assert "error" in result
        assert "Invalid regex" in result["error"]

    async def test_grep_no_matches(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "grep_result", {"data": "hello world", "pattern": "xyz"}
        )
        assert result["count"] == 0
        assert result["matches"] == []


# ---------------------------------------------------------------------------
# Parse JSON tests
# ---------------------------------------------------------------------------


class TestParseJson:
    async def test_extract_path(self, executor: TransformToolExecutor):
        """Extract a nested value by dot-path."""
        data = json.dumps({"results": [{"name": "Alice"}, {"name": "Bob"}]})
        result = await executor.execute(
            "parse_json", {"data": data, "path": "results.0.name"}
        )
        assert "error" not in result
        assert result["result"] == "Alice"

    async def test_extract_no_path_returns_full(self, executor: TransformToolExecutor):
        """Extract without path returns entire parsed object."""
        data = json.dumps({"key": "value"})
        result = await executor.execute("parse_json", {"data": data})
        assert result["result"] == {"key": "value"}

    async def test_keys(self, executor: TransformToolExecutor):
        """Keys action lists top-level keys."""
        data = json.dumps({"name": "Alice", "age": 30, "role": "admin"})
        result = await executor.execute(
            "parse_json", {"data": data, "action": "keys"}
        )
        assert "error" not in result
        assert set(result["keys"]) == {"name", "age", "role"}

    async def test_keys_on_non_dict_returns_error(self, executor: TransformToolExecutor):
        data = json.dumps([1, 2, 3])
        result = await executor.execute(
            "parse_json", {"data": data, "action": "keys"}
        )
        assert "error" in result

    async def test_validate_valid_json(self, executor: TransformToolExecutor):
        data = json.dumps({"valid": True})
        result = await executor.execute(
            "parse_json", {"data": data, "action": "validate"}
        )
        assert result["valid"] is True
        assert result["type"] == "dict"

    async def test_validate_invalid_json(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "parse_json", {"data": "not json {", "action": "validate"}
        )
        assert result["valid"] is False

    async def test_extract_missing_key_returns_error(self, executor: TransformToolExecutor):
        data = json.dumps({"a": 1})
        result = await executor.execute(
            "parse_json", {"data": data, "path": "b"}
        )
        assert "error" in result
        assert "not found" in result["error"]

    async def test_extract_index_out_of_range(self, executor: TransformToolExecutor):
        data = json.dumps({"items": [1, 2]})
        result = await executor.execute(
            "parse_json", {"data": data, "path": "items.5"}
        )
        assert "error" in result
        assert "out of range" in result["error"]

    async def test_missing_data_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute("parse_json", {})
        assert "error" in result


# ---------------------------------------------------------------------------
# Filter rows tests
# ---------------------------------------------------------------------------


class TestFilterRows:
    @pytest.fixture
    def sample_rows(self) -> str:
        return json.dumps([
            {"name": "Alice", "age": 30, "dept": "Engineering"},
            {"name": "Bob", "age": 25, "dept": "Sales"},
            {"name": "Charlie", "age": 35, "dept": "Engineering"},
            {"name": "Diana", "age": 28, "dept": "Marketing"},
        ])

    async def test_filter_equals(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "dept", "operator": "eq", "value": "Engineering"},
        )
        assert "error" not in result
        assert result["count"] == 2
        names = [r["name"] for r in result["matches"]]
        assert "Alice" in names
        assert "Charlie" in names

    async def test_filter_not_equals(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "dept", "operator": "neq", "value": "Engineering"},
        )
        assert result["count"] == 2
        names = [r["name"] for r in result["matches"]]
        assert "Bob" in names
        assert "Diana" in names

    async def test_filter_contains(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "name", "operator": "contains", "value": "li"},
        )
        assert "error" not in result
        assert result["count"] == 2
        names = [r["name"] for r in result["matches"]]
        assert "Alice" in names
        assert "Charlie" in names

    async def test_filter_greater_than(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "age", "operator": "gt", "value": "29"},
        )
        assert result["count"] == 2
        names = [r["name"] for r in result["matches"]]
        assert "Alice" in names
        assert "Charlie" in names

    async def test_filter_less_than_or_equal(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "age", "operator": "lte", "value": "28"},
        )
        assert result["count"] == 2
        names = [r["name"] for r in result["matches"]]
        assert "Bob" in names
        assert "Diana" in names

    async def test_filter_invalid_operator_returns_error(
        self, executor: TransformToolExecutor, sample_rows: str
    ):
        result = await executor.execute(
            "filter_rows",
            {"data": sample_rows, "field": "age", "operator": "like", "value": "30"},
        )
        assert "error" in result
        assert "Unknown operator" in result["error"]

    async def test_filter_invalid_json_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "filter_rows",
            {"data": "not json", "field": "x", "operator": "eq", "value": "1"},
        )
        assert "error" in result

    async def test_filter_non_array_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "filter_rows",
            {"data": json.dumps({"key": "val"}), "field": "x", "operator": "eq", "value": "1"},
        )
        assert "error" in result
        assert "array" in result["error"]

    async def test_filter_missing_field_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "filter_rows",
            {"data": "[]", "operator": "eq", "value": "1"},
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Transform data tests
# ---------------------------------------------------------------------------


class TestTransformData:
    @pytest.fixture
    def sample_data(self) -> str:
        return json.dumps([
            {"name": "Alice", "score": 90, "team": "A"},
            {"name": "Bob", "score": 75, "team": "B"},
            {"name": "Charlie", "score": 85, "team": "A"},
            {"name": "Diana", "score": 95, "team": "B"},
        ])

    async def test_sort(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        """Sort by field ascending."""
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "sort", "field": "score"},
        )
        assert "error" not in result
        assert result["count"] == 4
        names = [r["name"] for r in result["result"]]
        assert names == ["Bob", "Charlie", "Alice", "Diana"]

    async def test_sort_descending(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        """Sort by field descending."""
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "sort", "field": "score", "order": "desc"},
        )
        assert "error" not in result
        names = [r["name"] for r in result["result"]]
        assert names == ["Diana", "Alice", "Charlie", "Bob"]

    async def test_group_by(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        """Group by a field."""
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "group", "field": "team"},
        )
        assert "error" not in result
        assert result["group_count"] == 2
        assert len(result["groups"]["A"]) == 2
        assert len(result["groups"]["B"]) == 2

    async def test_count(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        """Count items in the array."""
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "count"},
        )
        assert result["count"] == 4

    async def test_pick(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        """Pick specific fields from each row."""
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "pick", "fields": "name,score"},
        )
        assert "error" not in result
        assert result["count"] == 4
        for row in result["result"]:
            assert set(row.keys()) == {"name", "score"}

    async def test_sort_missing_field_returns_error(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "sort"},
        )
        assert "error" in result

    async def test_group_missing_field_returns_error(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "group"},
        )
        assert "error" in result

    async def test_pick_missing_fields_returns_error(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "pick"},
        )
        assert "error" in result

    async def test_unknown_action_returns_error(
        self, executor: TransformToolExecutor, sample_data: str
    ):
        result = await executor.execute(
            "transform_data",
            {"data": sample_data, "action": "pivot"},
        )
        assert "error" in result
        assert "Unknown action" in result["error"]

    async def test_invalid_json_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "transform_data",
            {"data": "not json", "action": "count"},
        )
        assert "error" in result

    async def test_non_array_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute(
            "transform_data",
            {"data": json.dumps({"key": "val"}), "action": "count"},
        )
        assert "error" in result


# ---------------------------------------------------------------------------
# Executor dispatch tests
# ---------------------------------------------------------------------------


class TestExecutorDispatch:
    async def test_unknown_tool_returns_error(self, executor: TransformToolExecutor):
        result = await executor.execute("transform_unknown", {})
        assert "error" in result
        assert "Unknown" in result["error"]

    async def test_exception_in_handler_returns_error(
        self, executor: TransformToolExecutor
    ):
        """Internal errors are caught and returned as error dicts."""
        # Passing a non-string data that causes an unexpected error path
        # We'll test via a mock to guarantee an exception
        import unittest.mock

        with unittest.mock.patch.object(
            executor, "_grep", side_effect=RuntimeError("boom")
        ):
            result = await executor.execute("grep_result", {"data": "x", "pattern": "y"})
        assert "error" in result
        assert "boom" in result["error"]


# ---------------------------------------------------------------------------
# BuiltinToolExecutor delegation tests
# ---------------------------------------------------------------------------


class TestBuiltinDelegation:
    async def test_builtin_executor_delegates_transform_tools(self):
        """BuiltinToolExecutor.execute delegates transform tool calls."""
        from flydesk.tools.builtin import BuiltinToolExecutor

        catalog_repo = MagicMock()
        catalog_repo.list_systems = AsyncMock(return_value=[])
        catalog_repo.list_endpoints = AsyncMock(return_value=[])
        audit_logger = MagicMock()
        audit_logger.query = AsyncMock(return_value=[])

        builtin = BuiltinToolExecutor(
            catalog_repo=catalog_repo, audit_logger=audit_logger
        )

        result = await builtin.execute(
            "grep_result", {"data": "hello world\nfoo bar", "pattern": "foo"}
        )
        assert "error" not in result
        assert result["count"] == 1
        assert "foo bar" in result["matches"]

    async def test_builtin_executor_delegates_parse_json(self):
        """BuiltinToolExecutor.execute delegates parse_json calls."""
        from flydesk.tools.builtin import BuiltinToolExecutor

        catalog_repo = MagicMock()
        catalog_repo.list_systems = AsyncMock(return_value=[])
        catalog_repo.list_endpoints = AsyncMock(return_value=[])
        audit_logger = MagicMock()
        audit_logger.query = AsyncMock(return_value=[])

        builtin = BuiltinToolExecutor(
            catalog_repo=catalog_repo, audit_logger=audit_logger
        )

        data = json.dumps({"users": [{"name": "Alice"}]})
        result = await builtin.execute(
            "parse_json", {"data": data, "path": "users.0.name"}
        )
        assert result["result"] == "Alice"
