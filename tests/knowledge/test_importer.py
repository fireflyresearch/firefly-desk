# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for KnowledgeImporter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from flydek.knowledge.importer import KnowledgeImporter, _strip_extension
from flydek.knowledge.models import DocumentType, KnowledgeDocument


@pytest.fixture
def mock_indexer() -> AsyncMock:
    indexer = AsyncMock()
    indexer.index_document = AsyncMock(return_value=[])
    return indexer


@pytest.fixture
def mock_http_client() -> AsyncMock:
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def importer(mock_indexer: AsyncMock, mock_http_client: AsyncMock) -> KnowledgeImporter:
    return KnowledgeImporter(indexer=mock_indexer, http_client=mock_http_client)


def _make_response(
    content: str,
    content_type: str = "text/html; charset=utf-8",
    status_code: int = 200,
) -> httpx.Response:
    """Build a fake httpx.Response."""
    return httpx.Response(
        status_code=status_code,
        headers={"content-type": content_type},
        text=content,
        request=httpx.Request("GET", "https://example.com"),
    )


class TestImportUrl:
    async def test_fetches_and_converts_html(
        self, importer: KnowledgeImporter, mock_http_client: AsyncMock, mock_indexer: AsyncMock
    ):
        """import_url fetches URL and converts HTML to markdown."""
        html = "<html><head><title>Test Page</title></head><body><h1>Hello</h1><p>World</p></body></html>"
        mock_http_client.get = AsyncMock(return_value=_make_response(html))

        doc = await importer.import_url("https://example.com/page")

        mock_http_client.get.assert_called_once_with(
            "https://example.com/page", follow_redirects=True
        )
        assert "Hello" in doc.content
        assert "World" in doc.content
        assert doc.title == "Test Page"
        assert doc.source == "https://example.com/page"
        mock_indexer.index_document.assert_awaited_once()

    async def test_detects_api_spec_from_url(
        self, importer: KnowledgeImporter, mock_http_client: AsyncMock
    ):
        """import_url detects API_SPEC when URL contains /api/."""
        html = "<html><body><p>Some API docs</p></body></html>"
        mock_http_client.get = AsyncMock(return_value=_make_response(html))

        doc = await importer.import_url("https://example.com/api/v1/docs")

        assert doc.document_type == DocumentType.API_SPEC

    async def test_plain_text_url(
        self, importer: KnowledgeImporter, mock_http_client: AsyncMock
    ):
        """import_url handles plain text responses without HTML conversion."""
        mock_http_client.get = AsyncMock(
            return_value=_make_response("Plain text content", content_type="text/plain")
        )

        doc = await importer.import_url("https://example.com/file.txt")

        assert doc.content == "Plain text content"

    async def test_custom_title_and_tags(
        self, importer: KnowledgeImporter, mock_http_client: AsyncMock
    ):
        """import_url uses custom title and tags when provided."""
        html = "<html><body><p>Content</p></body></html>"
        mock_http_client.get = AsyncMock(return_value=_make_response(html))

        doc = await importer.import_url(
            "https://example.com/page",
            title="Custom Title",
            tags=["custom", "test"],
        )

        assert doc.title == "Custom Title"
        assert doc.tags == ["custom", "test"]

    async def test_explicit_doc_type_overrides_detection(
        self, importer: KnowledgeImporter, mock_http_client: AsyncMock
    ):
        """import_url uses explicit doc_type instead of heuristic detection."""
        html = "<html><body><p>openapi swagger content</p></body></html>"
        mock_http_client.get = AsyncMock(return_value=_make_response(html))

        doc = await importer.import_url(
            "https://example.com/page",
            doc_type=DocumentType.TUTORIAL,
        )

        # Even though content mentions openapi/swagger, explicit type wins
        assert doc.document_type == DocumentType.TUTORIAL


