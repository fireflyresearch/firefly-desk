# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for CustomToolAdapter."""

from __future__ import annotations

import pytest

from flydesk.tools.custom_models import CustomTool
from flydesk.tools.genai_adapter import CustomToolAdapter
from flydesk.tools.sandbox import SandboxResult


class MockSandbox:
    """A fake SandboxExecutor that returns a pre-configured result."""

    def __init__(self, result: SandboxResult) -> None:
        self._result = result
        self.last_code: str | None = None
        self.last_params: dict | None = None

    async def execute(self, code, params, **kwargs):
        self.last_code = code
        self.last_params = params
        return self._result


class TestCustomToolAdapter:
    """Tests for CustomToolAdapter construction and execution."""

    def test_adapter_creation(self):
        tool = CustomTool(
            id="t1",
            name="calc_risk",
            description="Calculate risk",
            python_code="pass",
            parameters={"order_id": {"type": "string", "description": "Order ID", "required": True}},
        )
        sandbox = MockSandbox(SandboxResult(success=True, data={}))
        adapter = CustomToolAdapter(tool, sandbox)
        assert adapter.name == "calc_risk"
        assert adapter.description == "Calculate risk"

    @pytest.mark.anyio
    async def test_adapter_execution_success(self):
        tool = CustomTool(
            id="t1",
            name="calc_risk",
            description="Calculate risk",
            python_code='print("ok")',
            parameters={"order_id": {"type": "string", "description": "Order ID", "required": True}},
        )
        sandbox = MockSandbox(SandboxResult(success=True, data={"score": 85}))
        adapter = CustomToolAdapter(tool, sandbox)
        result = await adapter._execute(order_id="123")
        assert result == {"score": 85}
        assert sandbox.last_params == {"order_id": "123"}

    @pytest.mark.anyio
    async def test_adapter_execution_failure(self):
        tool = CustomTool(
            id="t1",
            name="calc_risk",
            description="Calculate risk",
            python_code="raise Exception('fail')",
        )
        sandbox = MockSandbox(SandboxResult(success=False, error="fail"))
        adapter = CustomToolAdapter(tool, sandbox)
        from fireflyframework_genai.exceptions import ToolError

        with pytest.raises(ToolError, match="fail"):
            await adapter._execute()
