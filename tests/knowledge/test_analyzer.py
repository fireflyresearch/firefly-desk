# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for DocumentAnalyzer -- LLM-based document classification and analysis."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.knowledge.analyzer import (
    AnalysisResult,
    DocumentAnalyzer,
    DocumentType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis_response(
    document_type: str = "reference",
    summary: str = "A reference document.",
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    section_boundaries: list[int] | None = None,
    suggested_title: str = "Reference Doc",
    is_openapi: bool = False,
) -> str:
    """Build a JSON string matching the expected analysis response schema."""
    return json.dumps(
        {
            "document_type": document_type,
            "summary": summary,
            "tags": tags or ["reference"],
            "entities": entities or [],
            "section_boundaries": section_boundaries or [],
            "suggested_title": suggested_title,
            "is_openapi": is_openapi,
        }
    )


def _make_mock_agent(response_text: str) -> AsyncMock:
    """Create a mock FireflyAgent whose run() returns the given text."""
    agent = AsyncMock()
    result = MagicMock()
    result.output = response_text
    agent.run.return_value = result
    return agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_agent_factory():
    factory = AsyncMock()
    factory.create_agent.return_value = None  # Default: no LLM configured
    return factory


@pytest.fixture
def analyzer(mock_agent_factory):
    return DocumentAnalyzer(mock_agent_factory)


# ---------------------------------------------------------------------------
# Tests: _heuristic_analysis
# ---------------------------------------------------------------------------


class TestHeuristicAnalysis:
    """Tests for DocumentAnalyzer._heuristic_analysis()."""

    def test_detects_openapi_by_filename(self):
        """Files with 'openapi' in the name are classified as api_spec."""
        result = DocumentAnalyzer._heuristic_analysis("some content", "openapi.yaml")
        assert result.document_type == DocumentType.api_spec
        assert result.is_openapi is True

    def test_detects_openapi_by_swagger_filename(self):
        """Files with 'swagger' in the name are classified as api_spec."""
        result = DocumentAnalyzer._heuristic_analysis("some content", "swagger.json")
        assert result.document_type == DocumentType.api_spec
        assert result.is_openapi is True

    def test_detects_openapi_by_content(self):
        """Content containing OpenAPI markers triggers api_spec classification."""
        content = 'openapi: "3.0.0"\ninfo:\n  title: My API'
        result = DocumentAnalyzer._heuristic_analysis(content, "spec.yaml")
        assert result.document_type == DocumentType.api_spec
        assert result.is_openapi is True

    def test_detects_openapi_by_json_content(self):
        """Content with JSON-style openapi key triggers api_spec classification."""
        content = '{"openapi": "3.0.0", "info": {"title": "My API"}}'
        result = DocumentAnalyzer._heuristic_analysis(content, "api.json")
        assert result.document_type == DocumentType.api_spec
        assert result.is_openapi is True

    def test_detects_readme(self):
        """Files with 'readme' in the name are classified as readme."""
        result = DocumentAnalyzer._heuristic_analysis(
            "# My Project\nSome description.", "README.md"
        )
        assert result.document_type == DocumentType.readme
        assert result.is_openapi is False

    def test_detects_changelog(self):
        """Files with 'changelog' in the name are classified as changelog."""
        result = DocumentAnalyzer._heuristic_analysis(
            "## v1.0.0\n- Initial release.", "CHANGELOG.md"
        )
        assert result.document_type == DocumentType.changelog

    def test_detects_release_notes(self):
        """Files with 'release-notes' in the name are classified as changelog."""
        result = DocumentAnalyzer._heuristic_analysis(
            "## v2.0\n- Breaking changes.", "release-notes.md"
        )
        assert result.document_type == DocumentType.changelog

    def test_detects_faq_by_filename(self):
        """Files with 'faq' in the name are classified as faq."""
        result = DocumentAnalyzer._heuristic_analysis("Q: What? A: This.", "FAQ.md")
        assert result.document_type == DocumentType.faq

    def test_detects_policy_by_filename(self):
        """Files with 'policy' in the name are classified as policy."""
        result = DocumentAnalyzer._heuristic_analysis("All users must...", "security-policy.md")
        assert result.document_type == DocumentType.policy

    def test_detects_tutorial_by_filename(self):
        """Files with 'tutorial' in the name are classified as tutorial."""
        result = DocumentAnalyzer._heuristic_analysis("Step 1: ...", "getting-started-tutorial.md")
        assert result.document_type == DocumentType.tutorial

    def test_detects_manual_by_filename(self):
        """Files with 'manual' in the name are classified as manual."""
        result = DocumentAnalyzer._heuristic_analysis("Chapter 1", "user-manual.md")
        assert result.document_type == DocumentType.manual

    def test_unknown_falls_back_to_other(self):
        """Unknown files with no keyword matches fall back to OTHER."""
        result = DocumentAnalyzer._heuristic_analysis(
            "Nothing special here.", "random-notes.md"
        )
        assert result.document_type == DocumentType.other
        assert result.is_openapi is False

    def test_content_keyword_fallback_tutorial(self):
        """Content with tutorial keywords triggers tutorial classification."""
        result = DocumentAnalyzer._heuristic_analysis(
            "Step 1: Install the tool\nStep 2: Configure it", "guide.txt"
        )
        assert result.document_type == DocumentType.tutorial

    def test_suggested_title_derived_from_filename(self):
        """Suggested title is derived from filename with extension stripped."""
        result = DocumentAnalyzer._heuristic_analysis(
            "Content.", "my-great-document.md"
        )
        assert result.suggested_title == "My Great Document"

    def test_summary_from_first_line(self):
        """Summary is taken from the first non-blank line."""
        result = DocumentAnalyzer._heuristic_analysis(
            "\n\n  First meaningful line.\nSecond line.", "doc.md"
        )
        assert result.summary == "First meaningful line."

    def test_tags_from_headings(self):
        """Heading lines are extracted as tags."""
        content = "# Introduction\n## Setup\nSome text.\n## Usage"
        result = DocumentAnalyzer._heuristic_analysis(content, "doc.md")
        assert "introduction" in result.tags
        assert "setup" in result.tags
        assert "usage" in result.tags


