# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for ToolFactory.build_system_context."""

from __future__ import annotations

from flydesk.catalog.models import ExternalSystem, SystemTag
from flydesk.knowledge.models import KnowledgeDocument
from flydesk.tools.factory import ToolFactory


def _make_system(
    *,
    name: str = "Jira",
    description: str = "Project tracking tool",
    base_url: str = "https://jira.example.com",
    tags: list[SystemTag] | None = None,
) -> ExternalSystem:
    return ExternalSystem(
        id="sys-1",
        name=name,
        description=description,
        base_url=base_url,
        tags=tags or [],
    )


def _make_doc(
    *,
    doc_id: str = "doc-1",
    title: str = "API Guide",
    content: str = "Short content",
) -> KnowledgeDocument:
    return KnowledgeDocument(id=doc_id, title=title, content=content)


class TestBuildSystemContext:
    """Tests for ToolFactory.build_system_context()."""

    def test_basic_context(self):
        """System with tags produces name, description, base URL, and tag names."""
        tags = [
            SystemTag(id="t1", name="engineering"),
            SystemTag(id="t2", name="agile"),
        ]
        system = _make_system(tags=tags)
        result = ToolFactory.build_system_context(system, linked_docs=[])

        assert "## Jira" in result
        assert "Project tracking tool" in result
        assert "https://jira.example.com" in result
        assert "Tags: engineering, agile" in result

    def test_context_with_linked_docs(self):
        """Linked docs are included with titles and truncated content."""
        system = _make_system()
        long_content = "A" * 600
        docs = [
            _make_doc(doc_id="d1", title="Setup Guide", content=long_content),
            _make_doc(doc_id="d2", title="FAQ", content="Short FAQ"),
        ]
        result = ToolFactory.build_system_context(system, linked_docs=docs)

        assert "### Reference Documents" in result
        assert "**Setup Guide**:" in result
        assert "**FAQ**: Short FAQ" in result
        # Long content should be truncated with ellipsis
        assert "..." in result
        # Content should be limited to 500 chars + "..."
        assert "A" * 500 in result
        assert "A" * 501 not in result

    def test_empty_system(self):
        """Minimal system (no tags, no docs) still produces output."""
        system = _make_system(description="", tags=[])
        result = ToolFactory.build_system_context(system, linked_docs=[])

        assert "## Jira" in result
        assert "Base URL: https://jira.example.com" in result
        # No tags section
        assert "Tags:" not in result
        # No docs section
        assert "Reference Documents" not in result

    def test_custom_max_doc_chars(self):
        """Custom max_doc_chars truncates at the specified length."""
        system = _make_system()
        docs = [_make_doc(content="B" * 100)]
        result = ToolFactory.build_system_context(system, linked_docs=docs, max_doc_chars=50)

        assert "B" * 50 in result
        assert "..." in result
        assert "B" * 51 not in result

    def test_doc_content_exactly_at_limit_no_ellipsis(self):
        """Content exactly at the limit does not get an ellipsis."""
        system = _make_system()
        docs = [_make_doc(content="C" * 500)]
        result = ToolFactory.build_system_context(system, linked_docs=docs, max_doc_chars=500)

        assert "C" * 500 in result
        assert "..." not in result
