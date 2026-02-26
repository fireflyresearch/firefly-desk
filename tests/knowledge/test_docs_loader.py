# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for DocsLoader -- dynamic markdown document loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from flydesk.knowledge.docs_loader import (
    DocsLoader,
    _content_hash,
    _parse_frontmatter,
    _stable_id,
    _title_from_filename,
)
from flydesk.knowledge.models import DocumentType


# ---------------------------------------------------------------------------
# Helper: write a markdown file inside a tmp_path
# ---------------------------------------------------------------------------

def _write_md(tmp_path: Path, relative: str, content: str) -> Path:
    """Write *content* to ``tmp_path / relative`` and return the full path."""
    fp = tmp_path / relative
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(content, encoding="utf-8")
    return fp


# ===========================================================================
# Unit tests for internal helpers
# ===========================================================================


class TestParseFrontmatter:
    def test_no_frontmatter(self):
        meta, body = _parse_frontmatter("# Hello\n\nSome content.")
        assert meta == {}
        assert body == "# Hello\n\nSome content."

    def test_basic_frontmatter(self):
        text = "---\ntitle: My Doc\ntype: manual\n---\n# Hello\nContent here."
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "My Doc"
        assert meta["type"] == "manual"
        assert body == "# Hello\nContent here."

    def test_frontmatter_with_list_tags(self):
        text = '---\ntags: [alpha, beta, gamma]\n---\nBody text.'
        meta, body = _parse_frontmatter(text)
        assert meta["tags"] == ["alpha", "beta", "gamma"]
        assert body == "Body text."

    def test_frontmatter_with_quoted_values(self):
        text = '---\ntitle: "Quoted Title"\nsource: \'single\'\n---\nBody.'
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "Quoted Title"
        assert meta["source"] == "single"

    def test_frontmatter_ignores_comments_and_blank_lines(self):
        text = "---\n# comment\n\ntitle: Foo\n---\nBody."
        meta, body = _parse_frontmatter(text)
        assert meta["title"] == "Foo"

    def test_partial_frontmatter_not_at_start(self):
        text = "Some preamble\n---\ntitle: Nope\n---\nBody."
        meta, body = _parse_frontmatter(text)
        # Not at the very start -- should not be parsed as frontmatter
        assert meta == {}
        assert body == text


class TestTitleFromFilename:
    def test_dashes(self):
        assert _title_from_filename("getting-started.md") == "Getting Started"

    def test_underscores(self):
        assert _title_from_filename("api_reference.md") == "Api Reference"

    def test_mixed(self):
        assert _title_from_filename("my-great_doc.md") == "My Great Doc"


class TestStableId:
    def test_deterministic(self):
        id1 = _stable_id("getting-started.md")
        id2 = _stable_id("getting-started.md")
        assert id1 == id2
        assert id1.startswith("doc-")
        assert len(id1) == 4 + 12  # "doc-" + 12 hex chars

    def test_different_paths_different_ids(self):
        assert _stable_id("a.md") != _stable_id("b.md")


class TestContentHash:
    def test_deterministic(self):
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_content(self):
        assert _content_hash("hello") != _content_hash("world")


# ===========================================================================
# Integration tests for DocsLoader.load_from_directory
# ===========================================================================


