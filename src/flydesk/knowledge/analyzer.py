# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""LLM-powered document analysis for import enrichment.

``DocumentAnalyzer`` uses ``DeskAgentFactory`` (fireflyframework-genai) to
classify, summarise, tag, and extract entities from imported documents.  When
no LLM provider is configured it falls back to simple heuristic analysis based
on filename patterns and content keywords.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from flydesk.domain.common import DocumentType

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of analysing a single document."""

    document_type: DocumentType = DocumentType.OTHER
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    section_boundaries: list[int] = field(default_factory=list)
    suggested_title: str = ""
    is_openapi: bool = False


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

ANALYSIS_SYSTEM_PROMPT = """\
You are a document analysis assistant.  Given a document's content and its \
filename, return a JSON object with the following fields:

- "document_type": one of "api_spec", "tutorial", "reference", "faq", \
"policy", "manual", "changelog", "readme", "other"
- "summary": a concise 1-3 sentence summary of the document
- "tags": a list of lowercase keyword tags (max 10)
- "entities": a list of notable entity names mentioned (people, systems, \
APIs, products -- max 15)
- "section_boundaries": a list of character offsets where major sections begin \
(empty list if unsure)
- "suggested_title": a short human-readable title for the document
- "is_openapi": true if the document is an OpenAPI / Swagger specification, \
otherwise false

