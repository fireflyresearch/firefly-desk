"""Tests for KGRecomputeHandler checkpoint support."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.jobs.handlers import ExecutionResult, KGRecomputeHandler


def _make_doc(doc_id, title, content):
    doc = MagicMock()
    doc.title = title
    doc.content = content
    doc.id = doc_id
    return doc


@pytest.fixture
def handler():
    catalog = AsyncMock()
    kg = AsyncMock()
    extractor = AsyncMock()
    extractor.extract_from_document.return_value = ([], [])
    return KGRecomputeHandler(catalog, kg, extractor), catalog, extractor


class TestKGRecomputeCheckpoint:
    async def test_pauses_at_boundary(self, handler):
        h, catalog, extractor = handler
        catalog.list_knowledge_documents.return_value = [
            _make_doc("d1", "Doc 1", "content1"),
            _make_doc("d2", "Doc 2", "content2"),
            _make_doc("d3", "Doc 3", "content3"),
        ]

        call_count = 0
        def pause_after_one():
            nonlocal call_count
            call_count += 1
            return call_count >= 2  # pause after processing first doc

        progress = AsyncMock()
        result = await h.execute("j-1", {}, progress, should_pause=pause_after_one)

        assert isinstance(result, ExecutionResult)
        assert result.is_paused
        assert result.checkpoint["current_index"] == 2
        assert extractor.extract_from_document.call_count == 2

    async def test_resumes_from_checkpoint(self, handler):
        h, catalog, extractor = handler
        docs = [
            _make_doc("d1", "Doc 1", "c1"),
            _make_doc("d2", "Doc 2", "c2"),
            _make_doc("d3", "Doc 3", "c3"),
        ]
        catalog.list_knowledge_documents.return_value = docs

        progress = AsyncMock()
        result = await h.execute(
            "j-1", {}, progress,
            checkpoint={"current_index": 2, "entities_added": 0, "relations_added": 0},
        )

        assert isinstance(result, ExecutionResult) or isinstance(result, dict)
        # Should only process doc at index 2 (d3)
        extractor.extract_from_document.assert_called_once()
        call_args = extractor.extract_from_document.call_args
        assert call_args[0][1] == "Doc 3"