class TestLoadFromDirectory:
    def test_empty_directory(self, tmp_path: Path):
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs == []

    def test_nonexistent_directory(self, tmp_path: Path):
        docs = DocsLoader.load_from_directory(tmp_path / "nope")
        assert docs == []

    def test_single_file_with_heading(self, tmp_path: Path):
        _write_md(tmp_path, "overview.md", "# Platform Overview\n\nSome content here.")
        docs = DocsLoader.load_from_directory(tmp_path)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.title == "Platform Overview"
        assert doc.content == "# Platform Overview\n\nSome content here."
        assert doc.source == "docs://overview.md"
        assert doc.id == _stable_id("overview.md")
        assert doc.metadata["relative_path"] == "overview.md"
        assert "content_hash" in doc.metadata

    def test_single_file_with_frontmatter(self, tmp_path: Path):
        _write_md(
            tmp_path,
            "guide.md",
            "---\ntitle: Custom Title\ntags: [ops, guide]\ntype: tutorial\nsource: custom://guide\n---\n# Heading\nBody.",
        )
        docs = DocsLoader.load_from_directory(tmp_path)

        assert len(docs) == 1
        doc = docs[0]
        assert doc.title == "Custom Title"
        assert doc.tags == ["ops", "guide"]
        assert doc.document_type == DocumentType.TUTORIAL
        assert doc.source == "custom://guide"
        assert doc.content == "# Heading\nBody."

    def test_frontmatter_title_overrides_heading(self, tmp_path: Path):
        _write_md(
            tmp_path,
            "doc.md",
            "---\ntitle: Frontmatter Title\n---\n# Heading Title\nContent.",
        )
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].title == "Frontmatter Title"

    def test_filename_fallback_for_title(self, tmp_path: Path):
        _write_md(tmp_path, "my-fancy-doc.md", "No heading here, just text.")
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].title == "My Fancy Doc"

    def test_recursive_scanning(self, tmp_path: Path):
        _write_md(tmp_path, "top.md", "# Top")
        _write_md(tmp_path, "sub/nested.md", "# Nested")
        _write_md(tmp_path, "sub/deep/leaf.md", "# Leaf")

        docs = DocsLoader.load_from_directory(tmp_path)
        assert len(docs) == 3

        # Sorted by relative path
        titles = [d.title for d in docs]
        assert "Nested" in titles
        assert "Leaf" in titles
        assert "Top" in titles

    def test_non_md_files_ignored(self, tmp_path: Path):
        _write_md(tmp_path, "valid.md", "# Valid")
        (tmp_path / "readme.txt").write_text("not markdown")
        (tmp_path / "data.json").write_text("{}")

        docs = DocsLoader.load_from_directory(tmp_path)
        assert len(docs) == 1
        assert docs[0].title == "Valid"

    def test_stable_ids_across_loads(self, tmp_path: Path):
        _write_md(tmp_path, "alpha.md", "# Alpha")
        _write_md(tmp_path, "beta.md", "# Beta")

        docs1 = DocsLoader.load_from_directory(tmp_path)
        docs2 = DocsLoader.load_from_directory(tmp_path)

        ids1 = {d.id for d in docs1}
        ids2 = {d.id for d in docs2}
        assert ids1 == ids2

    def test_document_type_inferred_when_no_frontmatter(self, tmp_path: Path):
        _write_md(tmp_path, "plain.md", "# Plain Doc\nNo type frontmatter.")
        docs = DocsLoader.load_from_directory(tmp_path)
        # With no frontmatter type, inference kicks in; generic paths -> REFERENCE
        assert docs[0].document_type == DocumentType.REFERENCE

    def test_unknown_type_defaults_to_other(self, tmp_path: Path):
        _write_md(tmp_path, "unknown.md", "---\ntype: alien\n---\n# Alien")
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].document_type == DocumentType.OTHER

    def test_known_document_types(self, tmp_path: Path):
        for dtype in ("manual", "tutorial", "api_spec", "faq", "policy", "reference"):
            _write_md(
                tmp_path, f"{dtype}.md", f"---\ntype: {dtype}\n---\n# {dtype}"
            )
        docs = DocsLoader.load_from_directory(tmp_path)
        types = {d.document_type for d in docs}
        expected = {
            DocumentType.MANUAL,
            DocumentType.TUTORIAL,
            DocumentType.API_SPEC,
            DocumentType.FAQ,
            DocumentType.POLICY,
            DocumentType.REFERENCE,
        }
        assert types == expected

    def test_content_stripped(self, tmp_path: Path):
        _write_md(tmp_path, "padded.md", "---\ntitle: P\n---\n\n  Body  \n\n")
        docs = DocsLoader.load_from_directory(tmp_path)
        # Outer whitespace is stripped
        assert docs[0].content == "Body"

    def test_tags_as_comma_string(self, tmp_path: Path):
        _write_md(tmp_path, "csv-tags.md", "---\ntags: alpha, beta, gamma\n---\n# T")
        docs = DocsLoader.load_from_directory(tmp_path)
        assert docs[0].tags == ["alpha", "beta", "gamma"]


# ===========================================================================
# Tests for DocsLoader.detect_changes
# ===========================================================================


