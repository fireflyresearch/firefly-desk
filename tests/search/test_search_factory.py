# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SearchProviderFactory."""

from __future__ import annotations

import pytest

from flydesk.search.provider import SearchProviderFactory, SearchResult


def test_factory_create_unknown_raises():
    with pytest.raises(ValueError, match="Unknown search provider"):
        SearchProviderFactory.create("nonexistent", {})


def test_factory_register_and_create():
    class FakeProvider:
        def __init__(self, api_key: str) -> None:
            self.api_key = api_key
        async def search(self, query, *, max_results=5):
            return []
        async def search_with_content(self, query, *, max_results=3):
            return []
        async def aclose(self):
            pass

    SearchProviderFactory.register("fake_test", FakeProvider)
    provider = SearchProviderFactory.create("fake_test", {"api_key": "test-key"})
    assert provider.api_key == "test-key"
    SearchProviderFactory._registry.pop("fake_test", None)


def test_search_result_dataclass():
    result = SearchResult(
        title="Test", url="https://example.com", snippet="A snippet"
    )
    assert result.title == "Test"
    assert result.content is None
    assert result.score is None
