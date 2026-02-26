# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Load KnowledgeDocuments from a directory of Markdown files.

Supports YAML frontmatter for metadata (title, tags, type, source) and
falls back to extracting the title from the first ``# heading`` or from
the filename itself.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from flydesk.knowledge.models import DocumentStatus, DocumentType, KnowledgeDocument

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_HEADING_RE = re.compile(r"^#\s+(.+)", re.MULTILINE)


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Extract YAML frontmatter and return (metadata, remaining_content).

    If no frontmatter is found the full text is returned with an empty dict.
    Uses a lightweight parser to avoid a hard dependency on PyYAML.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text

    raw = match.group(1)
    remaining = text[match.end() :]

    meta: dict[str, object] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        # Handle YAML list values: [item1, item2] or - item style
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
            meta[key] = [v for v in items if v]
        elif not value:
            # Could be a block-style list -- collect subsequent ``- item`` lines
            # We don't handle that here to keep it simple; treat as empty string
            meta[key] = ""
        else:
            meta[key] = value.strip("\"'")

    return meta, remaining


def _title_from_filename(filename: str) -> str:
    """Derive a human-readable title from a filename stem."""
    stem = Path(filename).stem
    return stem.replace("-", " ").replace("_", " ").title()


def _stable_id(relative_path: str) -> str:
    """Generate a deterministic document ID from the relative path."""
    digest = hashlib.sha256(relative_path.encode()).hexdigest()[:12]
    return f"doc-{digest}"


def _content_hash(content: str) -> str:
    """Generate a hash of document content for change detection."""
    return hashlib.sha256(content.encode()).hexdigest()


def _resolve_document_type(raw: str | None) -> DocumentType:
    """Map a frontmatter type string to a DocumentType enum value."""
    if not raw:
        return DocumentType.OTHER
    raw_lower = raw.lower().strip()
    for member in DocumentType:
        if member.value == raw_lower:
            return member
    return DocumentType.OTHER


def _infer_document_type(relative_path: str) -> DocumentType:
    """Infer document type from the relative file path."""
    path_lower = relative_path.lower()
    if "help/" in path_lower or "tutorial" in path_lower:
        return DocumentType.TUTORIAL
    if "api" in path_lower:
        return DocumentType.API_SPEC
    if "faq" in path_lower:
        return DocumentType.FAQ
    if "policy" in path_lower or "security" in path_lower:
        return DocumentType.POLICY
    return DocumentType.REFERENCE


class DocsLoader:
    """Load Markdown files from a directory into KnowledgeDocument instances."""

    @staticmethod
    def load_from_directory(
        docs_path: str | Path,
        default_workspace_ids: list[str] | None = None,
        default_status: DocumentStatus | None = None,
    ) -> list[KnowledgeDocument]:
        """Scan *docs_path* recursively for ``*.md`` files and return documents.

        For each file the loader:
        1. Parses optional YAML frontmatter for *title*, *tags*, *type*, *source*.
        2. Falls back to the first ``# heading`` for the title.
        3. Uses the filename (dashes/underscores to spaces) as a last resort.
        4. Generates a stable ID from ``sha256(relative_path)[:12]``.
        5. Strips frontmatter from the stored content.

        Returns a list sorted by relative path for deterministic ordering.
        """
        docs_path = Path(docs_path)
        if not docs_path.is_dir():
            logger.warning("Docs path %s does not exist or is not a directory.", docs_path)
            return []

        documents: list[KnowledgeDocument] = []
        md_files = sorted(docs_path.rglob("*.md"))

        for filepath in md_files:
            try:
                raw_text = filepath.read_text(encoding="utf-8")
            except OSError:
                logger.warning("Could not read %s, skipping.", filepath)
                continue

            relative = filepath.relative_to(docs_path).as_posix()

            # Parse frontmatter
            frontmatter, content = _parse_frontmatter(raw_text)

            # Resolve title
            title = str(frontmatter.get("title", "")) or None
            if not title:
                heading_match = _HEADING_RE.search(content)
                if heading_match:
                    title = heading_match.group(1).strip()
            if not title:
                title = _title_from_filename(filepath.name)

            # Resolve tags
            raw_tags = frontmatter.get("tags", [])
            if isinstance(raw_tags, str):
                tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
            elif isinstance(raw_tags, list):
                tags = [str(t).strip() for t in raw_tags if str(t).strip()]
            else:
                tags = []

            # Resolve document type
            doc_type = _resolve_document_type(
                str(frontmatter["type"]) if "type" in frontmatter else None
            )

            if doc_type == DocumentType.OTHER and "type" not in frontmatter:
                doc_type = _infer_document_type(relative)

            # Resolve status
            status = default_status if default_status is not None else DocumentStatus.DRAFT

            # Resolve source
            source = str(frontmatter.get("source", "")) or f"docs://{relative}"

            # Stable ID and content hash
            doc_id = _stable_id(relative)
            c_hash = _content_hash(content)

            documents.append(
                KnowledgeDocument(
                    id=doc_id,
                    title=title,
                    content=content.strip(),
                    document_type=doc_type,
                    status=status,
                    source=source,
                    workspace_ids=list(default_workspace_ids) if default_workspace_ids else [],
                    tags=tags,
                    metadata={
                        "relative_path": relative,
                        "content_hash": c_hash,
                    },
                )
            )

        logger.info("Loaded %d document(s) from %s.", len(documents), docs_path)
        return documents

    @staticmethod
    def detect_changes(
        docs_path: str | Path,
        existing_docs: dict[str, str],
    ) -> tuple[list[KnowledgeDocument], list[KnowledgeDocument], list[str]]:
        """Compare on-disk documents against previously indexed ones.

        Parameters
        ----------
        docs_path:
            Directory to scan for markdown files.
        existing_docs:
            Mapping of ``{document_id: content_hash}`` for documents already
            in the knowledge base.

        Returns
        -------
        tuple
            ``(new_docs, updated_docs, removed_ids)`` where *new_docs* are
            documents with IDs not in *existing_docs*, *updated_docs* have a
            different content hash, and *removed_ids* are IDs present in
            *existing_docs* but no longer on disk.
        """
        current = DocsLoader.load_from_directory(docs_path)
        current_by_id = {doc.id: doc for doc in current}

        new_docs: list[KnowledgeDocument] = []
        updated_docs: list[KnowledgeDocument] = []

        for doc in current:
            if doc.id not in existing_docs:
                new_docs.append(doc)
            else:
                current_hash = doc.metadata.get("content_hash", "")
                if current_hash != existing_docs[doc.id]:
                    updated_docs.append(doc)

        removed_ids = [
            doc_id for doc_id in existing_docs if doc_id not in current_by_id
        ]

        return new_docs, updated_docs, removed_ids