Return ONLY the JSON object.  Do not include any explanation or markdown \
formatting.
"""

# ---------------------------------------------------------------------------
# Heuristic helpers
# ---------------------------------------------------------------------------

_OPENAPI_FILENAME_RE = re.compile(
    r"(openapi|swagger|api-spec|apispec)", re.IGNORECASE
)
_OPENAPI_CONTENT_MARKERS = ("openapi:", '"openapi":', "swagger:", '"swagger":')

_README_RE = re.compile(r"readme", re.IGNORECASE)
_CHANGELOG_RE = re.compile(r"changelog|changes|release.?notes", re.IGNORECASE)
_FAQ_RE = re.compile(r"faq|frequently.asked", re.IGNORECASE)
_POLICY_RE = re.compile(r"policy|policies|compliance|security.?policy", re.IGNORECASE)
_TUTORIAL_RE = re.compile(r"tutorial|guide|getting.?started|how.?to|quickstart", re.IGNORECASE)
_MANUAL_RE = re.compile(r"manual|handbook|playbook", re.IGNORECASE)

# Content-level keyword lists used when filename gives no strong signal.
_CONTENT_TYPE_KEYWORDS: list[tuple[re.Pattern[str], DocumentType]] = [
    (re.compile(r"endpoint|request|response|status.?code|curl", re.IGNORECASE), DocumentType.API_SPEC),
    (re.compile(r"step\s+\d|tutorial|walk.?through", re.IGNORECASE), DocumentType.TUTORIAL),
    (re.compile(r"frequently.asked|q\s*[:&]\s*a", re.IGNORECASE), DocumentType.FAQ),
    (re.compile(r"policy|compliance|must not|prohibited", re.IGNORECASE), DocumentType.POLICY),
]

# Maximum content length sent to the LLM to stay within token limits.
_MAX_CONTENT_LENGTH = 8000


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class DocumentAnalyzer:
    """Analyse documents using an LLM with heuristic fallback.

    Uses ``DeskAgentFactory`` to create a temporary ``FireflyAgent`` for each
    analysis call.  If no LLM provider is configured (factory returns ``None``)
    or the LLM call fails, the analyser falls back to ``_heuristic_analysis``.
    """

    def __init__(self, agent_factory: DeskAgentFactory) -> None:
        self._agent_factory = agent_factory

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def analyze(self, content: str, filename: str = "") -> AnalysisResult:
        """Analyse a single document.

        Attempts LLM-based analysis first; falls back to heuristics on error
        or when no LLM is configured.
        """
        try:
            agent = await self._agent_factory.create_agent(ANALYSIS_SYSTEM_PROMPT)
        except Exception:
            logger.debug("Failed to create analysis agent.", exc_info=True)
            agent = None

        if agent is None:
            logger.debug("No LLM provider configured; using heuristic analysis.")
            return self._heuristic_analysis(content, filename)

        truncated = content[:_MAX_CONTENT_LENGTH]
        user_prompt = f"Filename: {filename}\n\n{truncated}"

        try:
            result = await agent.run(user_prompt)
            output_text = str(result.output)
        except Exception:
            logger.exception("LLM call failed during document analysis.")
            return self._heuristic_analysis(content, filename)

        parsed = self._parse_llm_response(output_text)
        if parsed is not None:
            return parsed

        logger.warning("Could not parse LLM analysis response; falling back to heuristic.")
        return self._heuristic_analysis(content, filename)

    async def analyze_batch(
        self,
        files: list[tuple[str, str]],
        on_progress: Callable[[int, int], Coroutine[Any, Any, None]] | Callable[[int, int], None] | None = None,
    ) -> list[AnalysisResult]:
        """Analyse multiple files sequentially with optional progress callback.

        Parameters
        ----------
        files:
            A list of ``(content, filename)`` pairs.
        on_progress:
            Optional callback invoked as ``on_progress(completed, total)``.
            May be sync or async.
        """
        total = len(files)
        results: list[AnalysisResult] = []
        for idx, (content, filename) in enumerate(files):
            result = await self.analyze(content, filename)
            results.append(result)
            if on_progress is not None:
                maybe_coro = on_progress(idx + 1, total)
                # Support both sync and async callbacks.
                if maybe_coro is not None:
                    try:
                        await maybe_coro  # type: ignore[arg-type]
                    except TypeError:
                        pass  # sync callback, nothing to await
        return results

    # ------------------------------------------------------------------
    # LLM response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_llm_response(response: str) -> AnalysisResult | None:
        """Parse an LLM JSON response into an ``AnalysisResult``.

        Strips markdown code fences if present.  Returns ``None`` if the
        response cannot be parsed or validated.
        """
        cleaned = response.strip()

        # Strip markdown code blocks if present.
        if cleaned.startswith("```"):
            first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
            cleaned = cleaned[first_newline + 1:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        try:
            data: dict[str, Any] = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning(
                "Failed to parse document analysis response as JSON: %s...",
                cleaned[:200],
            )
            return None

        # Validate and coerce document_type.
        raw_type = data.get("document_type", "other")
        try:
            doc_type = DocumentType(raw_type)
        except ValueError:
            doc_type = DocumentType.OTHER

        return AnalysisResult(
            document_type=doc_type,
            summary=data.get("summary", ""),
            tags=data.get("tags", []),
            entities=data.get("entities", []),
            section_boundaries=data.get("section_boundaries", []),
            suggested_title=data.get("suggested_title", ""),
            is_openapi=bool(data.get("is_openapi", False)),
        )

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    @staticmethod
    def _heuristic_analysis(content: str, filename: str = "") -> AnalysisResult:
        """Simple rule-based analysis using filename patterns and content keywords."""
        fname_lower = filename.lower()
        content_lower = content[:4000].lower()

        # Detect OpenAPI specs.
        is_openapi = bool(_OPENAPI_FILENAME_RE.search(fname_lower)) or any(
            marker in content_lower for marker in _OPENAPI_CONTENT_MARKERS
        )

        # Determine document type from filename first, then content.
        doc_type = DocumentType.OTHER
        if is_openapi:
            doc_type = DocumentType.API_SPEC
        elif _README_RE.search(fname_lower):
            doc_type = DocumentType.README
        elif _CHANGELOG_RE.search(fname_lower):
            doc_type = DocumentType.CHANGELOG
        elif _FAQ_RE.search(fname_lower):
            doc_type = DocumentType.FAQ
        elif _POLICY_RE.search(fname_lower):
            doc_type = DocumentType.POLICY
        elif _TUTORIAL_RE.search(fname_lower):
            doc_type = DocumentType.TUTORIAL
        elif _MANUAL_RE.search(fname_lower):
            doc_type = DocumentType.MANUAL
        else:
            # Fall back to content keyword scanning.
            for pattern, dtype in _CONTENT_TYPE_KEYWORDS:
                if pattern.search(content_lower):
                    doc_type = dtype
                    break

        # Build a simple summary from the first non-blank line(s).
        lines = [ln.strip() for ln in content.split("\n") if ln.strip()]
        summary = lines[0][:200] if lines else ""

        # Derive suggested title from filename.
        suggested_title = filename
        if suggested_title:
            # Strip common extensions.
            for ext in (".md", ".txt", ".yaml", ".yml", ".json", ".rst", ".html"):
                if suggested_title.lower().endswith(ext):
                    suggested_title = suggested_title[: -len(ext)]
                    break
            suggested_title = suggested_title.replace("-", " ").replace("_", " ").strip()
            suggested_title = suggested_title.title() if suggested_title else filename

        # Extract simple tags from headings.
        heading_tags: list[str] = []
        for line in lines[:30]:
            if line.startswith("#"):
                tag = line.lstrip("#").strip().lower()
                if tag and len(tag) < 40:
                    heading_tags.append(tag)
        tags = heading_tags[:10]

        return AnalysisResult(
            document_type=doc_type,
            summary=summary,
            tags=tags,
            entities=[],
            section_boundaries=[],
            suggested_title=suggested_title,
            is_openapi=is_openapi,
        )
