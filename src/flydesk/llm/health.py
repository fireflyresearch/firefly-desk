# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Health checker for LLM provider connectivity."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

_logger = logging.getLogger(__name__)

from flydesk.llm.models import LLMProvider, ProviderHealthStatus, ProviderType

# Default base URLs for known providers
_DEFAULT_URLS: dict[str, str] = {
    ProviderType.OPENAI: "https://api.openai.com/v1",
    ProviderType.ANTHROPIC: "https://api.anthropic.com/v1",
    ProviderType.GOOGLE: "https://generativelanguage.googleapis.com/v1beta",
    ProviderType.AZURE_OPENAI: "",  # requires custom base_url
    ProviderType.OLLAMA: "http://localhost:11434",
}

# Health-check paths per provider type
_HEALTH_PATHS: dict[str, str] = {
    ProviderType.OPENAI: "/models",
    ProviderType.ANTHROPIC: "/models",
    ProviderType.GOOGLE: "/models",
    ProviderType.AZURE_OPENAI: "/openai/models",
    ProviderType.OLLAMA: "/api/tags",
}


class LLMHealthChecker:
    """Test LLM provider connectivity with a lightweight API call."""

    async def check(self, provider: LLMProvider) -> ProviderHealthStatus:
        """Test provider connectivity and return a health status."""
        base = provider.base_url or _DEFAULT_URLS.get(provider.provider_type, "")
        if not base:
            return ProviderHealthStatus(
                provider_id=provider.id,
                name=provider.name,
                reachable=False,
                error="No base URL configured",
                checked_at=datetime.now(timezone.utc),
            )

        path = _HEALTH_PATHS.get(provider.provider_type, "/models")
        url = f"{base.rstrip('/')}{path}"

        headers: dict[str, str] = {}
        if provider.api_key:
            if provider.provider_type == ProviderType.ANTHROPIC:
                headers["x-api-key"] = provider.api_key
            elif provider.provider_type == ProviderType.GOOGLE:
                # Google uses query parameter, but header works for health check
                url = f"{url}?key={provider.api_key}"
            else:
                headers["Authorization"] = f"Bearer {provider.api_key}"

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                latency = (time.monotonic() - start) * 1000

                if response.status_code < 400:
                    return ProviderHealthStatus(
                        provider_id=provider.id,
                        name=provider.name,
                        reachable=True,
                        latency_ms=round(latency, 1),
                        checked_at=datetime.now(timezone.utc),
                    )
                return ProviderHealthStatus(
                    provider_id=provider.id,
                    name=provider.name,
                    reachable=False,
                    latency_ms=round(latency, 1),
                    error=f"HTTP {response.status_code}",
                    checked_at=datetime.now(timezone.utc),
                )
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            return ProviderHealthStatus(
                provider_id=provider.id,
                name=provider.name,
                reachable=False,
                latency_ms=round(latency, 1),
                error=str(exc),
                checked_at=datetime.now(timezone.utc),
            )

    async def list_models(self, provider: LLMProvider) -> list[str]:
        """Fetch available model IDs from the provider's models endpoint."""
        base = provider.base_url or _DEFAULT_URLS.get(provider.provider_type, "")
        if not base:
            return []

        path = _HEALTH_PATHS.get(provider.provider_type, "/models")
        url = f"{base.rstrip('/')}{path}"

        headers: dict[str, str] = {}
        if provider.api_key:
            if provider.provider_type == ProviderType.ANTHROPIC:
                headers["x-api-key"] = provider.api_key
            elif provider.provider_type == ProviderType.GOOGLE:
                url = f"{url}?key={provider.api_key}"
            else:
                headers["Authorization"] = f"Bearer {provider.api_key}"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code >= 400:
                    return []
                data = resp.json()
                # OpenAI-compatible: {"data": [{"id": "gpt-4"}, ...]}
                if "data" in data:
                    return [m.get("id", "") for m in data["data"] if isinstance(m, dict)]
                # Ollama: {"models": [{"name": "llama3"}, ...]}
                if "models" in data:
                    return [m.get("name", "") for m in data["models"] if isinstance(m, dict)]
                return []
        except Exception:
            _logger.debug("Failed to list models from provider.", exc_info=True)
            return []