class TestDetectChanges:
    def test_all_new_when_no_existing(self, tmp_path: Path):
        _write_md(tmp_path, "a.md", "# A")
        _write_md(tmp_path, "b.md", "# B")

        new, updated, removed = DocsLoader.detect_changes(tmp_path, {})
        assert len(new) == 2
        assert len(updated) == 0
        assert len(removed) == 0

    def test_no_changes_when_hashes_match(self, tmp_path: Path):
        _write_md(tmp_path, "a.md", "# A")
        docs = DocsLoader.load_from_directory(tmp_path)
        existing = {d.id: d.metadata["content_hash"] for d in docs}

        new, updated, removed = DocsLoader.detect_changes(tmp_path, existing)
        assert len(new) == 0
        assert len(updated) == 0
        assert len(removed) == 0

    def test_updated_when_content_changes(self, tmp_path: Path):
        _write_md(tmp_path, "a.md", "# A\nOriginal content.")
        docs = DocsLoader.load_from_directory(tmp_path)
        existing = {d.id: d.metadata["content_hash"] for d in docs}

        # Modify the file
        _write_md(tmp_path, "a.md", "# A\nUpdated content!")

        new, updated, removed = DocsLoader.detect_changes(tmp_path, existing)
        assert len(new) == 0
        assert len(updated) == 1
        assert updated[0].content == "# A\nUpdated content!"
        assert len(removed) == 0

    def test_removed_when_file_deleted(self, tmp_path: Path):
        _write_md(tmp_path, "a.md", "# A")
        _write_md(tmp_path, "b.md", "# B")
        docs = DocsLoader.load_from_directory(tmp_path)
        existing = {d.id: d.metadata["content_hash"] for d in docs}

        # Remove one file
        (tmp_path / "b.md").unlink()

        new, updated, removed = DocsLoader.detect_changes(tmp_path, existing)
        assert len(new) == 0
        assert len(updated) == 0
        assert len(removed) == 1
        assert removed[0] == _stable_id("b.md")

    def test_mixed_changes(self, tmp_path: Path):
        _write_md(tmp_path, "keep.md", "# Keep")
        _write_md(tmp_path, "change.md", "# Change\nOld.")
        _write_md(tmp_path, "remove.md", "# Remove")
        docs = DocsLoader.load_from_directory(tmp_path)
        existing = {d.id: d.metadata["content_hash"] for d in docs}

        # Modify one, remove one, add one
        _write_md(tmp_path, "change.md", "# Change\nNew!")
        (tmp_path / "remove.md").unlink()
        _write_md(tmp_path, "brand-new.md", "# Brand New")

        new, updated, removed = DocsLoader.detect_changes(tmp_path, existing)
        assert len(new) == 1
        assert new[0].title == "Brand New"
        assert len(updated) == 1
        assert updated[0].title == "Change"
        assert len(removed) == 1

    def test_empty_dir_removes_all(self, tmp_path: Path):
        existing = {"doc-abc123456789": "somehash"}
        new, updated, removed = DocsLoader.detect_changes(tmp_path, existing)
        assert len(new) == 0
        assert len(updated) == 0
        assert removed == ["doc-abc123456789"]


# ===========================================================================
# Tests for platform_docs.py integration
# ===========================================================================


class TestPlatformDocsIntegration:
    def test_load_platform_docs_from_directory(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import load_platform_docs

        _write_md(tmp_path, "overview.md", "# Overview\nContent.")
        docs = load_platform_docs(tmp_path)
        assert len(docs) == 1
        assert docs[0].title == "Overview"

    def test_load_platform_docs_fallback(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import load_platform_docs

        # Point to a nonexistent directory
        docs = load_platform_docs(tmp_path / "missing")
        assert len(docs) > 0
        # Should be the fallback documents
        assert docs[0].id == "doc-platform-overview"

    def test_load_platform_docs_empty_dir_fallback(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import load_platform_docs

        # Empty directory (no .md files)
        docs = load_platform_docs(tmp_path)
        assert len(docs) > 0
        assert docs[0].id == "doc-platform-overview"

    async def test_seed_platform_docs(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import seed_platform_docs

        _write_md(tmp_path, "test.md", "# Test\nContent.")

        indexed: list = []

        class FakeIndexer:
            async def index_document(self, doc):
                indexed.append(doc)

        await seed_platform_docs(FakeIndexer(), docs_path=tmp_path)
        assert len(indexed) == 1
        assert indexed[0].title == "Test"

    async def test_seed_skips_existing(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import seed_platform_docs

        _write_md(tmp_path, "test.md", "# Test\nContent.")

        indexed: list = []
        doc_id = _stable_id("test.md")

        class FakeIndexer:
            async def index_document(self, doc):
                indexed.append(doc)

        class FakeCatalog:
            async def get_knowledge_document(self, did):
                if did == doc_id:
                    return {"id": did}
                return None

        await seed_platform_docs(FakeIndexer(), FakeCatalog(), docs_path=tmp_path)
        assert len(indexed) == 0

    async def test_unseed_platform_docs(self, tmp_path: Path):
        from flydesk.seeds.platform_docs import unseed_platform_docs

        _write_md(tmp_path, "test.md", "# Test\nContent.")

        deleted: list = []

        class FakeIndexer:
            async def delete_document(self, doc_id):
                deleted.append(doc_id)

        await unseed_platform_docs(FakeIndexer(), docs_path=tmp_path)
        assert len(deleted) == 1
