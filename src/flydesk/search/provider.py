# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Search provider protocol, data classes, and factory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class SearchResult:
    """A single web search result."""

    title: str
    url: str
    snippet: str
    content: str | None = None
    score: float | None = None
    published_date: str | None = None


@runtime_checkable
class SearchProvider(Protocol):
    """Protocol for pluggable web search engine adapters."""

    async def search(
        self, query: str, *, max_results: int = 5
    ) -> list[SearchResult]: ...

    async def search_with_content(
        self, query: str, *, max_results: int = 3
    ) -> list[SearchResult]: ...

    async def aclose(self) -> None: ...


class SearchProviderFactory:
    """Registry-based factory for search provider adapters."""

    _registry: dict[str, type] = {}

    @classmethod
    def register(cls, name: str, adapter_cls: type) -> None:
        cls._registry[name] = adapter_cls

    @classmethod
    def create(cls, provider_name: str, config: dict) -> SearchProvider:
        adapter_cls = cls._registry.get(provider_name)
        if adapter_cls is None:
            raise ValueError(f"Unknown search provider: {provider_name}")
        return adapter_cls(**config)

    @classmethod
    def available_providers(cls) -> list[str]:
        return list(cls._registry.keys())
