# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for embedding factory."""

from __future__ import annotations

import importlib

import pytest

_has_google_genai = importlib.util.find_spec("google.generativeai") is not None
_has_voyageai = importlib.util.find_spec("voyageai") is not None

from flydesk.domain.exceptions import ConfigurationError, ProviderNotFoundError
from flydesk.knowledge.embedding_factory import create_embedder, parse_embedding_config

# Dummy API keys so provider SDKs don't raise during construction.
_DUMMY_ENV = {
    "OPENAI_API_KEY": "sk-test-dummy",
    "AZURE_OPENAI_API_KEY": "az-test-dummy",
    "GOOGLE_API_KEY": "goog-test-dummy",
    "VOYAGE_API_KEY": "voy-test-dummy",
    "CO_API_KEY": "co-test-dummy",
    "MISTRAL_API_KEY": "mis-test-dummy",
    "AWS_ACCESS_KEY_ID": "AKIAIOSFODNN7EXAMPLE",
    "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "AWS_DEFAULT_REGION": "us-east-1",
}


@pytest.fixture(autouse=True)
def _fake_api_keys(monkeypatch):
    """Inject dummy API keys so provider constructors don't reject init."""
    for key, value in _DUMMY_ENV.items():
        monkeypatch.setenv(key, value)


# -- parse_embedding_config ---------------------------------------------------


def test_parse_valid_config():
    provider, model = parse_embedding_config("openai:text-embedding-3-small")
    assert provider == "openai"
    assert model == "text-embedding-3-small"


def test_parse_config_with_colon_in_model():
    provider, model = parse_embedding_config("azure:my-deployment:v2")
    assert provider == "azure"
    assert model == "my-deployment:v2"


def test_parse_config_strips_whitespace():
    provider, model = parse_embedding_config("  openai : text-embedding-3-small  ")
    assert provider == "openai"
    assert model == "text-embedding-3-small"


def test_parse_config_lowercases_provider():
    provider, model = parse_embedding_config("OpenAI:text-embedding-3-small")
    assert provider == "openai"


def test_parse_invalid_config_no_colon():
    with pytest.raises(ConfigurationError, match="format"):
        parse_embedding_config("just-a-model-name")


def test_parse_empty_string():
    with pytest.raises(ConfigurationError):
        parse_embedding_config("")


# -- create_embedder -----------------------------------------------------------


def test_create_embedder_openai():
    embedder = create_embedder("openai", "text-embedding-3-small", dimensions=1536)
    from fireflyframework_genai.embeddings.providers import OpenAIEmbedder

    assert isinstance(embedder, OpenAIEmbedder)


def test_create_embedder_ollama():
    embedder = create_embedder("ollama", "nomic-embed-text")
    from fireflyframework_genai.embeddings.providers import OllamaEmbedder

    assert isinstance(embedder, OllamaEmbedder)


def test_create_embedder_ollama_with_base_url():
    embedder = create_embedder(
        "ollama", "nomic-embed-text", base_url="http://myhost:11434"
    )
    from fireflyframework_genai.embeddings.providers import OllamaEmbedder

    assert isinstance(embedder, OllamaEmbedder)
    assert embedder._base_url == "http://myhost:11434"


def test_create_embedder_azure_with_base_url():
    embedder = create_embedder(
        "azure", "my-deployment", base_url="https://myinstance.openai.azure.com"
    )
    from fireflyframework_genai.embeddings.providers import AzureEmbedder

    assert isinstance(embedder, AzureEmbedder)


@pytest.mark.skipif(not _has_google_genai, reason="google-generativeai not installed")
def test_create_embedder_google():
    embedder = create_embedder("google", "models/text-embedding-004")
    from fireflyframework_genai.embeddings.providers import GoogleEmbedder

    assert isinstance(embedder, GoogleEmbedder)


@pytest.mark.skipif(not _has_voyageai, reason="voyageai not installed")
def test_create_embedder_voyage():
    embedder = create_embedder("voyage", "voyage-3")
    from fireflyframework_genai.embeddings.providers import VoyageEmbedder

    assert isinstance(embedder, VoyageEmbedder)


def test_create_embedder_cohere():
    embedder = create_embedder("cohere", "embed-english-v3.0")
    from fireflyframework_genai.embeddings.providers import CohereEmbedder

    assert isinstance(embedder, CohereEmbedder)


def test_create_embedder_mistral():
    embedder = create_embedder("mistral", "mistral-embed")
    from fireflyframework_genai.embeddings.providers import MistralEmbedder

    assert isinstance(embedder, MistralEmbedder)


def test_create_embedder_bedrock():
    embedder = create_embedder("bedrock", "amazon.titan-embed-text-v2:0")
    from fireflyframework_genai.embeddings.providers import BedrockEmbedder

    assert isinstance(embedder, BedrockEmbedder)


def test_create_embedder_unknown_provider():
    with pytest.raises(ProviderNotFoundError, match="foobar"):
        create_embedder("foobar", "some-model")


def test_create_embedder_with_api_key():
    embedder = create_embedder("openai", "text-embedding-3-small", api_key="sk-test")
    assert embedder is not None


def test_create_embedder_case_insensitive():
    embedder = create_embedder("OpenAI", "text-embedding-3-small")
    from fireflyframework_genai.embeddings.providers import OpenAIEmbedder

    assert isinstance(embedder, OpenAIEmbedder)


def test_create_embedder_base_url_ignored_for_non_ollama_azure():
    """base_url is only used for ollama and azure; should be ignored for others."""
    embedder = create_embedder(
        "openai", "text-embedding-3-small", base_url="https://custom.api.com"
    )
    assert embedder is not None
