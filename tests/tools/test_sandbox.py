# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for subprocess sandbox executor."""

from __future__ import annotations

import pytest

from flydesk.tools.sandbox import SandboxExecutor, SandboxResult


@pytest.fixture
def executor():
    return SandboxExecutor()


class TestSandboxExecutor:
    @pytest.mark.anyio
    async def test_simple_execution(self, executor):
        code = 'import json, sys\nparams = json.loads(sys.stdin.read())\nresult = {"doubled": params["value"] * 2}\nprint(json.dumps(result))'
        result = await executor.execute(code, {"value": 5}, timeout=10)
        assert result.success is True
        assert result.data == {"doubled": 10}

    @pytest.mark.anyio
    async def test_timeout(self, executor):
        code = "import time\ntime.sleep(60)"
        result = await executor.execute(code, {}, timeout=1)
        assert result.success is False
        assert "timeout" in result.error.lower()

    @pytest.mark.anyio
    async def test_syntax_error(self, executor):
        code = "def broken(:"
        result = await executor.execute(code, {}, timeout=5)
        assert result.success is False
        assert result.error

    @pytest.mark.anyio
    async def test_runtime_error(self, executor):
        code = "raise ValueError('test error')"
        result = await executor.execute(code, {}, timeout=5)
        assert result.success is False
        assert "test error" in result.error

    @pytest.mark.anyio
    async def test_non_json_output(self, executor):
        code = 'print("not json")'
        result = await executor.execute(code, {}, timeout=5)
        assert result.success is False
        assert "json" in result.error.lower()

    @pytest.mark.anyio
    async def test_no_output(self, executor):
        code = "pass"
        result = await executor.execute(code, {}, timeout=5)
        assert result.success is False
        assert "no output" in result.error.lower()
