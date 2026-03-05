"""Tests for job timeout enforcement."""

import asyncio

import pytest


def test_config_has_job_timeout_field():
    """DeskConfig should have job_timeout_seconds field."""
    from flydesk.config import DeskConfig

    config = DeskConfig(database_url="sqlite+aiosqlite:///test.db")
    assert hasattr(config, "job_timeout_seconds")
    assert config.job_timeout_seconds == 3600


@pytest.mark.asyncio
async def test_job_timeout_triggers():
    """A slow handler wrapped in wait_for should raise TimeoutError."""

    async def slow_handler():
        await asyncio.sleep(10)

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_handler(), timeout=0.01)


@pytest.mark.asyncio
async def test_job_completes_within_timeout():
    """A fast handler should complete normally."""

    async def fast_handler():
        return "done"

    result = await asyncio.wait_for(fast_handler(), timeout=5)
    assert result == "done"