# ---------------------------------------------------------------------------
# Tests: _parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    """Tests for DocumentAnalyzer._parse_llm_response()."""

    def test_valid_json(self):
        """A well-formed JSON response is parsed correctly."""
        text = _make_analysis_response(
            document_type="api_spec",
            summary="An API specification for the widget service.",
            tags=["api", "widgets"],
            entities=["WidgetService", "REST"],
            suggested_title="Widget API Spec",
            is_openapi=True,
        )
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.api_spec
        assert result.summary == "An API specification for the widget service."
        assert result.tags == ["api", "widgets"]
        assert result.entities == ["WidgetService", "REST"]
        assert result.suggested_title == "Widget API Spec"
        assert result.is_openapi is True

    def test_markdown_fenced_response(self):
        """JSON wrapped in markdown code fences is handled correctly."""
        inner = _make_analysis_response(
            document_type="tutorial",
            summary="A getting started guide.",
            tags=["tutorial", "setup"],
        )
        text = f"```json\n{inner}\n```"
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.tutorial
        assert result.summary == "A getting started guide."

    def test_plain_code_block(self):
        """JSON wrapped in plain code fences is handled."""
        inner = _make_analysis_response(document_type="readme")
        text = f"```\n{inner}\n```"
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.readme

    def test_invalid_json_returns_none(self):
        """Malformed JSON returns None."""
        result = DocumentAnalyzer._parse_llm_response("this is not json {{{")
        assert result is None

    def test_invalid_document_type_falls_back_to_other(self):
        """An unrecognised document_type value falls back to OTHER."""
        text = _make_analysis_response(document_type="unknown_type_xyz")
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.other

    def test_missing_fields_use_defaults(self):
        """Missing fields in the JSON use sensible defaults."""
        text = json.dumps({"document_type": "faq"})
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.faq
        assert result.summary == ""
        assert result.tags == []
        assert result.entities == []
        assert result.suggested_title == ""
        assert result.is_openapi is False

    def test_whitespace_handling(self):
        """Leading/trailing whitespace is stripped."""
        inner = _make_analysis_response()
        text = f"  \n  {inner}  \n  "
        result = DocumentAnalyzer._parse_llm_response(text)
        assert result is not None
        assert result.document_type == DocumentType.reference


# ---------------------------------------------------------------------------
# Tests: analyze (LLM path)
# ---------------------------------------------------------------------------


