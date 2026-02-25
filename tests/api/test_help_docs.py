# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Help Docs API (read-only markdown file serving)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_md(directory: Path, filename: str, content: str) -> Path:
    """Write a markdown file into *directory* and return its path."""
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def help_dir(tmp_path: Path) -> Path:
    """Return a temporary docs/help directory populated with sample docs."""
    d = tmp_path / "docs" / "help"
    d.mkdir(parents=True)
    _write_md(
        d,
        "getting-started.md",
        "# Getting Started\n\nLearn how to set up Firefly Desk.\n\n## Installation\n\nRun the installer.",
    )
    _write_md(
        d,
        "knowledge-base.md",
        "# Knowledge Base\n\nHow to manage your knowledge base.\n\n## Adding Documents\n\nUpload or import.",
    )
    return d


@pytest.fixture
def empty_help_dir(tmp_path: Path) -> Path:
    """Return an empty temporary docs/help directory."""
    d = tmp_path / "docs" / "help"
    d.mkdir(parents=True)
    return d


@pytest.fixture
async def client(help_dir: Path):
    """Async test client with DOCS_DIR patched to *help_dir*."""
    with patch("flydesk.api.help_docs.DOCS_DIR", help_dir):
        from flydesk.api.help_docs import router

        # Build a minimal FastAPI just for the help docs router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def empty_client(empty_help_dir: Path):
    """Async test client with an empty docs directory."""
    with patch("flydesk.api.help_docs.DOCS_DIR", empty_help_dir):
        from flydesk.api.help_docs import router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def missing_client(tmp_path: Path):
    """Async test client where the docs directory does not exist."""
    nonexistent = tmp_path / "no" / "such" / "dir"
    with patch("flydesk.api.help_docs.DOCS_DIR", nonexistent):
        from flydesk.api.help_docs import router

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# Tests — list endpoint
# ---------------------------------------------------------------------------


class TestListHelpDocs:
    """GET /api/help/docs — list available help documents."""

    async def test_list_returns_all_docs(self, client: AsyncClient):
        response = await client.get("/api/help/docs")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        slugs = {d["slug"] for d in data}
        assert slugs == {"getting-started", "knowledge-base"}

    async def test_list_includes_title_and_description(self, client: AsyncClient):
        response = await client.get("/api/help/docs")
        data = response.json()

        by_slug = {d["slug"]: d for d in data}
        gs = by_slug["getting-started"]
        assert gs["title"] == "Getting Started"
        assert "set up Firefly Desk" in gs["description"]

    async def test_list_empty_directory(self, empty_client: AsyncClient):
        response = await empty_client.get("/api/help/docs")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_missing_directory(self, missing_client: AsyncClient):
        response = await missing_client.get("/api/help/docs")
        assert response.status_code == 200
        assert response.json() == []


# ---------------------------------------------------------------------------
# Tests — get endpoint
# ---------------------------------------------------------------------------


class TestGetHelpDoc:
    """GET /api/help/docs/{slug} — get a single help document."""

    async def test_get_existing_doc(self, client: AsyncClient):
        response = await client.get("/api/help/docs/getting-started")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "getting-started"
        assert data["title"] == "Getting Started"
        assert "## Installation" in data["content"]

    async def test_get_returns_full_content(self, client: AsyncClient):
        response = await client.get("/api/help/docs/knowledge-base")
        data = response.json()
        assert data["content"].startswith("# Knowledge Base")
        assert "Adding Documents" in data["content"]

    async def test_get_not_found(self, client: AsyncClient):
        response = await client.get("/api/help/docs/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_get_missing_directory_returns_404(self, missing_client: AsyncClient):
        response = await missing_client.get("/api/help/docs/anything")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests — title extraction
# ---------------------------------------------------------------------------


class TestTitleExtraction:
    """Verify title parsing from markdown headings."""

    def test_title_from_heading(self):
        from flydesk.api.help_docs import _extract_title

        assert _extract_title("# Hello World\n\nSome text.") == "Hello World"

    def test_title_strips_whitespace(self):
        from flydesk.api.help_docs import _extract_title

        assert _extract_title("#   Padded Title  \n\nBody.") == "Padded Title"

    def test_title_untitled_when_no_heading(self):
        from flydesk.api.help_docs import _extract_title

        assert _extract_title("Just a paragraph.\n\nNo heading.") == "Untitled"

    def test_title_picks_first_heading(self):
        from flydesk.api.help_docs import _extract_title

        md = "# First\n\n## Second\n\n# Third"
        assert _extract_title(md) == "First"


# ---------------------------------------------------------------------------
# Tests — description extraction
# ---------------------------------------------------------------------------


class TestDescriptionExtraction:
    """Verify description parsing from first paragraph after heading."""

    def test_description_from_first_paragraph(self):
        from flydesk.api.help_docs import _extract_description

        md = "# Title\n\nThis is the description.\n\nAnother paragraph."
        assert _extract_description(md) == "This is the description."

    def test_description_empty_when_no_heading(self):
        from flydesk.api.help_docs import _extract_description

        assert _extract_description("No heading here.") == ""

    def test_description_empty_when_nothing_after_heading(self):
        from flydesk.api.help_docs import _extract_description

        assert _extract_description("# Just a Heading") == ""

    def test_description_skips_sub_heading(self):
        from flydesk.api.help_docs import _extract_description

        md = "# Title\n\n## Sub-Heading\n\nActual paragraph."
        assert _extract_description(md) == ""

    def test_description_skips_code_block(self):
        from flydesk.api.help_docs import _extract_description

        md = "# Title\n\n```python\ncode()\n```\n\nParagraph."
        assert _extract_description(md) == ""
