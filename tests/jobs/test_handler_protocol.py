"""Tests for the updated handler protocol with checkpoint support."""
from __future__ import annotations

from dataclasses import dataclass

from flydesk.jobs.handlers import ExecutionResult


class TestExecutionResult:
    def test_completed_result(self):
        r = ExecutionResult(result={"docs": 5})
        assert r.result == {"docs": 5}
        assert r.checkpoint is None

    def test_paused_result(self):
        r = ExecutionResult(result={}, checkpoint={"idx": 3})
        assert r.checkpoint == {"idx": 3}

    def test_is_paused_property(self):
        assert not ExecutionResult(result={}).is_paused
        assert ExecutionResult(result={}, checkpoint={"x": 1}).is_paused