class TestAnalyzeLLM:
    """Tests for DocumentAnalyzer.analyze() with an LLM agent."""

    async def test_successful_llm_analysis(self, analyzer, mock_agent_factory):
        """Successful LLM call returns parsed analysis result."""
        response = _make_analysis_response(
            document_type="api_spec",
            summary="Widget API docs.",
            tags=["api", "widget"],
            entities=["WidgetService"],
            suggested_title="Widget API",
            is_openapi=True,
        )
        mock_agent = _make_mock_agent(response)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await analyzer.analyze("openapi: 3.0.0\ninfo: ...", "openapi.yaml")
        assert result.document_type == DocumentType.api_spec
        assert result.summary == "Widget API docs."
        assert result.is_openapi is True
        assert result.suggested_title == "Widget API"

    async def test_no_llm_configured_falls_back(self, analyzer, mock_agent_factory):
        """When no LLM is configured, falls back to heuristic."""
        mock_agent_factory.create_agent.return_value = None
        result = await analyzer.analyze("# My README\nStuff here.", "README.md")
        assert result.document_type == DocumentType.readme

    async def test_llm_exception_falls_back(self, analyzer, mock_agent_factory):
        """LLM call that raises falls back to heuristic."""
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = RuntimeError("API timeout")
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await analyzer.analyze("# Changelog\n## v1.0", "CHANGELOG.md")
        assert result.document_type == DocumentType.changelog

    async def test_llm_invalid_json_falls_back(self, analyzer, mock_agent_factory):
        """When LLM returns unparseable text, falls back to heuristic."""
        mock_agent = _make_mock_agent("Sorry, I cannot analyse this document.")
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await analyzer.analyze("openapi: 3.0.0\ninfo: ...", "openapi.yaml")
        # Should fall back to heuristic which detects OpenAPI by filename
        assert result.document_type == DocumentType.api_spec
        assert result.is_openapi is True

    async def test_content_truncated_for_llm(self, analyzer, mock_agent_factory):
        """Long content is truncated to 8000 chars before sending to LLM."""
        response = _make_analysis_response()
        mock_agent = _make_mock_agent(response)
        mock_agent_factory.create_agent.return_value = mock_agent

        long_content = "x" * 20000
        await analyzer.analyze(long_content, "big-doc.md")

        mock_agent.run.assert_called_once()
        prompt = mock_agent.run.call_args.args[0]
        # Prompt includes filename header + truncated content
        assert len(prompt) < 20000

    async def test_agent_factory_exception_falls_back(self, analyzer, mock_agent_factory):
        """If agent factory raises, falls back to heuristic."""
        mock_agent_factory.create_agent.side_effect = RuntimeError("DB error")

        result = await analyzer.analyze("# FAQ\nQ: What?", "faq.md")
        assert result.document_type == DocumentType.faq


# ---------------------------------------------------------------------------
# Tests: analyze_batch
# ---------------------------------------------------------------------------


class TestAnalyzeBatch:
    """Tests for DocumentAnalyzer.analyze_batch()."""

    async def test_batch_analyzes_multiple_files(self, analyzer, mock_agent_factory):
        """Batch analysis processes all files and returns results."""
        # No LLM configured -- uses heuristic for each file
        mock_agent_factory.create_agent.return_value = None

        files = [
            ("# My Project\nDescription.", "README.md"),
            ("## v1.0\n- Release.", "CHANGELOG.md"),
            ("openapi: 3.0.0\ninfo: ...", "openapi.yaml"),
        ]

        results = await analyzer.analyze_batch(files)
        assert len(results) == 3
        assert results[0].document_type == DocumentType.readme
        assert results[1].document_type == DocumentType.changelog
        assert results[2].document_type == DocumentType.api_spec

    async def test_batch_calls_progress_callback(self, analyzer, mock_agent_factory):
        """Progress callback is invoked for each file."""
        mock_agent_factory.create_agent.return_value = None
        progress_calls: list[tuple[int, int]] = []

        def on_progress(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        files = [
            ("Content A.", "a.md"),
            ("Content B.", "b.md"),
        ]
        results = await analyzer.analyze_batch(files, on_progress=on_progress)
        assert len(results) == 2
        assert progress_calls == [(1, 2), (2, 2)]

    async def test_batch_calls_async_progress_callback(self, analyzer, mock_agent_factory):
        """Async progress callback is awaited for each file."""
        mock_agent_factory.create_agent.return_value = None
        progress_calls: list[tuple[int, int]] = []

        async def on_progress(completed: int, total: int) -> None:
            progress_calls.append((completed, total))

        files = [
            ("Content A.", "a.md"),
            ("Content B.", "b.md"),
            ("Content C.", "c.md"),
        ]
        results = await analyzer.analyze_batch(files, on_progress=on_progress)
        assert len(results) == 3
        assert progress_calls == [(1, 3), (2, 3), (3, 3)]

    async def test_batch_empty_list(self, analyzer):
        """Empty file list returns empty results."""
        results = await analyzer.analyze_batch([])
        assert results == []
