# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tavily web search adapter."""

from __future__ import annotations

import logging

import httpx

from flydesk.search.provider import SearchProviderFactory, SearchResult

logger = logging.getLogger(__name__)

_DEFAULT_TAVILY_API_URL = "https://api.tavily.com"


class TavilyAdapter:
    """Search provider using the Tavily search API."""

    def __init__(
        self,
        api_key: str,
        *,
        api_url: str = _DEFAULT_TAVILY_API_URL,
        max_results: int = 5,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url.rstrip("/")
        self._max_results = max_results
        self._client = httpx.AsyncClient(timeout=30.0)

    async def search(
        self, query: str, *, max_results: int | None = None
    ) -> list[SearchResult]:
        return await self._do_search(
            query, max_results=max_results or self._max_results, include_raw_content=False
        )

    async def search_with_content(
        self, query: str, *, max_results: int | None = None
    ) -> list[SearchResult]:
        return await self._do_search(
            query, max_results=max_results or min(self._max_results, 3), include_raw_content=True
        )

    async def _do_search(
        self, query: str, *, max_results: int, include_raw_content: bool
    ) -> list[SearchResult]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
        }
        try:
            response = await self._client.post(f"{self._api_url}/search", json=payload)
            response.raise_for_status()
        except Exception:
            logger.warning("Tavily search failed for query: %s", query, exc_info=True)
            return []

        data = response.json()
        results: list[SearchResult] = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    content=item.get("raw_content") if include_raw_content else None,
                    score=item.get("score"),
                    published_date=item.get("published_date"),
                )
            )
        return results

    async def aclose(self) -> None:
        await self._client.aclose()


# Auto-register with the factory
SearchProviderFactory.register("tavily", TavilyAdapter)
