# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for tool wiring verification.

Ensures that the BuiltinToolRegistry registers the expected tools
and that every tool definition has required metadata.
"""

from __future__ import annotations

from flydesk.tools.builtin import BuiltinToolRegistry


class TestBuiltinToolsRegistered:
    """Verify the expected built-in tools are present."""

    def test_search_processes_registered(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        tool_names = [t.name for t in tools]
        assert "search_processes" in tool_names

    def test_search_knowledge_registered(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        tool_names = [t.name for t in tools]
        assert "search_knowledge" in tool_names

    def test_list_catalog_systems_registered(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        tool_names = [t.name for t in tools]
        assert "list_catalog_systems" in tool_names

    def test_list_system_endpoints_registered(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        tool_names = [t.name for t in tools]
        assert "list_system_endpoints" in tool_names

    def test_get_platform_status_registered(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        tool_names = [t.name for t in tools]
        assert "get_platform_status" in tool_names


class TestBuiltinToolsHaveMetadata:
    """Verify all built-in tools have required metadata fields."""

    def test_all_tools_have_names(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.name, "Tool must have a name"

    def test_all_tools_have_descriptions(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.description, f"Tool {tool.name} must have a description"

    def test_all_tools_have_endpoint_ids(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.endpoint_id, f"Tool {tool.name} must have an endpoint_id"

    def test_all_tools_have_risk_levels(self):
        tools = BuiltinToolRegistry.get_tool_definitions(["*"])
        for tool in tools:
            assert tool.risk_level is not None, f"Tool {tool.name} must have a risk_level"
