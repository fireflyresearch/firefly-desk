# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for structural Markdown chunking in KnowledgeIndexer."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.models.base import Base


class _FakeEmbeddingProvider:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3, 0.4] for _ in texts]


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def indexer(session_factory) -> KnowledgeIndexer:
    return KnowledgeIndexer(
        session_factory=session_factory,
        embedding_provider=_FakeEmbeddingProvider(),
        chunk_size=50,
        chunk_overlap=10,
    )


# ---------------------------------------------------------------------------
# _split_by_headings
# ---------------------------------------------------------------------------


class TestSplitByHeadings:
    def test_splits_on_h1_and_h2(self, indexer):
        """H1 and H2 headings produce separate sections."""
        text = "# Introduction\nHello world\n## Details\nSome details here"
        sections = KnowledgeIndexer._split_by_headings(text)

        assert len(sections) == 2
        assert sections[0]["heading_path"] == "# Introduction"
        assert "Hello world" in sections[0]["content"]
        assert sections[1]["heading_path"] == "## Details"
        assert "Some details here" in sections[1]["content"]

    def test_no_headings_returns_single_section(self, indexer):
        """Plain text without headings yields one section with empty heading_path."""
        text = "Just some plain text without any headings."
        sections = KnowledgeIndexer._split_by_headings(text)

        assert len(sections) == 1
        assert sections[0]["heading_path"] == ""
        assert "plain text" in sections[0]["content"]

    def test_h3_does_not_split(self, indexer):
        """H3 headings are NOT treated as split points."""
        text = "# Top\nIntro\n### Subsection\nMore text"
        sections = KnowledgeIndexer._split_by_headings(text)

        # Only one H1 section; the ### stays in the content
        assert len(sections) == 1
        assert sections[0]["heading_path"] == "# Top"
        assert "### Subsection" in sections[0]["content"]
        assert "More text" in sections[0]["content"]

    def test_content_before_first_heading_preserved(self, indexer):
        """Text before the first heading gets its own section."""
        text = "Preamble text\n# First Heading\nBody"
        sections = KnowledgeIndexer._split_by_headings(text)

        assert len(sections) == 2
        assert sections[0]["heading_path"] == ""
        assert "Preamble text" in sections[0]["content"]
        assert sections[1]["heading_path"] == "# First Heading"
        assert "Body" in sections[1]["content"]


# ---------------------------------------------------------------------------
# _chunk_text_structural / chunk_document
# ---------------------------------------------------------------------------


class TestStructuralChunking:
    def test_creates_chunk_per_section(self, indexer):
        """Each Markdown section becomes a separate chunk."""
        text = "# Section A\nShort content.\n## Section B\nAlso short."
        chunks = indexer.chunk_document("doc-1", text, mode="structural")

        assert len(chunks) == 2
        assert "Section A" in chunks[0].content
        assert "Section B" in chunks[1].content

        # Verify section_path metadata
        assert chunks[0].metadata["section_path"] == "# Section A"
        assert chunks[1].metadata["section_path"] == "## Section B"

    def test_falls_back_for_unstructured_text(self, indexer):
        """Without headings, structural mode falls back to fixed chunking."""
        text = "A" * 200  # No headings, longer than chunk_size
        chunks = indexer.chunk_document("doc-2", text, mode="structural")

        # Should produce multiple fixed-size chunks (chunk_size=50, overlap=10)
        assert len(chunks) > 1
        # Fixed chunks have empty metadata by default
        assert chunks[0].metadata == {}

    def test_large_sections_get_sub_chunked(self, indexer):
        """Sections larger than chunk_size * 2 are sub-chunked."""
        # chunk_size=50, so threshold = 100
        large_body = "X" * 150
        text = f"# Intro\nSmall.\n## Big Section\n{large_body}"
        chunks = indexer.chunk_document("doc-3", text, mode="structural")

        # The first section ("# Intro\nSmall.") is short -> 1 chunk
        # The second section header + 150 chars > 100 -> sub-chunked
        big_chunks = [c for c in chunks if c.metadata.get("section_path") == "## Big Section"]
        assert len(big_chunks) > 1, "Large section should be sub-chunked"

        # All sub-chunks should carry the section_path metadata
        for c in big_chunks:
            assert c.metadata["section_path"] == "## Big Section"


