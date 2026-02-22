# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Import knowledge documents from URLs and files."""

from __future__ import annotations

import re
import uuid

import html2text
import httpx

from flydek.knowledge.indexer import KnowledgeIndexer
from flydek.knowledge.models import DocumentType, KnowledgeDocument


class KnowledgeImporter:
    """Fetch and process documents from URLs or file uploads, then index them."""

    def __init__(self, indexer: KnowledgeIndexer, http_client: httpx.AsyncClient) -> None:
        self._indexer = indexer
        self._http_client = http_client
        self._html_converter = html2text.HTML2Text()
        self._html_converter.ignore_links = False
        self._html_converter.ignore_images = True
        self._html_converter.body_width = 0  # No line wrapping

    async def import_url(
        self,
        url: str,
        title: str | None = None,
        doc_type: DocumentType | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeDocument:
        """Fetch URL, convert HTML to markdown, detect type, index."""
        response = await self._http_client.get(url, follow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        raw = response.text

        # Convert HTML content to markdown
        if "html" in content_type:
            content = self._html_converter.handle(raw)
        else:
            content = raw

        if doc_type is None:
            doc_type = self.detect_document_type(content, url=url)

        if title is None:
            # Try to extract title from HTML <title> tag
            title_match = re.search(r"<title[^>]*>([^<]+)</title>", raw, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else url

        document = KnowledgeDocument(
            id=str(uuid.uuid4()),
            title=title,
            content=content.strip(),
            document_type=doc_type,
            source=url,
            tags=tags or [],
            metadata={"import_source": "url", "original_url": url},
        )

        await self._indexer.index_document(document)
        return document

    async def import_file(
        self,
        filename: str,
        content: bytes,
        content_type: str,
        title: str | None = None,
        doc_type: DocumentType | None = None,
        tags: list[str] | None = None,
    ) -> KnowledgeDocument:
        """Process uploaded file content, detect type, index."""
        # Decode content based on content type
        if "html" in content_type:
            text = self._html_converter.handle(content.decode("utf-8"))
        else:
            text = content.decode("utf-8")

        if doc_type is None:
            doc_type = self.detect_document_type(text, filename=filename)

        if title is None:
            # Use filename without extension as title
            title = _strip_extension(filename)

        document = KnowledgeDocument(
            id=str(uuid.uuid4()),
            title=title,
            content=text.strip(),
            document_type=doc_type,
            source=filename,
            tags=tags or [],
            metadata={"import_source": "file", "filename": filename, "content_type": content_type},
        )

        await self._indexer.index_document(document)
        return document

    def detect_document_type(
        self, content: str, filename: str = "", url: str = ""
    ) -> DocumentType:
        """Heuristic type detection from content and metadata."""
        lower_content = content.lower()
        lower_filename = filename.lower()
        lower_url = url.lower()

        # API spec detection
        if "/api/" in lower_url or "openapi" in lower_content or "swagger" in lower_content:
            return DocumentType.API_SPEC

        # Tutorial detection -- step-by-step instructions
        step_pattern = re.compile(
            r"(step\s+\d|^\s*\d+\.\s+.{10,})", re.IGNORECASE | re.MULTILINE
        )
        step_matches = step_pattern.findall(lower_content)
        if len(step_matches) >= 3:
            return DocumentType.TUTORIAL

        # Policy detection
        policy_keywords = ("policy", "compliance", "regulation")
        if any(kw in lower_filename for kw in policy_keywords) or any(
            kw in lower_content for kw in policy_keywords
        ):
            return DocumentType.POLICY

        # FAQ detection -- Q&A pairs
        qa_pattern = re.compile(
            r"(^\s*Q[:.]|^\s*\*\*Q[:.]|^#{1,3}\s+.*\?$)", re.IGNORECASE | re.MULTILINE
        )
        qa_matches = qa_pattern.findall(content)
        if len(qa_matches) >= 2:
            return DocumentType.FAQ

        # Manual/Reference detection -- markdown with headers
        if lower_filename.endswith(".md") and re.search(r"^#\s+", content, re.MULTILINE):
            # If it has many sub-headers, likely a reference
            header_count = len(re.findall(r"^#{2,}\s+", content, re.MULTILINE))
            if header_count >= 5:
                return DocumentType.REFERENCE
            return DocumentType.MANUAL

        return DocumentType.OTHER


def _strip_extension(filename: str) -> str:
    """Remove file extension and clean up the filename for use as a title."""
    # Remove path components
    name = filename.rsplit("/", 1)[-1]
    name = name.rsplit("\\", 1)[-1]
    # Remove extension
    if "." in name:
        name = name.rsplit(".", 1)[0]
    # Replace separators with spaces
    return name.replace("-", " ").replace("_", " ").strip()
