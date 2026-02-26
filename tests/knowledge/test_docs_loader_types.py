# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for DocsLoader type inference and status defaults."""

from __future__ import annotations

import pytest

from flydesk.knowledge.docs_loader import DocsLoader, _infer_document_type
from flydesk.knowledge.models import DocumentStatus, DocumentType


class TestInferDocumentType:
    def test_help_path_returns_tutorial(self):
        assert _infer_document_type("help/getting-started.md") == DocumentType.TUTORIAL

    def test_api_path_returns_api_spec(self):
        assert _infer_document_type("api-reference.md") == DocumentType.API_SPEC

    def test_faq_path_returns_faq(self):
        assert _infer_document_type("faq.md") == DocumentType.FAQ

    def test_security_path_returns_policy(self):
        assert _infer_document_type("security.md") == DocumentType.POLICY

    def test_generic_path_returns_reference(self):
        assert _infer_document_type("architecture.md") == DocumentType.REFERENCE

    def test_tutorial_keyword_returns_tutorial(self):
        assert _infer_document_type("tutorial-basics.md") == DocumentType.TUTORIAL


class TestDocsLoaderDefaultStatus:
    def test_loads_with_published_status(self, tmp_path):
        (tmp_path / "test.md").write_text("# Test\nContent here.")
        docs = DocsLoader.load_from_directory(tmp_path, default_status=DocumentStatus.PUBLISHED)
        assert len(docs) == 1
        assert docs[0].status == DocumentStatus.PUBLISHED

    def test_loads_with_draft_status_by_default(self, tmp_path):
        (tmp_path / "test.md").write_text("# Test\nContent here.")
        docs = DocsLoader.load_from_directory(tmp_path)
        assert len(docs) == 1
        assert docs[0].status == DocumentStatus.DRAFT

    def test_frontmatter_type_overrides_inference(self, tmp_path):
        content = "---\ntype: faq\n---\n# Architecture\nContent."
        (tmp_path / "architecture.md").write_text(content)
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].document_type == DocumentType.FAQ

    def test_inference_used_when_no_frontmatter_type(self, tmp_path):
        (tmp_path / "help").mkdir()
        (tmp_path / "help" / "getting-started.md").write_text("# Getting Started\nWelcome.")
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].document_type == DocumentType.TUTORIAL
