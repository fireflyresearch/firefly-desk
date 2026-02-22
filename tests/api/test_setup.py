# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Setup API including first-run detection and wizard endpoints."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.models.base import Base


@pytest.fixture
async def client():
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDEK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydek.server import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def db_client():
    """Client with a real in-memory database wired into app state.

    ASGITransport does not trigger the lifespan, so we manually create the
    engine, tables, and session factory and attach them to app.state.
    """
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDEK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydek.config import get_config
        from flydek.server import create_app

        app = create_app()

        # Create in-memory database and wire dependencies manually
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        config = get_config()
        app.state.config = config
        app.state.session_factory = session_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


class TestFirstRun:
    async def test_first_run_returns_true_when_no_systems(self, client):
        """Fresh database with no seed data should be first run."""
        response = await client.get("/api/setup/first-run")
        assert response.status_code == 200
        data = response.json()
        assert data["is_first_run"] is True

    async def test_first_run_endpoint_returns_200(self, client):
        """The first-run endpoint should always return a valid JSON response."""
        response = await client.get("/api/setup/first-run")
        assert response.status_code == 200
        data = response.json()
        assert "is_first_run" in data
        assert isinstance(data["is_first_run"], bool)


class TestSetupStatus:
    async def test_status_returns_agent_name(self, client):
        """Setup status should reflect the configured agent name."""
        response = await client.get("/api/setup/status")
        assert response.status_code == 200
        data = response.json()
        assert data["agent_name"] == "Ember"

    async def test_status_returns_all_fields(self, client):
        """Setup status should include all expected fields."""
        response = await client.get("/api/setup/status")
        assert response.status_code == 200
        data = response.json()
        expected_fields = [
            "dev_mode", "database_configured", "oidc_configured",
            "has_seed_data", "app_title", "app_version", "agent_name", "accent_color",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"


class TestConfigure:
    async def test_configure_marks_setup_complete(self, db_client):
        """POST /api/setup/configure should mark setup as complete."""
        response = await db_client.post(
            "/api/setup/configure",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["setup_completed"] is True

    async def test_configure_with_llm_provider(self, db_client):
        """Configure with LLM provider should store it."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "Test OpenAI",
                    "provider_type": "openai",
                    "api_key": "sk-test-key-12345",
                    "base_url": None,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["llm_provider"] == "configured"

    async def test_configure_with_seed_data(self, db_client):
        """Configure with seed_data=true should load banking data."""
        response = await db_client.post(
            "/api/setup/configure",
            json={"seed_data": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["seed_data"] == "loaded"

    async def test_configure_with_all_options(self, db_client):
        """Configure with both LLM and seed data."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "Test Anthropic",
                    "provider_type": "anthropic",
                    "api_key": "sk-ant-test",
                },
                "seed_data": True,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["llm_provider"] == "configured"
        assert data["details"]["seed_data"] == "loaded"

    async def test_configure_invalid_provider_type(self, db_client):
        """Invalid provider type should return failure."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "Bad Provider",
                    "provider_type": "nonexistent",
                    "api_key": "key",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Failed" in data["message"]

    async def test_configure_without_db_returns_failure(self, client):
        """Configure without database should return failure."""
        response = await client.post(
            "/api/setup/configure",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not initialised" in data["message"]


class TestWizardState:
    async def test_wizard_state_not_started(self, client):
        """When no setup handlers exist and no completion flag, return not_started."""
        response = await client.get("/api/setup/wizard-state")
        assert response.status_code == 200
        data = response.json()
        assert data["step"] == "not_started"
        assert data["completed"] is False

    async def test_wizard_state_returns_completed_after_configure(self, db_client):
        """After running configure, wizard-state should return completed."""
        # First, configure (which marks setup complete)
        await db_client.post("/api/setup/configure", json={})

        response = await db_client.get("/api/setup/wizard-state")
        assert response.status_code == 200
        data = response.json()
        assert data["step"] == "completed"
        assert data["completed"] is True

    async def test_wizard_state_with_active_handler(self, client):
        """When an active handler exists, return its current step."""
        from flydek.agent.setup_handler import SetupStep

        mock_handler = MagicMock()
        mock_handler.current_step = SetupStep.DATABASE_CHECK

        transport = client._transport
        app = transport.app
        if not hasattr(app.state, "setup_handlers"):
            app.state.setup_handlers = {}
        app.state.setup_handlers["test-conv"] = mock_handler

        response = await client.get("/api/setup/wizard-state")
        assert response.status_code == 200
        data = response.json()
        assert data["step"] == "database_check"
        assert data["completed"] is False

        # Cleanup
        del app.state.setup_handlers["test-conv"]

    async def test_wizard_state_done_handler(self, client):
        """When handler is at DONE step, completed should be True."""
        from flydek.agent.setup_handler import SetupStep

        mock_handler = MagicMock()
        mock_handler.current_step = SetupStep.DONE

        transport = client._transport
        app = transport.app
        if not hasattr(app.state, "setup_handlers"):
            app.state.setup_handlers = {}
        app.state.setup_handlers["test-conv"] = mock_handler

        response = await client.get("/api/setup/wizard-state")
        assert response.status_code == 200
        data = response.json()
        assert data["step"] == "done"
        assert data["completed"] is True

        # Cleanup
        del app.state.setup_handlers["test-conv"]
