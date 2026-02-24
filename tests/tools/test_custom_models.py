# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CustomTool domain model."""

from __future__ import annotations

from flydesk.tools.custom_models import CustomTool, ToolSource


class TestCustomTool:
    def test_create_custom_tool(self):
        tool = CustomTool(
            id="tool-001",
            name="calculate_risk",
            description="Calculate credit risk score",
            python_code='async def execute(params, ctx):\n    return {"score": 85}',
            parameters={"order_id": {"type": "string", "description": "Order ID", "required": True}},
        )
        assert tool.id == "tool-001"
        assert tool.source == ToolSource.MANUAL
        assert tool.active is True
        assert tool.timeout_seconds == 30

    def test_builtin_source(self):
        tool = CustomTool(
            id="tool-builtin",
            name="search_knowledge",
            description="Search knowledge base",
            python_code="...",
            source=ToolSource.BUILTIN,
        )
        assert tool.source == ToolSource.BUILTIN

    def test_defaults(self):
        tool = CustomTool(
            id="t", name="t", description="t", python_code="pass",
        )
        assert tool.parameters == {}
        assert tool.output_schema == {}
        assert tool.timeout_seconds == 30
        assert tool.max_memory_mb == 256