# ---------------------------------------------------------------------------
# Auto-detection mode
# ---------------------------------------------------------------------------


class TestAutoDetectionMode:
    def test_auto_detects_markdown_headings(self):
        """Auto mode uses structural chunking when Markdown headings are found."""
        indexer = KnowledgeIndexer(
            session_factory=None,
            embedding_provider=_FakeEmbeddingProvider(),
            chunk_size=500,
            chunk_overlap=50,
            chunking_mode="auto",
        )
        md_text = "# Heading 1\nContent under heading 1.\n## Heading 2\nContent under heading 2."
        chunks = indexer.chunk_document("doc-auto-md", md_text)

        assert len(chunks) == 2
        assert chunks[0].metadata.get("section_path") == "# Heading 1"
        assert chunks[1].metadata.get("section_path") == "## Heading 2"

    def test_auto_falls_back_to_fixed_for_plain_text(self):
        """Auto mode uses fixed chunking when no headings are found."""
        indexer = KnowledgeIndexer(
            session_factory=None,
            embedding_provider=_FakeEmbeddingProvider(),
            chunk_size=50,
            chunk_overlap=10,
            chunking_mode="auto",
        )
        plain_text = "A" * 200
        chunks = indexer.chunk_document("doc-auto-plain", plain_text)

        assert len(chunks) > 1
        # Fixed chunks don't have section_path metadata
        assert chunks[0].metadata == {}

    def test_auto_ignores_h3_headings(self):
        """Auto mode only detects H1/H2 headings, not H3+."""
        indexer = KnowledgeIndexer(
            session_factory=None,
            embedding_provider=_FakeEmbeddingProvider(),
            chunk_size=50,
            chunk_overlap=10,
            chunking_mode="auto",
        )
        text = "### Only H3\nSome content here that is long enough." + "X" * 100
        chunks = indexer.chunk_document("doc-auto-h3", text)

        # H3 not detected -> falls back to fixed chunking -> no section_path
        assert all(c.metadata == {} for c in chunks)

    def test_constructor_default_is_auto(self):
        """Default chunking_mode in constructor is 'auto'."""
        indexer = KnowledgeIndexer(
            session_factory=None,
            embedding_provider=_FakeEmbeddingProvider(),
        )
        assert indexer._chunking_mode == "auto"

    def test_constructor_accepts_chunking_mode(self):
        """Constructor properly stores a custom chunking_mode."""
        indexer = KnowledgeIndexer(
            session_factory=None,
            embedding_provider=_FakeEmbeddingProvider(),
            chunking_mode="structural",
        )
        assert indexer._chunking_mode == "structural"


class TestFixedModeUnchanged:
    def test_fixed_mode_produces_overlapping_chunks(self, indexer):
        """Fixed mode via chunk_document behaves identically to _chunk_text."""
        text = "B" * 100
        chunks_direct = indexer._chunk_text("doc-f", text)
        chunks_via_api = indexer.chunk_document("doc-f2", text, mode="fixed")

        assert len(chunks_direct) == len(chunks_via_api)
        for a, b in zip(chunks_direct, chunks_via_api):
            assert a.content == b.content
            assert a.chunk_index == b.chunk_index

    def test_explicit_fixed_mode_matches_chunk_text(self, indexer):
        """When fixed mode is explicitly supplied, it matches _chunk_text."""
        text = "C" * 100
        chunks_explicit = indexer.chunk_document("doc-d1", text, mode="fixed")
        chunks_direct = indexer._chunk_text("doc-d2", text)
        assert len(chunks_explicit) == len(chunks_direct)


class TestChunkIndicesSequential:
    def test_structural_chunk_indices_are_sequential(self, indexer):
        """All chunks produced by structural mode have sequential indices."""
        large_body = "Y" * 150
        text = f"# A\nShort.\n## B\n{large_body}\n## C\nAlso short."
        chunks = indexer.chunk_document("doc-seq", text, mode="structural")

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks))), (
            f"Indices should be 0..{len(chunks)-1}, got {indices}"
        )

    def test_fixed_chunk_indices_are_sequential(self, indexer):
        """Fixed-mode chunks also have sequential indices."""
        text = "Z" * 200
        chunks = indexer.chunk_document("doc-seq-fixed", text, mode="fixed")

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks)))
