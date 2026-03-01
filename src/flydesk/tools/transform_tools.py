# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Result transformation tools for grep, parse, filter, and transform operations.

These tools let the agent grep, parse, extract, and filter API results
without going through an external HTTP round-trip.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.tools.builtin import BUILTIN_SYSTEM_ID
from flydesk.tools.factory import ToolDefinition

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def grep_result_tool() -> ToolDefinition:
    """Tool definition for filtering lines/objects matching a regex pattern."""
    return ToolDefinition(
        endpoint_id="__builtin__grep_result",
        name="grep_result",
        description=(
            "Filter lines or objects from a text/JSON result that match a "
            "regular expression pattern. Accepts either a plain text block "
            "(searched line-by-line) or a JSON array (each element is tested). "
            "Use when: you need to narrow down a large result set to lines or "
            "objects matching a keyword or pattern."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/grep",
        parameters={
            "data": {
                "type": "string",
                "description": "The text or JSON array string to search through",
                "required": True,
            },
            "pattern": {
                "type": "string",
                "description": "Regular expression pattern to match",
                "required": True,
            },
        },
    )


def parse_json_tool() -> ToolDefinition:
    """Tool definition for parsing JSON and extracting by dot-path."""
    return ToolDefinition(
        endpoint_id="__builtin__parse_json",
        name="parse_json",
        description=(
            "Parse a JSON string and optionally extract a value by dot-path, "
            "list top-level keys, or validate the structure. "
            "Use when: you need to drill into a JSON response, check its "
            "structure, or pull out a nested value."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/parse_json",
        parameters={
            "data": {
                "type": "string",
                "description": "JSON string to parse",
                "required": True,
            },
            "action": {
                "type": "string",
                "description": "Action: extract (default), keys, or validate",
                "required": False,
            },
            "path": {
                "type": "string",
                "description": "Dot-separated path for extraction (e.g. 'results.0.name')",
                "required": False,
            },
        },
    )


def filter_rows_tool() -> ToolDefinition:
    """Tool definition for filtering an array of objects by field conditions."""
    return ToolDefinition(
        endpoint_id="__builtin__filter_rows",
        name="filter_rows",
        description=(
            "Filter an array of objects by field conditions. Supports operators: "
            "eq, neq, gt, lt, gte, lte, contains. "
            "Use when: you need to narrow down a list of records by a specific "
            "field value or range."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/filter_rows",
        parameters={
            "data": {
                "type": "string",
                "description": "JSON array string of objects to filter",
                "required": True,
            },
            "field": {
                "type": "string",
                "description": "Field name to filter on",
                "required": True,
            },
            "operator": {
                "type": "string",
                "description": "Comparison operator: eq, neq, gt, lt, gte, lte, contains",
                "required": True,
            },
            "value": {
                "type": "string",
                "description": "Value to compare against",
                "required": True,
            },
        },
    )


def transform_data_tool() -> ToolDefinition:
    """Tool definition for sorting, grouping, counting, or picking fields."""
    return ToolDefinition(
        endpoint_id="__builtin__transform_data",
        name="transform_data",
        description=(
            "Transform an array of objects: sort by a field, group by a field, "
            "count items, or pick specific fields. "
            "Use when: you need to reorder, aggregate, or slim down a dataset."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/data",
        parameters={
            "data": {
                "type": "string",
                "description": "JSON array string of objects to transform",
                "required": True,
            },
            "action": {
                "type": "string",
                "description": "Action: sort, group, count, or pick",
                "required": True,
            },
            "field": {
                "type": "string",
                "description": "Field name for sort/group actions",
                "required": False,
            },
            "order": {
                "type": "string",
                "description": "Sort order: asc (default) or desc",
                "required": False,
            },
            "fields": {
                "type": "string",
                "description": "Comma-separated field names for pick action",
                "required": False,
            },
        },
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TransformToolExecutor:
    """Execute transform tools for grepping, parsing, filtering, and transforming data.

    All operations are pure in-memory transformations using only stdlib
    modules (``json``, ``re``, ``collections.defaultdict``).
    """

    _TOOL_NAMES = frozenset({
        "grep_result",
        "parse_json",
        "filter_rows",
        "transform_data",
    })

    @classmethod
    def is_transform_tool(cls, tool_name: str) -> bool:
        """Return True if *tool_name* is handled by this executor."""
        return tool_name in cls._TOOL_NAMES

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to the appropriate transform handler."""
        handlers: dict[str, Any] = {
            "grep_result": self._grep,
            "parse_json": self._parse_json,
            "filter_rows": self._filter_rows,
            "transform_data": self._transform_data,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown transform tool: {tool_name}"}

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Transform tool %s failed: %s", tool_name, exc, exc_info=True)
            return {"error": str(exc)}

    # ---- Grep ----

    async def _grep(self, arguments: dict[str, Any]) -> dict[str, Any]:
        data: str = arguments.get("data", "")
        pattern: str = arguments.get("pattern", "")

        if not data:
            return {"error": "data is required"}
        if not pattern:
            return {"error": "pattern is required"}

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            return {"error": f"Invalid regex pattern: {exc}"}

        # Try JSON array first
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                matches = [
                    item for item in parsed
                    if regex.search(json.dumps(item, default=str))
                ]
                return {"matches": matches, "count": len(matches)}
        except (json.JSONDecodeError, TypeError):
            logger.debug("Data is not JSON; falling back to line-by-line search")

        # Fall back to line-by-line text search
        lines = data.splitlines()
        matches = [line for line in lines if regex.search(line)]
        return {"matches": matches, "count": len(matches)}

    # ---- Parse JSON ----

    async def _parse_json(self, arguments: dict[str, Any]) -> dict[str, Any]:
        data: str = arguments.get("data", "")
        action: str = arguments.get("action", "extract")
        path: str = arguments.get("path", "")

        if not data:
            return {"error": "data is required"}

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON: {exc}", "valid": False}

        if action == "validate":
            return {"valid": True, "type": type(parsed).__name__}

        if action == "keys":
            if isinstance(parsed, dict):
                return {"keys": list(parsed.keys())}
            return {"error": "keys action requires a JSON object (dict)"}

        # Default action: extract
        if not path:
            return {"result": parsed}

        # Dot-path traversal
        current: Any = parsed
        for segment in path.split("."):
            if isinstance(current, dict):
                if segment not in current:
                    return {"error": f"Key '{segment}' not found in path '{path}'"}
                current = current[segment]
            elif isinstance(current, list):
                try:
                    idx = int(segment)
                except ValueError:
                    return {"error": f"Expected integer index, got '{segment}' in path '{path}'"}
                if idx < 0 or idx >= len(current):
                    return {"error": f"Index {idx} out of range for path '{path}'"}
                current = current[idx]
            else:
                return {"error": f"Cannot traverse into {type(current).__name__} at '{segment}'"}

        return {"result": current}

    # ---- Filter rows ----

    async def _filter_rows(self, arguments: dict[str, Any]) -> dict[str, Any]:
        data: str = arguments.get("data", "")
        field_name: str = arguments.get("field", "")
        operator: str = arguments.get("operator", "")
        value: str = arguments.get("value", "")

        if not data:
            return {"error": "data is required"}
        if not field_name:
            return {"error": "field is required"}
        if not operator:
            return {"error": "operator is required"}

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON: {exc}"}

        if not isinstance(parsed, list):
            return {"error": "data must be a JSON array"}

        valid_operators = {"eq", "neq", "gt", "lt", "gte", "lte", "contains"}
        if operator not in valid_operators:
            valid_str = ", ".join(sorted(valid_operators))
            return {"error": f"Unknown operator: {operator}. Valid: {valid_str}"}

        matches: list[Any] = []
        for row in parsed:
            if not isinstance(row, dict):
                continue
            if field_name not in row:
                continue
            field_value = row[field_name]
            if self._compare(field_value, operator, value):
                matches.append(row)

        return {"matches": matches, "count": len(matches)}

    @staticmethod
    def _compare(field_value: Any, operator: str, value: str) -> bool:
        """Compare a field value against the given value using the operator."""
        if operator == "eq":
            return str(field_value) == value
        if operator == "neq":
            return str(field_value) != value
        if operator == "contains":
            return value in str(field_value)

        # Numeric comparisons for gt, lt, gte, lte
        try:
            num_field = float(field_value)
            num_value = float(value)
        except (ValueError, TypeError):
            return False

        if operator == "gt":
            return num_field > num_value
        if operator == "lt":
            return num_field < num_value
        if operator == "gte":
            return num_field >= num_value
        if operator == "lte":
            return num_field <= num_value

        return False

    # ---- Transform data ----

    async def _transform_data(self, arguments: dict[str, Any]) -> dict[str, Any]:
        data: str = arguments.get("data", "")
        action: str = arguments.get("action", "")

        if not data:
            return {"error": "data is required"}
        if not action:
            return {"error": "action is required"}

        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as exc:
            return {"error": f"Invalid JSON: {exc}"}

        if not isinstance(parsed, list):
            return {"error": "data must be a JSON array"}

        if action == "count":
            return {"count": len(parsed)}

        if action == "sort":
            return self._do_sort(parsed, arguments)

        if action == "group":
            return self._do_group(parsed, arguments)

        if action == "pick":
            return self._do_pick(parsed, arguments)

        return {"error": f"Unknown action: {action}. Valid: sort, group, count, pick"}

    @staticmethod
    def _do_sort(rows: list[Any], arguments: dict[str, Any]) -> dict[str, Any]:
        field_name: str = arguments.get("field", "")
        order: str = arguments.get("order", "asc")

        if not field_name:
            return {"error": "field is required for sort action"}

        try:
            sorted_rows = sorted(
                rows,
                key=lambda row: row.get(field_name) if isinstance(row, dict) else row,
                reverse=(order == "desc"),
            )
        except TypeError:
            return {"error": f"Cannot sort by field '{field_name}': incompatible types"}

        return {"result": sorted_rows, "count": len(sorted_rows)}

    @staticmethod
    def _do_group(rows: list[Any], arguments: dict[str, Any]) -> dict[str, Any]:
        field_name: str = arguments.get("field", "")

        if not field_name:
            return {"error": "field is required for group action"}

        groups: dict[str, list[Any]] = defaultdict(list)
        for row in rows:
            if isinstance(row, dict):
                key = str(row.get(field_name, "__missing__"))
            else:
                key = "__missing__"
            groups[key].append(row)

        return {"groups": dict(groups), "group_count": len(groups)}

    @staticmethod
    def _do_pick(rows: list[Any], arguments: dict[str, Any]) -> dict[str, Any]:
        fields_str: str = arguments.get("fields", "")

        if not fields_str:
            return {"error": "fields is required for pick action"}

        field_names = [f.strip() for f in fields_str.split(",")]
        picked = []
        for row in rows:
            if isinstance(row, dict):
                picked.append({k: row.get(k) for k in field_names})
            else:
                picked.append(row)

        return {"result": picked, "count": len(picked)}
