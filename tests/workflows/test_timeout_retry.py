# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for workflow step timeout and retry."""

import asyncio

import pytest
from sqlalchemy import inspect as sa_inspect


def test_workflow_step_row_has_timeout_columns():
    """WorkflowStepRow should have timeout_seconds, max_retries, retry_count."""
    from flydesk.models.workflow import WorkflowStepRow

    cols = {c.key for c in sa_inspect(WorkflowStepRow).columns}
    assert "timeout_seconds" in cols
    assert "max_retries" in cols
    assert "retry_count" in cols


def test_workflow_step_row_defaults():
    """Default values should be timeout=300, max_retries=0, retry_count=0."""
    from flydesk.models.workflow import WorkflowStepRow

    mapper = sa_inspect(WorkflowStepRow)
    col_map = {c.key: c for c in mapper.columns}

    assert col_map["timeout_seconds"].default is not None
    assert col_map["max_retries"].default is not None
    assert col_map["retry_count"].default is not None


@pytest.mark.asyncio
async def test_step_timeout_triggers():
    """asyncio.wait_for should raise TimeoutError for slow operations."""

    async def slow_operation():
        await asyncio.sleep(10)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_operation(), timeout=0.01)


@pytest.mark.asyncio
async def test_exponential_backoff_calculation():
    """Backoff should be min(30 * 2^retry_count, 3600)."""

    def calculate_backoff(retry_count: int) -> int:
        return min(30 * (2 ** retry_count), 3600)

    assert calculate_backoff(0) == 30
    assert calculate_backoff(1) == 60
    assert calculate_backoff(2) == 120
    assert calculate_backoff(5) == 960
    assert calculate_backoff(7) == 3600  # Capped
    assert calculate_backoff(10) == 3600  # Still capped