class TestImportFile:
    async def test_handles_markdown_file(
        self, importer: KnowledgeImporter, mock_indexer: AsyncMock
    ):
        """import_file processes markdown content correctly."""
        content = b"# Guide\n\nSome markdown content here."

        doc = await importer.import_file(
            filename="guide.md",
            content=content,
            content_type="text/markdown",
        )

        assert doc.content == "# Guide\n\nSome markdown content here."
        assert doc.title == "guide"
        assert doc.source == "guide.md"
        mock_indexer.index_document.assert_awaited_once()

    async def test_handles_plain_text(self, importer: KnowledgeImporter):
        """import_file processes plain text content."""
        content = b"Just plain text."

        doc = await importer.import_file(
            filename="notes.txt",
            content=content,
            content_type="text/plain",
        )

        assert doc.content == "Just plain text."

    async def test_custom_title_tags_type(self, importer: KnowledgeImporter):
        """import_file respects custom title, tags, and type overrides."""
        content = b"Some content about regulations and compliance."

        doc = await importer.import_file(
            filename="doc.txt",
            content=content,
            content_type="text/plain",
            title="My Custom Title",
            doc_type=DocumentType.FAQ,
            tags=["override"],
        )

        assert doc.title == "My Custom Title"
        assert doc.document_type == DocumentType.FAQ
        assert doc.tags == ["override"]

    async def test_html_file_converted(self, importer: KnowledgeImporter):
        """import_file converts HTML file content to markdown."""
        html_content = b"<h1>Title</h1><p>Body text</p>"

        doc = await importer.import_file(
            filename="page.html",
            content=html_content,
            content_type="text/html",
        )

        assert "Title" in doc.content
        assert "Body text" in doc.content
        # Should not contain raw HTML tags after conversion
        assert "<h1>" not in doc.content


class TestDetectDocumentType:
    def test_api_spec_from_openapi_keyword(self, importer: KnowledgeImporter):
        """Detects API_SPEC from openapi keyword in content."""
        assert (
            importer.detect_document_type('{"openapi": "3.0.0"}')
            == DocumentType.API_SPEC
        )

    def test_api_spec_from_swagger_keyword(self, importer: KnowledgeImporter):
        """Detects API_SPEC from swagger keyword in content."""
        assert (
            importer.detect_document_type("swagger: 2.0\ninfo: ...")
            == DocumentType.API_SPEC
        )

    def test_api_spec_from_url(self, importer: KnowledgeImporter):
        """Detects API_SPEC from /api/ in URL."""
        assert (
            importer.detect_document_type("Some docs", url="https://example.com/api/v1")
            == DocumentType.API_SPEC
        )

    def test_tutorial_detection(self, importer: KnowledgeImporter):
        """Detects TUTORIAL from step-by-step instructions."""
        content = (
            "# Getting Started\n"
            "Step 1: Install the package\n"
            "Step 2: Configure your settings\n"
            "Step 3: Run the application\n"
        )
        assert importer.detect_document_type(content) == DocumentType.TUTORIAL

    def test_policy_from_filename(self, importer: KnowledgeImporter):
        """Detects POLICY from policy keyword in filename."""
        assert (
            importer.detect_document_type("Some rules.", filename="security-policy.pdf")
            == DocumentType.POLICY
        )

    def test_policy_from_content(self, importer: KnowledgeImporter):
        """Detects POLICY from compliance keyword in content."""
        assert (
            importer.detect_document_type("This document outlines our compliance requirements.")
            == DocumentType.POLICY
        )

    def test_faq_detection(self, importer: KnowledgeImporter):
        """Detects FAQ from Q&A pairs."""
        content = (
            "# Frequently Asked Questions\n\n"
            "Q: What is this?\n"
            "A: A product.\n\n"
            "Q: How does it work?\n"
            "A: Magic.\n"
        )
        assert importer.detect_document_type(content) == DocumentType.FAQ

    def test_manual_from_markdown(self, importer: KnowledgeImporter):
        """Detects MANUAL from .md file with headers."""
        content = "# User Guide\n\nSome content here."
        assert (
            importer.detect_document_type(content, filename="guide.md")
            == DocumentType.MANUAL
        )

    def test_reference_from_markdown_many_headers(self, importer: KnowledgeImporter):
        """Detects REFERENCE from .md file with many sub-headers."""
        headers = "\n".join(f"## Section {i}\nContent." for i in range(6))
        content = f"# API Reference\n\n{headers}"
        assert (
            importer.detect_document_type(content, filename="reference.md")
            == DocumentType.REFERENCE
        )

    def test_default_other(self, importer: KnowledgeImporter):
        """Falls back to OTHER when no heuristic matches."""
        assert importer.detect_document_type("Random text.") == DocumentType.OTHER


class TestStripExtension:
    def test_simple_filename(self):
        assert _strip_extension("readme.md") == "readme"

    def test_path_with_separators(self):
        assert _strip_extension("path/to/my-doc.txt") == "my doc"

    def test_no_extension(self):
        assert _strip_extension("README") == "README"

    def test_underscores(self):
        assert _strip_extension("my_doc_name.pdf") == "my doc name"
