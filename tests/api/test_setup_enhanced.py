# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the enhanced setup wizard features:
- POST /api/setup/test-database endpoint
- Agent settings support in POST /api/setup/configure
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDESK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydesk.server import create_app

        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def db_client():
    """Client with a real in-memory database wired into app state."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        "FLYDESK_AGENT_NAME": "Ember",
    }
    with patch.dict(os.environ, env):
        from flydesk.config import get_config
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        config = get_config()
        app.state.config = config
        app.state.session_factory = session_factory

        # Override knowledge indexer so seed endpoints work without real embeddings
        from flydesk.api.knowledge import get_knowledge_indexer
        from flydesk.knowledge.indexer import KnowledgeIndexer

        class _NoOpEmbedding:
            async def embed(self, texts):
                return [[0.0] * 4 for _ in texts]

        indexer = KnowledgeIndexer(
            session_factory=session_factory,
            embedding_provider=_NoOpEmbedding(),
        )
        app.dependency_overrides[get_knowledge_indexer] = lambda: indexer

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


class TestDatabaseEndpoint:
    """Tests for POST /api/setup/test-database."""

    async def test_test_database_current_connection(self, db_client):
        """Testing current database (empty connection_string) should succeed."""
        response = await db_client.post(
            "/api/setup/test-database",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["database_type"] == "SQLite"

    async def test_test_database_with_empty_string(self, db_client):
        """Explicitly passing empty connection_string tests current DB."""
        response = await db_client.post(
            "/api/setup/test-database",
            json={"connection_string": ""},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    async def test_test_database_invalid_connection_string(self, db_client):
        """Invalid connection string should return failure."""
        response = await db_client.post(
            "/api/setup/test-database",
            json={"connection_string": "postgresql+asyncpg://bad:bad@nonexistent:5432/nope"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["database_type"] == "PostgreSQL"
        assert data["error"] is not None

    async def test_test_database_without_session_factory(self, client):
        """Without a session factory and empty connection string, should fail."""
        response = await client.post(
            "/api/setup/test-database",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "No database session" in data["error"]


class TestConfigureWithAgentSettings:
    """Tests for agent_settings support in POST /api/setup/configure."""

    async def test_configure_with_agent_settings(self, db_client):
        """Configure with agent_settings should store them."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "agent_settings": {
                    "name": "Atlas",
                    "display_name": "Atlas AI",
                    "personality": "efficient, precise, direct",
                    "tone": "professional",
                    "greeting": "Hello! I'm {name}, ready to help.",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["agent_settings"] == "configured"

    async def test_configure_with_agent_and_llm(self, db_client):
        """Configure with both agent settings and LLM provider."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "Test OpenAI",
                    "provider_type": "openai",
                    "api_key": "sk-test-123",
                },
                "agent_settings": {
                    "name": "Spark",
                    "display_name": "Spark",
                    "personality": "cheerful, approachable, casual",
                    "tone": "casual",
                    "greeting": "Hey there! I'm {name}.",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["llm_provider"] == "configured"
        assert data["details"]["agent_settings"] == "configured"
        assert data["details"]["setup_completed"] is True

    async def test_configure_agent_settings_persisted(self, db_client):
        """Agent settings should be retrievable after configure."""
        # Configure with custom agent settings
        await db_client.post(
            "/api/setup/configure",
            json={
                "agent_settings": {
                    "name": "Nova",
                    "display_name": "Nova AI",
                    "personality": "warm, empathetic",
                    "tone": "friendly",
                    "greeting": "Hi! I'm {name}, how can I help?",
                },
            },
        )

        # Verify the settings were persisted by reading from the repository
        session_factory = db_client._transport.app.state.session_factory
        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(session_factory)
        agent = await repo.get_agent_settings()
        assert agent.name == "Nova"
        assert agent.display_name == "Nova AI"
        assert agent.personality == "warm, empathetic"
        assert agent.tone == "friendly"
        assert agent.greeting == "Hi! I'm {name}, how can I help?"

    async def test_configure_without_agent_settings(self, db_client):
        """Configure without agent_settings should still succeed."""
        response = await db_client.post(
            "/api/setup/configure",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "agent_settings" not in data.get("details", {})

    async def test_configure_all_options(self, db_client):
        """Configure with LLM, seed data, and agent settings all at once."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "Test Anthropic",
                    "provider_type": "anthropic",
                    "api_key": "sk-ant-test",
                },
                "seed_data": True,
                "agent_settings": {
                    "name": "Ember",
                    "display_name": "Ember",
                    "personality": "warm, professional, knowledgeable",
                    "tone": "friendly",
                    "greeting": "Hello! I'm {name}, your intelligent assistant.",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["llm_provider"] == "configured"
        assert data["details"]["seed_data"] == "loaded"
        assert data["details"]["agent_settings"] == "configured"
        assert data["details"]["setup_completed"] is True
