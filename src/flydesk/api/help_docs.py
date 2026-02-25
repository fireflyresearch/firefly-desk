# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Help documentation API — serves markdown files from docs/help/."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Default docs directory: project-root / docs / help
# From src/flydesk/api/help_docs.py → parents[3] reaches the project root.
DOCS_DIR: Path = Path(__file__).resolve().parents[3] / "docs" / "help"

router = APIRouter(prefix="/api/help", tags=["help"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class HelpDocSummary(BaseModel):
    """Summary of a help document (used in list responses)."""

    slug: str
    title: str
    description: str


class HelpDoc(BaseModel):
    """Full help document including markdown content."""

    slug: str
    title: str
    description: str
    content: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


def _extract_title(text: str) -> str:
    """Extract the first ``# heading`` from *text*, or return ``'Untitled'``."""
    match = _HEADING_RE.search(text)
    return match.group(1).strip() if match else "Untitled"


def _extract_description(text: str) -> str:
    """Return the first non-empty paragraph after the first ``# heading``.

    If no heading or no paragraph is found, return an empty string.
    """
    match = _HEADING_RE.search(text)
    if not match:
        return ""

    # Everything after the heading line
    after_heading = text[match.end():]
    # Split into blocks separated by blank lines
    paragraphs = re.split(r"\n\s*\n", after_heading.strip(), maxsplit=1)
    if paragraphs:
        first = paragraphs[0].strip()
        # Skip if the "paragraph" is actually another heading or a code block
        if first and not first.startswith("#") and not first.startswith("```"):
            return first
    return ""


def _parse_doc(slug: str, text: str) -> dict[str, str]:
    """Return a dict with slug, title, description, and content."""
    return {
        "slug": slug,
        "title": _extract_title(text),
        "description": _extract_description(text),
        "content": text,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/docs")
async def list_help_docs() -> list[HelpDocSummary]:
    """List all available help documents with slug, title, and description."""
    docs_dir = DOCS_DIR
    if not docs_dir.is_dir():
        return []

    results: list[HelpDocSummary] = []
    for path in sorted(docs_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        slug = path.stem
        info = _parse_doc(slug, text)
        results.append(HelpDocSummary(slug=info["slug"], title=info["title"], description=info["description"]))

    return results


@router.get("/docs/{slug}")
async def get_help_doc(slug: str) -> HelpDoc:
    """Return the full markdown content of a help document by slug."""
    docs_dir = DOCS_DIR
    file_path = docs_dir / f"{slug}.md"

    if not docs_dir.is_dir() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Help document '{slug}' not found.")

    text = file_path.read_text(encoding="utf-8")
    info = _parse_doc(slug, text)
    return HelpDoc(**info)
