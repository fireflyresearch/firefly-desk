# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for KGExtractSingleHandler -- per-document KG extraction."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from flydesk.jobs.handlers import KGExtractSingleHandler


@dataclass
class _FakeDoc:
    id: str
    title: str
    content: str


@pytest.fixture
def mock_catalog_repo():
    return AsyncMock()


@pytest.fixture
def mock_knowledge_graph():
    graph = AsyncMock()
    graph.upsert_entity = AsyncMock()
    graph.add_relation = AsyncMock()
    return graph


@pytest.fixture
def mock_extractor():
    return AsyncMock()


@pytest.fixture
def handler(mock_catalog_repo, mock_knowledge_graph, mock_extractor):
    return KGExtractSingleHandler(
        catalog_repo=mock_catalog_repo,
        knowledge_graph=mock_knowledge_graph,
        extractor=mock_extractor,
    )


@pytest.fixture
def on_progress():
    return AsyncMock()


class TestKGExtractSingleHandler:
    async def test_extracts_entities_and_relations(
        self, handler, mock_catalog_repo, mock_knowledge_graph, mock_extractor, on_progress
    ):
        """Extracts entities and relations from a single document."""
        doc = _FakeDoc(id="doc-1", title="Test Doc", content="Some content about services.")
        mock_catalog_repo.get_knowledge_document.return_value = doc

        mock_extractor.extract_from_document.return_value = (
            [
                {
                    "id": "ent-1",
                    "entity_type": "service",
                    "name": "Auth Service",
                    "properties": {},
                    "confidence": 0.9,
                }
            ],
            [
                {
                    "source_id": "ent-1",
                    "target_id": "ent-2",
                    "relation_type": "depends_on",
                    "properties": {},
                    "confidence": 0.8,
                }
            ],
        )

        result = await handler.execute("job-1", {"document_id": "doc-1"}, on_progress)

        assert result["document_id"] == "doc-1"
        assert result["entities"] == 1
        assert result["relations"] == 1
        mock_knowledge_graph.upsert_entity.assert_awaited_once()
        mock_knowledge_graph.add_relation.assert_awaited_once()

    async def test_skips_when_document_not_found(
        self, handler, mock_catalog_repo, on_progress
    ):
        """Returns skipped=True when document doesn't exist."""
        mock_catalog_repo.get_knowledge_document.return_value = None

        result = await handler.execute("job-2", {"document_id": "missing"}, on_progress)

        assert result["skipped"] is True
        assert result["entities"] == 0
        assert result["relations"] == 0

    async def test_skips_when_document_has_no_content(
        self, handler, mock_catalog_repo, on_progress
    ):
        """Returns skipped=True when document content is empty."""
        doc = _FakeDoc(id="doc-empty", title="Empty", content="")
        mock_catalog_repo.get_knowledge_document.return_value = doc

        result = await handler.execute("job-3", {"document_id": "doc-empty"}, on_progress)

        assert result["skipped"] is True

    async def test_handles_extraction_failure(
        self, handler, mock_catalog_repo, mock_extractor, on_progress
    ):
        """Returns error=True when extraction fails."""
        doc = _FakeDoc(id="doc-err", title="Broken", content="Some content")
        mock_catalog_repo.get_knowledge_document.return_value = doc
        mock_extractor.extract_from_document.side_effect = RuntimeError("LLM unavailable")

        result = await handler.execute("job-4", {"document_id": "doc-err"}, on_progress)

        assert result["error"] is True
        assert result["entities"] == 0
        assert result["relations"] == 0

    async def test_reports_progress(
        self, handler, mock_catalog_repo, mock_extractor, on_progress
    ):
        """Calls on_progress at start and completion."""
        doc = _FakeDoc(id="doc-prog", title="Progress Test", content="Content")
        mock_catalog_repo.get_knowledge_document.return_value = doc
        mock_extractor.extract_from_document.return_value = ([], [])

        await handler.execute("job-5", {"document_id": "doc-prog"}, on_progress)

        calls = on_progress.call_args_list
        assert len(calls) >= 2
        assert calls[0][0][0] == 10  # initial progress
        assert calls[-1][0][0] == 100  # completion
