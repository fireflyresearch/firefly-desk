# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for LLMProviderRepository."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydek.llm.models import LLMProvider, ProviderType
from flydek.llm.repository import LLMProviderRepository
from flydek.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return LLMProviderRepository(session_factory)


@pytest.fixture
def sample_provider() -> LLMProvider:
    return LLMProvider(
        id="openai-1",
        name="Production OpenAI",
        provider_type=ProviderType.OPENAI,
        api_key="sk-test-key-12345",
        base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
    )


class TestLLMProviderRepository:
    async def test_create_and_get_provider(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        result = await repo.get_provider("openai-1")
        assert result is not None
        assert result.name == "Production OpenAI"
        assert result.provider_type == ProviderType.OPENAI
        assert result.api_key == "sk-test-key-12345"
        assert result.default_model == "gpt-4o"

    async def test_get_provider_not_found(self, repo):
        result = await repo.get_provider("nonexistent")
        assert result is None

    async def test_list_providers(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        providers = await repo.list_providers()
        assert len(providers) == 1
        assert providers[0].id == "openai-1"

    async def test_list_providers_empty(self, repo):
        providers = await repo.list_providers()
        assert providers == []

    async def test_update_provider(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        sample_provider.name = "Updated OpenAI"
        sample_provider.default_model = "gpt-4o-mini"
        await repo.update_provider(sample_provider)
        result = await repo.get_provider("openai-1")
        assert result is not None
        assert result.name == "Updated OpenAI"
        assert result.default_model == "gpt-4o-mini"

    async def test_update_provider_preserves_api_key_when_none(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        # Update with api_key=None should preserve existing key
        sample_provider.api_key = None
        await repo.update_provider(sample_provider)
        result = await repo.get_provider("openai-1")
        assert result is not None
        assert result.api_key == "sk-test-key-12345"

    async def test_delete_provider(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        await repo.delete_provider("openai-1")
        result = await repo.get_provider("openai-1")
        assert result is None

    async def test_set_default_provider(self, repo, sample_provider):
        await repo.create_provider(sample_provider)

        # Create a second provider
        second = LLMProvider(
            id="anthropic-1",
            name="Anthropic",
            provider_type=ProviderType.ANTHROPIC,
            api_key="sk-ant-test",
        )
        await repo.create_provider(second)

        # Set first as default
        await repo.set_default("openai-1")
        result = await repo.get_provider("openai-1")
        assert result is not None
        assert result.is_default is True

        # Set second as default (should unset first)
        await repo.set_default("anthropic-1")
        first = await repo.get_provider("openai-1")
        second_result = await repo.get_provider("anthropic-1")
        assert first is not None
        assert first.is_default is False
        assert second_result is not None
        assert second_result.is_default is True

    async def test_get_default_provider(self, repo, sample_provider):
        await repo.create_provider(sample_provider)
        await repo.set_default("openai-1")

        result = await repo.get_default_provider()
        assert result is not None
        assert result.id == "openai-1"
        assert result.is_default is True

    async def test_get_default_provider_none(self, repo):
        result = await repo.get_default_provider()
        assert result is None

    async def test_api_key_encryption_roundtrip(self, repo, sample_provider):
        """Verify the API key is encrypted at rest and decrypted on read."""
        await repo.create_provider(sample_provider)
        result = await repo.get_provider("openai-1")
        assert result is not None
        assert result.api_key == "sk-test-key-12345"
