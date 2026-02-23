# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for embedding and vector store persistence during setup configure."""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base


@pytest.fixture
async def db_client():
    """Client with a real in-memory database wired into app state.

    Mirrors the ``db_client`` fixture in ``test_setup.py``.
    """
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


def _get_session_factory(client: AsyncClient):
    """Extract the session factory from the test client's app state."""
    return client._transport.app.state.session_factory  # type: ignore[union-attr]


class TestEmbeddingConfigure:
    """POST /api/setup/configure with embedding config."""

    async def test_embedding_config_persists_model(self, db_client):
        """Embedding model should be persisted as 'provider:model' format."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-test-emb-key",
                    "dimensions": 1536,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["embedding"] == "configured"

        # Verify persisted settings
        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="embedding")
        assert settings["embedding_model"] == "openai:text-embedding-3-small"
        assert settings["embedding_api_key"] == "sk-test-emb-key"
        assert settings["embedding_dimensions"] == "1536"

    async def test_embedding_config_persists_base_url(self, db_client):
        """When base_url is provided, it should be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "embedding": {
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "base_url": "http://localhost:11434",
                    "dimensions": 768,
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="embedding")
        assert settings["embedding_model"] == "ollama:nomic-embed-text"
        assert settings["embedding_base_url"] == "http://localhost:11434"
        assert settings["embedding_dimensions"] == "768"
        # api_key was not provided, so it should not be stored
        assert "embedding_api_key" not in settings

    async def test_embedding_config_omits_null_optional_fields(self, db_client):
        """Optional fields that are None should not be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-large",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="embedding")
        assert settings["embedding_model"] == "openai:text-embedding-3-large"
        assert settings["embedding_dimensions"] == "1536"  # default
        assert "embedding_api_key" not in settings
        assert "embedding_base_url" not in settings

    async def test_embedding_triggers_reinitialize(self, db_client):
        """When embedding is provided, _reinitialize_embedding_provider should be called."""
        mock_reinit = AsyncMock()
        with patch(
            "flydesk.api.settings._reinitialize_embedding_provider",
            mock_reinit,
        ):
            response = await db_client.post(
                "/api/setup/configure",
                json={
                    "embedding": {
                        "provider": "openai",
                        "model": "text-embedding-3-small",
                        "api_key": "sk-test",
                    },
                },
            )
            assert response.status_code == 200
            assert response.json()["success"] is True
            mock_reinit.assert_awaited_once()


class TestVectorStoreConfigure:
    """POST /api/setup/configure with vector_store config."""

    async def test_vector_store_sqlite_persists(self, db_client):
        """SQLite vector store type should be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "vector_store": {"type": "sqlite"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["vector_store"] == "configured"

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="vector_store")
        assert settings["type"] == "sqlite"

    async def test_vector_store_chromadb_persists(self, db_client):
        """ChromaDB vector store settings should be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "vector_store": {
                    "type": "chromadb",
                    "chroma_path": "/data/chroma",
                    "chroma_url": "http://chroma:8000",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="vector_store")
        assert settings["type"] == "chromadb"
        assert settings["chroma_path"] == "/data/chroma"
        assert settings["chroma_url"] == "http://chroma:8000"

    async def test_vector_store_pinecone_persists(self, db_client):
        """Pinecone vector store settings should be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "vector_store": {
                    "type": "pinecone",
                    "pinecone_api_key": "pk-test-key",
                    "pinecone_index_name": "flydesk-idx",
                    "pinecone_environment": "us-east-1",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="vector_store")
        assert settings["type"] == "pinecone"
        assert settings["pinecone_api_key"] == "pk-test-key"
        assert settings["pinecone_index_name"] == "flydesk-idx"
        assert settings["pinecone_environment"] == "us-east-1"

    async def test_vector_store_omits_null_optional_fields(self, db_client):
        """Optional fields that are None should not be persisted."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "vector_store": {"type": "pgvector"},
            },
        )
        assert response.status_code == 200

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        settings = await repo.get_all_app_settings(category="vector_store")
        assert settings == {"type": "pgvector"}


class TestEmbeddingAndVectorStoreCombined:
    """Configure with both embedding and vector_store together."""

    async def test_both_embedding_and_vector_store_persist(self, db_client):
        """Both embedding and vector store should be persisted in one call."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-test-key",
                    "dimensions": 1536,
                },
                "vector_store": {
                    "type": "chromadb",
                    "chroma_path": "/data/chroma",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["embedding"] == "configured"
        assert data["details"]["vector_store"] == "configured"
        assert data["details"]["setup_completed"] is True

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))

        emb_settings = await repo.get_all_app_settings(category="embedding")
        assert emb_settings["embedding_model"] == "openai:text-embedding-3-small"

        vs_settings = await repo.get_all_app_settings(category="vector_store")
        assert vs_settings["type"] == "chromadb"
        assert vs_settings["chroma_path"] == "/data/chroma"

    async def test_full_setup_with_all_sections(self, db_client):
        """Configure with LLM, embedding, vector store, and agent settings."""
        response = await db_client.post(
            "/api/setup/configure",
            json={
                "llm_provider": {
                    "name": "OpenAI",
                    "provider_type": "openai",
                    "api_key": "sk-llm-key",
                },
                "embedding": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "api_key": "sk-emb-key",
                    "dimensions": 1536,
                },
                "vector_store": {
                    "type": "sqlite",
                },
                "agent_settings": {
                    "name": "TestBot",
                    "display_name": "Test Bot",
                    "personality": "helpful",
                    "tone": "professional",
                    "greeting": "Hi, I'm Test Bot!",
                },
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["details"]["llm_provider"] == "configured"
        assert data["details"]["embedding"] == "configured"
        assert data["details"]["vector_store"] == "configured"
        assert data["details"]["agent_settings"] == "configured"
        assert data["details"]["setup_completed"] is True

    async def test_configure_without_embedding_skips_embedding_step(self, db_client):
        """When no embedding or vector_store is provided, no settings should be created."""
        response = await db_client.post(
            "/api/setup/configure",
            json={},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "embedding" not in data["details"]
        assert "vector_store" not in data["details"]

        from flydesk.settings.repository import SettingsRepository

        repo = SettingsRepository(_get_session_factory(db_client))
        emb_settings = await repo.get_all_app_settings(category="embedding")
        assert emb_settings == {}
        vs_settings = await repo.get_all_app_settings(category="vector_store")
        assert vs_settings == {}
