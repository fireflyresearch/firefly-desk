"""Tests for budget status endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.app.state.config = MagicMock()
    request.app.state.config.daily_budget_limit = 100.0
    request.app.state.config.budget_alert_warning = 0.8
    request.app.state.config.budget_alert_critical = 0.95
    request.app.state.settings_repo = AsyncMock()
    return request


@pytest.mark.asyncio
async def test_budget_status_ok(mock_request):
    from flydesk.api.budget import budget_status

    mock_request.app.state.settings_repo.get.return_value = "50.0"
    result = await budget_status(mock_request)
    assert result["status"] == "ok"
    assert result["spent_today"] == 50.0
    assert result["percentage"] == 0.5


@pytest.mark.asyncio
async def test_budget_status_warning(mock_request):
    from flydesk.api.budget import budget_status

    mock_request.app.state.settings_repo.get.return_value = "85.0"
    result = await budget_status(mock_request)
    assert result["status"] == "warning"


@pytest.mark.asyncio
async def test_budget_status_critical(mock_request):
    from flydesk.api.budget import budget_status

    mock_request.app.state.settings_repo.get.return_value = "96.0"
    result = await budget_status(mock_request)
    assert result["status"] == "critical"


@pytest.mark.asyncio
async def test_budget_status_unlimited():
    from flydesk.api.budget import budget_status

    request = MagicMock()
    request.app.state.config = MagicMock()
    request.app.state.config.daily_budget_limit = 0.0
    request.app.state.settings_repo = AsyncMock()
    request.app.state.settings_repo.get.return_value = "0"
    result = await budget_status(request)
    assert result["status"] == "unlimited"
    assert result["percentage"] == 0.0
