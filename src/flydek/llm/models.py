# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for LLM provider configuration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ProviderType(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"


class ModelCapabilities(BaseModel):
    context_window: int = 128000
    supports_vision: bool = False
    supports_function_calling: bool = True
    supports_streaming: bool = True
    max_output_tokens: int | None = None


class LLMModel(BaseModel):
    id: str
    name: str
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)


class LLMProvider(BaseModel):
    id: str
    name: str
    provider_type: ProviderType
    api_key: str | None = None  # plain text on input
    base_url: str | None = None
    models: list[LLMModel] = Field(default_factory=list)
    default_model: str | None = None
    capabilities: dict[str, bool] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    is_active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LLMProviderResponse(LLMProvider):
    """Response model that never exposes the API key."""

    api_key: str | None = Field(default=None, exclude=True)
    has_api_key: bool = False


class ProviderHealthStatus(BaseModel):
    provider_id: str
    name: str
    reachable: bool
    latency_ms: float | None = None
    error: str | None = None
    checked_at: datetime
