# Widget & Tool Enhancements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add 5 new interactive widgets (file viewer, editable table, paginated table, dynamic filter, 360° entity view), full-lifecycle office document tools, multimodal agent support, chat upload fixes, and API result transformation tools.

**Architecture:** Three vertical slices by domain: Document (viewer + tools + multimodal + upload fix), Table (editable + paginated + filter), Entity (360° view). Plus cross-cutting result transformation tools. Backend tools registered as built-in tools via `BuiltinToolRegistry`/`BuiltinToolExecutor`. Frontend widgets registered in `widgetRegistry` and rendered via `WidgetSlot`.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy async (backend), python-docx / openpyxl / python-pptx / reportlab / PyPDF2 (document processing), SvelteKit / Svelte 5 runes / Tailwind / lucide-svelte (frontend), pytest (tests)

---

## Context

**Widget system**: 20 widgets registered in `frontend/src/lib/widgets/registry.ts` → `widgetRegistry` map. Each widget is a Svelte component receiving props via `WidgetSlot.svelte`. Backend emits `:::widget{type="..." }\n{JSON}\n:::` directives parsed by `WidgetParser` in `src/flydesk/widgets/parser.py`.

**Built-in tools**: 6 tools in `src/flydesk/tools/builtin.py`. Each defined as a `ToolDefinition` with endpoint_id starting with `__builtin__`. Executed by `BuiltinToolExecutor` (in-process, no HTTP). Registered via `BuiltinToolRegistry.get_tool_definitions()`.

**GenAI adapter**: `src/flydesk/tools/genai_adapter.py` wraps `ToolDefinition` → `BaseTool` via `BuiltinToolAdapter` for in-process tools and `CatalogToolAdapter` for HTTP tools.

**File upload pipeline**: Frontend `uploadFile()` → `POST /api/chat/upload` → `ContentExtractor.extract()` → only handles `text/*` and `application/json`, returns `None` for everything else. `DeskAgent._build_file_context()` only reads `extracted_text` strings — never passes binary content to the LLM.

**Multimodal in genai framework**: `FireflyAgent.run()` accepts `str | Sequence[UserContent]` where `UserContent` includes `ImageUrl`, `BinaryContent`, `DocumentUrl`. Fully supported but not wired in Desk.

---

## Task 0: Add Document Processing Dependencies

**Problem:** No document processing libraries installed. Need python-docx, openpyxl, python-pptx, reportlab, PyPDF2.

**Files:**
- Modify: `pyproject.toml` — Add dependencies

**Steps:**

1. Add dependencies to `pyproject.toml` under `[project] dependencies`:
   ```
   "python-docx>=1.1",
   "openpyxl>=3.1",
   "python-pptx>=1.0",
   "reportlab>=4.0",
   "PyPDF2>=3.0",
   ```

2. Run: `uv sync`

3. Verify imports work:
   ```bash
   uv run python -c "import docx; import openpyxl; import pptx; import reportlab; import PyPDF2; print('OK')"
   ```
   Expected: `OK`

4. Commit:
   ```bash
   git add pyproject.toml uv.lock
   git commit -m "chore: add document processing dependencies"
   ```

---

## Task 1: Enhance Content Extractor for Office Documents

**Problem:** `ContentExtractor` in `src/flydesk/files/extractor.py` only handles `text/*` and `application/json`. Returns `None` for PDF, DOCX, XLSX, PPTX.

**Files:**
- Modify: `src/flydesk/files/extractor.py`
- Create: `tests/files/test_extractor.py`

**Steps:**

1. Write tests in `tests/files/test_extractor.py`:

```python
"""Tests for ContentExtractor with office document support."""

from __future__ import annotations

import io
import pytest

from flydesk.files.extractor import ContentExtractor


@pytest.fixture
def extractor():
    return ContentExtractor()


class TestTextExtraction:
    @pytest.mark.anyio
    async def test_plain_text(self, extractor):
        result = await extractor.extract("test.txt", b"Hello world", "text/plain")
        assert result == "Hello world"

    @pytest.mark.anyio
    async def test_json(self, extractor):
        result = await extractor.extract("data.json", b'{"key": "val"}', "application/json")
        assert result == '{"key": "val"}'

    @pytest.mark.anyio
    async def test_unknown_binary(self, extractor):
        result = await extractor.extract("file.bin", b"\x00\x01\x02", "application/octet-stream")
        assert result is None


class TestPdfExtraction:
    @pytest.mark.anyio
    async def test_pdf_extraction(self, extractor):
        """Create a minimal PDF and verify text extraction."""
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=letter)
        c.drawString(72, 700, "Hello from PDF")
        c.save()
        pdf_bytes = buf.getvalue()

        result = await extractor.extract("doc.pdf", pdf_bytes, "application/pdf")
        assert result is not None
        assert "Hello from PDF" in result


class TestDocxExtraction:
    @pytest.mark.anyio
    async def test_docx_extraction(self, extractor):
        """Create a minimal DOCX and verify text extraction."""
        from docx import Document

        doc = Document()
        doc.add_paragraph("Hello from DOCX")
        buf = io.BytesIO()
        doc.save(buf)
        docx_bytes = buf.getvalue()

        result = await extractor.extract(
            "doc.docx", docx_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        assert result is not None
        assert "Hello from DOCX" in result


class TestXlsxExtraction:
    @pytest.mark.anyio
    async def test_xlsx_extraction(self, extractor):
        """Create a minimal XLSX and verify text extraction."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Name"
        ws["B1"] = "Value"
        ws["A2"] = "Alpha"
        ws["B2"] = 42
        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        result = await extractor.extract(
            "data.xlsx", xlsx_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        assert result is not None
        assert "Name" in result
        assert "Alpha" in result


class TestPptxExtraction:
    @pytest.mark.anyio
    async def test_pptx_extraction(self, extractor):
        """Create a minimal PPTX and verify text extraction."""
        from pptx import Presentation

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        slide.shapes.title.text = "Slide Title"
        slide.placeholders[1].text = "Slide body text"
        buf = io.BytesIO()
        prs.save(buf)
        pptx_bytes = buf.getvalue()

        result = await extractor.extract(
            "deck.pptx", pptx_bytes,
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        assert result is not None
        assert "Slide Title" in result
        assert "Slide body text" in result
```

2. Run tests to verify they fail:
   ```bash
   uv run python -m pytest tests/files/test_extractor.py -v
   ```
   Expected: PDF/DOCX/XLSX/PPTX tests FAIL (return None)

3. Implement the enhanced extractor in `src/flydesk/files/extractor.py`:

```python
# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Content extraction from uploaded files."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract text content from uploaded files.

    Supports: text/*, JSON, PDF, DOCX, XLSX, PPTX.
    """

    async def extract(
        self, filename: str, content: bytes, content_type: str
    ) -> str | None:
        """Extract text content from a file.

        Returns the extracted text for supported types, or ``None`` for
        unsupported binary formats.
        """
        if content_type.startswith("text/"):
            return content.decode("utf-8", errors="replace")
        if content_type == "application/json":
            return content.decode("utf-8", errors="replace")
        if content_type == "application/pdf":
            return self._extract_pdf(content)
        if content_type in {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        }:
            return self._extract_docx(content)
        if content_type in {
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.ms-excel",
        }:
            return self._extract_xlsx(content)
        if content_type in {
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.ms-powerpoint",
        }:
            return self._extract_pptx(content)
        return None

    @staticmethod
    def _extract_pdf(content: bytes) -> str | None:
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(p for p in pages if p.strip())
            return text or None
        except Exception:
            logger.warning("PDF extraction failed", exc_info=True)
            return None

    @staticmethod
    def _extract_docx(content: bytes) -> str | None:
        try:
            from docx import Document

            doc = Document(io.BytesIO(content))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)
            return text or None
        except Exception:
            logger.warning("DOCX extraction failed", exc_info=True)
            return None

    @staticmethod
    def _extract_xlsx(content: bytes) -> str | None:
        try:
            from openpyxl import load_workbook

            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            parts: list[str] = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    cells = [str(c) if c is not None else "" for c in row]
                    rows.append("\t".join(cells))
                if rows:
                    header = f"[Sheet: {ws.title}]"
                    parts.append(f"{header}\n" + "\n".join(rows))
            wb.close()
            text = "\n\n".join(parts)
            return text or None
        except Exception:
            logger.warning("XLSX extraction failed", exc_info=True)
            return None

    @staticmethod
    def _extract_pptx(content: bytes) -> str | None:
        try:
            from pptx import Presentation

            prs = Presentation(io.BytesIO(content))
            slides: list[str] = []
            for i, slide in enumerate(prs.slides, 1):
                texts: list[str] = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        for para in shape.text_frame.paragraphs:
                            if para.text.strip():
                                texts.append(para.text)
                if texts:
                    slides.append(f"[Slide {i}]\n" + "\n".join(texts))
            text = "\n\n".join(slides)
            return text or None
        except Exception:
            logger.warning("PPTX extraction failed", exc_info=True)
            return None
```

4. Run tests:
   ```bash
   uv run python -m pytest tests/files/test_extractor.py -v
   ```
   Expected: ALL PASS

5. Commit:
   ```bash
   git add src/flydesk/files/extractor.py tests/files/test_extractor.py
   git commit -m "feat: enhance ContentExtractor with PDF, DOCX, XLSX, PPTX support"
   ```

---

## Task 2: File Render API Endpoint

**Problem:** Need a backend endpoint to render office documents for the file viewer widget. Different formats need different rendering: DOCX → HTML, XLSX → JSON table, PPTX → text slides, PDF → pass-through.

**Files:**
- Modify: `src/flydesk/api/files.py` — Add render endpoint
- Create: `tests/api/test_file_render.py`

**Steps:**

1. Write tests in `tests/api/test_file_render.py`:

```python
"""Tests for the file render API endpoint."""

from __future__ import annotations

import io
import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.files.repository import FileUploadRepository
from flydesk.files.storage import LocalFileStorage
from flydesk.files.extractor import ContentExtractor


ENV = {
    "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
    "FLYDESK_OIDC_CLIENT_ID": "test",
    "FLYDESK_OIDC_CLIENT_SECRET": "test",
    "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
}


@pytest.fixture
async def client(tmp_path):
    with patch.dict(os.environ, ENV):
        from flydesk.api.files import get_file_repo, get_file_storage, get_content_extractor
        from flydesk.server import create_app

        app = create_app()
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        file_repo = FileUploadRepository(session_factory)
        file_storage = LocalFileStorage(str(tmp_path / "uploads"))
        content_extractor = ContentExtractor()

        app.dependency_overrides[get_file_repo] = lambda: file_repo
        app.dependency_overrides[get_file_storage] = lambda: file_storage
        app.dependency_overrides[get_content_extractor] = lambda: content_extractor

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


class TestFileRenderEndpoint:
    @pytest.mark.anyio
    async def test_render_docx_as_html(self, client):
        from docx import Document
        doc = Document()
        doc.add_paragraph("Rendered paragraph")
        buf = io.BytesIO()
        doc.save(buf)

        upload = await client.post(
            "/api/chat/upload",
            files={"file": ("test.docx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        file_id = upload.json()["id"]

        resp = await client.get(f"/api/files/{file_id}/render?format=html")
        assert resp.status_code == 200
        body = resp.json()
        assert "html" in body
        assert "Rendered paragraph" in body["html"]

    @pytest.mark.anyio
    async def test_render_xlsx_as_json(self, client):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Name"
        ws["B1"] = "Age"
        ws["A2"] = "Alice"
        ws["B2"] = 30
        buf = io.BytesIO()
        wb.save(buf)

        upload = await client.post(
            "/api/chat/upload",
            files={"file": ("data.xlsx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        file_id = upload.json()["id"]

        resp = await client.get(f"/api/files/{file_id}/render?format=json")
        assert resp.status_code == 200
        body = resp.json()
        assert "sheets" in body
        assert body["sheets"][0]["columns"][0]["label"] == "Name"

    @pytest.mark.anyio
    async def test_render_missing_file_404(self, client):
        resp = await client.get("/api/files/nonexistent/render?format=html")
        assert resp.status_code == 404

    @pytest.mark.anyio
    async def test_render_text_file(self, client):
        upload = await client.post(
            "/api/chat/upload",
            files={"file": ("readme.txt", b"Plain text content", "text/plain")},
        )
        file_id = upload.json()["id"]

        resp = await client.get(f"/api/files/{file_id}/render?format=html")
        assert resp.status_code == 200
        body = resp.json()
        assert "text" in body
        assert "Plain text content" in body["text"]
```

2. Run to verify they fail:
   ```bash
   uv run python -m pytest tests/api/test_file_render.py -v
   ```

3. Add the render endpoint to `src/flydesk/api/files.py`. Add this after the existing `download_file` endpoint:

```python
@router.get("/api/files/{file_id}/render")
async def render_file(
    file_id: str,
    repo: FileRepo,
    storage: Storage,
    format: str = Query(default="html", description="Render format: html, json, text"),
) -> dict:
    """Render a file for preview in the file viewer widget.

    Returns rendered content based on file type:
    - DOCX → HTML
    - XLSX → JSON with sheets/columns/rows
    - PPTX → structured slide text
    - PDF → extracted text (viewer uses iframe for native rendering)
    - text/* → raw text
    """
    upload = await repo.get(file_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="File not found")

    content = await storage.retrieve(upload.storage_path)
    ct = upload.content_type

    if ct in {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    }:
        return _render_docx(content)
    if ct in {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }:
        return _render_xlsx(content)
    if ct in {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/vnd.ms-powerpoint",
    }:
        return _render_pptx(content)
    if ct == "application/pdf":
        return {"type": "pdf", "download_url": f"/api/files/{file_id}/download"}
    if ct.startswith("image/"):
        return {"type": "image", "download_url": f"/api/files/{file_id}/download"}

    # Fallback: text
    text = content.decode("utf-8", errors="replace")
    return {"type": "text", "text": text}


def _render_docx(content: bytes) -> dict:
    import io
    from docx import Document

    doc = Document(io.BytesIO(content))
    html_parts: list[str] = []
    for para in doc.paragraphs:
        if para.style and para.style.name.startswith("Heading"):
            level = para.style.name.replace("Heading ", "").strip()
            if level.isdigit():
                html_parts.append(f"<h{level}>{para.text}</h{level}>")
            else:
                html_parts.append(f"<p><strong>{para.text}</strong></p>")
        elif para.text.strip():
            html_parts.append(f"<p>{para.text}</p>")

    for table in doc.tables:
        rows_html: list[str] = []
        for i, row in enumerate(table.rows):
            cells = "".join(
                f"<{'th' if i == 0 else 'td'}>{cell.text}</{'th' if i == 0 else 'td'}>"
                for cell in row.cells
            )
            rows_html.append(f"<tr>{cells}</tr>")
        html_parts.append(f"<table>{''.join(rows_html)}</table>")

    return {"type": "docx", "html": "\n".join(html_parts)}


def _render_xlsx(content: bytes) -> dict:
    import io
    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheets = []
    for ws in wb.worksheets:
        rows_data = list(ws.iter_rows(values_only=True))
        if not rows_data:
            continue
        header = rows_data[0]
        columns = [
            {"key": f"col_{i}", "label": str(h) if h is not None else f"Column {i + 1}"}
            for i, h in enumerate(header)
        ]
        rows = []
        for row in rows_data[1:]:
            row_dict = {}
            for i, cell in enumerate(row):
                row_dict[f"col_{i}"] = cell if cell is not None else ""
            rows.append(row_dict)
        sheets.append({"title": ws.title, "columns": columns, "rows": rows})
    wb.close()
    return {"type": "xlsx", "sheets": sheets}


def _render_pptx(content: bytes) -> dict:
    import io
    from pptx import Presentation

    prs = Presentation(io.BytesIO(content))
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts: list[str] = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        texts.append(para.text)
        slides.append({"slide_number": i, "texts": texts})
    return {"type": "pptx", "slides": slides}
```

Also add the `Query` import if not already present (it should be since the existing endpoint uses it).

4. Run tests:
   ```bash
   uv run python -m pytest tests/api/test_file_render.py -v
   ```
   Expected: ALL PASS

5. Commit:
   ```bash
   git add src/flydesk/api/files.py tests/api/test_file_render.py
   git commit -m "feat: add file render endpoint for DOCX, XLSX, PPTX, PDF preview"
   ```

---

## Task 3: Multimodal Agent Wiring

**Problem:** `DeskAgent._build_file_context()` only passes `extracted_text` strings to the LLM. Need to pass actual binary content for images and documents when the LLM supports multimodal.

**Files:**
- Modify: `src/flydesk/agent/desk_agent.py` — Enhance `_build_file_context` to return multimodal content
- Modify: `src/flydesk/files/storage.py` — Need `retrieve` accessible from DeskAgent
- Create: `tests/agent/test_multimodal.py`

**Steps:**

1. Write tests in `tests/agent/test_multimodal.py`:

```python
"""Tests for multimodal file context building in DeskAgent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.agent.desk_agent import DeskAgent, _build_multimodal_parts
from flydesk.files.models import FileUpload


class TestBuildMultimodalParts:
    @pytest.mark.anyio
    async def test_image_returns_binary_content(self):
        upload = FileUpload(
            id="f1", user_id="u1", filename="photo.png",
            content_type="image/png", file_size=100,
            storage_path="/tmp/photo.png", extracted_text=None,
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"\x89PNG\r\n...")

        parts = await _build_multimodal_parts([upload], storage)
        assert len(parts) == 1
        from fireflyframework_genai.types import BinaryContent
        assert isinstance(parts[0], BinaryContent)

    @pytest.mark.anyio
    async def test_text_file_returns_string(self):
        upload = FileUpload(
            id="f2", user_id="u1", filename="notes.txt",
            content_type="text/plain", file_size=50,
            storage_path="/tmp/notes.txt", extracted_text="Hello world",
        )
        storage = AsyncMock()

        parts = await _build_multimodal_parts([upload], storage)
        assert len(parts) == 1
        assert isinstance(parts[0], str)
        assert "Hello world" in parts[0]

    @pytest.mark.anyio
    async def test_docx_returns_extracted_text(self):
        upload = FileUpload(
            id="f3", user_id="u1", filename="doc.docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=200, storage_path="/tmp/doc.docx",
            extracted_text="Document content here",
        )
        storage = AsyncMock()

        parts = await _build_multimodal_parts([upload], storage)
        assert len(parts) == 1
        assert isinstance(parts[0], str)
        assert "Document content here" in parts[0]

    @pytest.mark.anyio
    async def test_empty_list_returns_empty(self):
        storage = AsyncMock()
        parts = await _build_multimodal_parts([], storage)
        assert parts == []

    @pytest.mark.anyio
    async def test_mixed_files(self):
        img = FileUpload(
            id="f1", user_id="u1", filename="pic.jpg",
            content_type="image/jpeg", file_size=100,
            storage_path="/tmp/pic.jpg", extracted_text=None,
        )
        txt = FileUpload(
            id="f2", user_id="u1", filename="readme.md",
            content_type="text/markdown", file_size=50,
            storage_path="/tmp/readme.md", extracted_text="# Hello",
        )
        storage = AsyncMock()
        storage.retrieve = AsyncMock(return_value=b"\xff\xd8\xff\xe0...")

        parts = await _build_multimodal_parts([img, txt], storage)
        assert len(parts) == 2
```

2. Run to verify they fail:
   ```bash
   uv run python -m pytest tests/agent/test_multimodal.py -v
   ```

3. Add the `_build_multimodal_parts` function and modify `_build_file_context` in `src/flydesk/agent/desk_agent.py`.

First, add at the top of the file (after existing imports):
```python
from flydesk.files.models import FileUpload
from flydesk.files.storage import FileStorageProvider
```

Add a module-level helper function (outside the class, near the bottom before any private helpers):
```python
_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"}


async def _build_multimodal_parts(
    uploads: list[FileUpload],
    storage: FileStorageProvider,
) -> list:
    """Build multimodal content parts from file uploads.

    - Images → BinaryContent (for multimodal LLMs)
    - Text/docs with extracted_text → string context
    """
    from fireflyframework_genai.types import BinaryContent

    parts: list = []
    for upload in uploads:
        if upload.content_type in _IMAGE_CONTENT_TYPES:
            raw = await storage.retrieve(upload.storage_path)
            parts.append(BinaryContent(data=raw, media_type=upload.content_type))
        elif upload.extracted_text:
            parts.append(f"[{upload.filename}]: {upload.extracted_text}")
    return parts
```

Then modify the `DeskAgent.__init__` to also accept a `file_storage` parameter:
- Add `file_storage: FileStorageProvider | None = None` to the constructor
- Store as `self._file_storage = file_storage`

Modify `_build_file_context` to also return multimodal parts:
```python
async def _build_file_context(
    self, file_ids: list[str] | None
) -> tuple[str, list]:
    """Fetch uploaded files and build both text context and multimodal parts.

    Returns (text_context, multimodal_parts).
    """
    if not file_ids or self._file_repo is None:
        return "", []

    uploads: list[FileUpload] = []
    for file_id in file_ids:
        upload = await self._file_repo.get(file_id)
        if upload is not None:
            uploads.append(upload)

    # Text context (always available)
    text_parts: list[str] = []
    for upload in uploads:
        text = upload.extracted_text or ""
        if text:
            text_parts.append(f"- [{upload.filename}]: {text}")
    text_context = "\n".join(text_parts)

    # Multimodal parts (for capable LLMs)
    multimodal_parts: list = []
    if self._file_storage is not None:
        multimodal_parts = await _build_multimodal_parts(uploads, self._file_storage)

    return text_context, multimodal_parts
```

Update all callers of `_build_file_context` in the class:
- In `_prepare_turn`: change `file_context = await self._build_file_context(file_ids)` to `file_context, multimodal_parts = await self._build_file_context(file_ids)` and return `multimodal_parts` alongside.
- In `run()` and `stream()` and `run_with_reasoning()`: when calling `FireflyAgent.run()`, if `multimodal_parts` is non-empty, prepend the user message as a string part and pass the full list as the prompt instead of just the string message.

4. Run tests:
   ```bash
   uv run python -m pytest tests/agent/test_multimodal.py -v
   ```
   Expected: ALL PASS

5. Run full agent tests to ensure no regressions:
   ```bash
   uv run python -m pytest tests/agent/ -v
   ```

6. Commit:
   ```bash
   git add src/flydesk/agent/desk_agent.py tests/agent/test_multimodal.py
   git commit -m "feat: wire multimodal file content into DeskAgent for image/doc support"
   ```

---

## Task 4: Document Tools — Read, Create, Modify, Convert

**Problem:** No tools for the agent to read, create, modify, or convert office documents.

**Files:**
- Create: `src/flydesk/tools/document_tools.py` — Document tool definitions + executor methods
- Modify: `src/flydesk/tools/builtin.py` — Register document tools
- Create: `tests/tools/test_document_tools.py`

**Steps:**

1. Write tests in `tests/tools/test_document_tools.py`:

```python
"""Tests for document tools (read, create, modify, convert)."""

from __future__ import annotations

import io
import pytest
from unittest.mock import AsyncMock

from flydesk.tools.document_tools import DocumentToolExecutor


@pytest.fixture
def storage():
    mock = AsyncMock()
    mock.retrieve = AsyncMock()
    mock.store = AsyncMock(return_value="/tmp/out.pdf")
    return mock


@pytest.fixture
def executor(storage):
    return DocumentToolExecutor(storage)


class TestDocumentRead:
    @pytest.mark.anyio
    async def test_read_docx(self, executor, storage):
        from docx import Document
        doc = Document()
        doc.add_paragraph("Test content")
        buf = io.BytesIO()
        doc.save(buf)
        storage.retrieve.return_value = buf.getvalue()

        result = await executor.execute("document_read", {
            "file_path": "/tmp/test.docx",
            "file_type": "docx",
        })
        assert "text" in result
        assert "Test content" in result["text"]

    @pytest.mark.anyio
    async def test_read_xlsx(self, executor, storage):
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Header"
        ws["A2"] = "Value"
        buf = io.BytesIO()
        wb.save(buf)
        storage.retrieve.return_value = buf.getvalue()

        result = await executor.execute("document_read", {
            "file_path": "/tmp/data.xlsx",
            "file_type": "xlsx",
        })
        assert "sheets" in result


class TestDocumentCreate:
    @pytest.mark.anyio
    async def test_create_docx(self, executor, storage):
        result = await executor.execute("document_create", {
            "file_type": "docx",
            "title": "My Report",
            "content": "This is the report body.",
            "output_filename": "report.docx",
        })
        assert "file_path" in result
        storage.store.assert_awaited_once()

    @pytest.mark.anyio
    async def test_create_xlsx(self, executor, storage):
        result = await executor.execute("document_create", {
            "file_type": "xlsx",
            "title": "Data Export",
            "content": '[{"name": "Alice", "age": 30}]',
            "output_filename": "data.xlsx",
        })
        assert "file_path" in result

    @pytest.mark.anyio
    async def test_create_pdf(self, executor, storage):
        result = await executor.execute("document_create", {
            "file_type": "pdf",
            "title": "Invoice",
            "content": "Invoice content here",
            "output_filename": "invoice.pdf",
        })
        assert "file_path" in result
```

2. Run to verify they fail:
   ```bash
   uv run python -m pytest tests/tools/test_document_tools.py -v
   ```

3. Create `src/flydesk/tools/document_tools.py`:

```python
# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Document tools for reading, creating, modifying, and converting office documents."""

from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING, Any

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.tools.factory import ToolDefinition

if TYPE_CHECKING:
    from flydesk.files.storage import FileStorageProvider

logger = logging.getLogger(__name__)

BUILTIN_SYSTEM_ID = "__flydesk__"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def document_read_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__document_read",
        name="document_read",
        description=(
            "Extract text, tables, and metadata from an office document "
            "(PDF, DOCX, XLSX, PPTX). Returns structured text content. "
            "Use when: the user asks about the contents of an uploaded document, "
            "needs specific data extracted, or wants a summary."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/documents/read",
        parameters={
            "file_path": {"type": "string", "description": "Storage path of the file", "required": True},
            "file_type": {"type": "string", "description": "File type: pdf, docx, xlsx, pptx", "required": True},
        },
    )


def document_create_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__document_create",
        name="document_create",
        description=(
            "Create a new office document (PDF, DOCX, XLSX). "
            "For DOCX: provide text content with paragraphs. "
            "For XLSX: provide JSON array of objects for rows. "
            "For PDF: provide text content. "
            "Use when: the user asks to generate a report, export data, or create a document."
        ),
        risk_level=RiskLevel.LOW_WRITE,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/create",
        parameters={
            "file_type": {"type": "string", "description": "Output type: pdf, docx, xlsx", "required": True},
            "title": {"type": "string", "description": "Document title", "required": True},
            "content": {"type": "string", "description": "Document content (text or JSON array for XLSX)", "required": True},
            "output_filename": {"type": "string", "description": "Desired filename", "required": True},
        },
    )


def document_modify_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__document_modify",
        name="document_modify",
        description=(
            "Modify an existing document. "
            "DOCX: append paragraphs, replace text. "
            "XLSX: update cells, add rows. "
            "PDF: merge multiple PDFs. "
            "Use when: the user wants to edit or update an existing document."
        ),
        risk_level=RiskLevel.LOW_WRITE,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/modify",
        parameters={
            "file_path": {"type": "string", "description": "Storage path of the file to modify", "required": True},
            "file_type": {"type": "string", "description": "File type: docx, xlsx, pdf", "required": True},
            "action": {"type": "string", "description": "Action: append, replace, merge, update_cells", "required": True},
            "data": {"type": "string", "description": "Action data (JSON): replacement text, new rows, etc.", "required": True},
            "output_filename": {"type": "string", "description": "Output filename", "required": True},
        },
    )


def document_convert_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__document_convert",
        name="document_convert",
        description=(
            "Convert a document between formats. "
            "Supported conversions: XLSX→CSV, DOCX→text. "
            "Use when: the user needs data in a different format."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/convert",
        parameters={
            "file_path": {"type": "string", "description": "Storage path of the source file", "required": True},
            "source_type": {"type": "string", "description": "Source format: docx, xlsx, pptx", "required": True},
            "target_type": {"type": "string", "description": "Target format: csv, text", "required": True},
            "output_filename": {"type": "string", "description": "Output filename", "required": True},
        },
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class DocumentToolExecutor:
    """Execute document tools using office document libraries."""

    def __init__(self, storage: FileStorageProvider) -> None:
        self._storage = storage

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "document_read": self._read,
            "document_create": self._create,
            "document_modify": self._modify,
            "document_convert": self._convert,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown document tool: {tool_name}"}
        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Document tool %s failed: %s", tool_name, exc, exc_info=True)
            return {"error": str(exc)}

    def is_document_tool(self, tool_name: str) -> bool:
        return tool_name.startswith("document_")

    async def _read(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path = args["file_path"]
        file_type = args["file_type"].lower()
        content = await self._storage.retrieve(file_path)

        if file_type == "pdf":
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            return {"text": "\n\n".join(pages), "page_count": len(reader.pages)}

        if file_type == "docx":
            from docx import Document
            doc = Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            tables = []
            for table in doc.tables:
                rows = [[cell.text for cell in row.cells] for row in table.rows]
                tables.append(rows)
            return {"text": text, "tables": tables}

        if file_type == "xlsx":
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheets = []
            for ws in wb.worksheets:
                rows = []
                for row in ws.iter_rows(values_only=True):
                    rows.append([str(c) if c is not None else "" for c in row])
                sheets.append({"title": ws.title, "rows": rows})
            wb.close()
            return {"sheets": sheets}

        if file_type == "pptx":
            from pptx import Presentation
            prs = Presentation(io.BytesIO(content))
            slides = []
            for i, slide in enumerate(prs.slides, 1):
                texts = []
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        texts.extend(p.text for p in shape.text_frame.paragraphs if p.text.strip())
                slides.append({"slide": i, "texts": texts})
            return {"slides": slides}

        return {"error": f"Unsupported file type: {file_type}"}

    async def _create(self, args: dict[str, Any]) -> dict[str, Any]:
        file_type = args["file_type"].lower()
        title = args["title"]
        content_str = args["content"]
        output_filename = args["output_filename"]

        if file_type == "docx":
            from docx import Document
            doc = Document()
            doc.add_heading(title, level=1)
            for para in content_str.split("\n"):
                if para.strip():
                    doc.add_paragraph(para)
            buf = io.BytesIO()
            doc.save(buf)
            ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            path = await self._storage.store(output_filename, buf.getvalue(), ct)
            return {"file_path": path, "filename": output_filename, "file_type": "docx"}

        if file_type == "xlsx":
            from openpyxl import Workbook
            data = json.loads(content_str) if isinstance(content_str, str) else content_str
            wb = Workbook()
            ws = wb.active
            ws.title = title
            if data and isinstance(data, list) and isinstance(data[0], dict):
                headers = list(data[0].keys())
                ws.append(headers)
                for row in data:
                    ws.append([row.get(h, "") for h in headers])
            buf = io.BytesIO()
            wb.save(buf)
            ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            path = await self._storage.store(output_filename, buf.getvalue(), ct)
            return {"file_path": path, "filename": output_filename, "file_type": "xlsx"}

        if file_type == "pdf":
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet

            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=letter)
            styles = getSampleStyleSheet()
            story = [Paragraph(title, styles["Title"]), Spacer(1, 12)]
            for para in content_str.split("\n"):
                if para.strip():
                    story.append(Paragraph(para, styles["Normal"]))
                    story.append(Spacer(1, 6))
            doc.build(story)
            path = await self._storage.store(output_filename, buf.getvalue(), "application/pdf")
            return {"file_path": path, "filename": output_filename, "file_type": "pdf"}

        return {"error": f"Cannot create file type: {file_type}"}

    async def _modify(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path = args["file_path"]
        file_type = args["file_type"].lower()
        action = args["action"]
        data = json.loads(args["data"]) if isinstance(args["data"], str) else args["data"]
        output_filename = args["output_filename"]

        content = await self._storage.retrieve(file_path)

        if file_type == "docx" and action == "append":
            from docx import Document
            doc = Document(io.BytesIO(content))
            for text in (data if isinstance(data, list) else [data]):
                doc.add_paragraph(str(text))
            buf = io.BytesIO()
            doc.save(buf)
            ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            path = await self._storage.store(output_filename, buf.getvalue(), ct)
            return {"file_path": path, "filename": output_filename}

        if file_type == "docx" and action == "replace":
            from docx import Document
            doc = Document(io.BytesIO(content))
            old_text = data.get("old", "")
            new_text = data.get("new", "")
            for para in doc.paragraphs:
                if old_text in para.text:
                    para.text = para.text.replace(old_text, new_text)
            buf = io.BytesIO()
            doc.save(buf)
            ct = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            path = await self._storage.store(output_filename, buf.getvalue(), ct)
            return {"file_path": path, "filename": output_filename}

        if file_type == "xlsx" and action == "update_cells":
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content))
            ws = wb.active
            for update in (data if isinstance(data, list) else [data]):
                cell = update.get("cell", "")
                value = update.get("value", "")
                if cell:
                    ws[cell] = value
            buf = io.BytesIO()
            wb.save(buf)
            ct = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            path = await self._storage.store(output_filename, buf.getvalue(), ct)
            return {"file_path": path, "filename": output_filename}

        if file_type == "pdf" and action == "merge":
            from PyPDF2 import PdfMerger
            merger = PdfMerger()
            merger.append(io.BytesIO(content))
            for extra_path in (data if isinstance(data, list) else [data]):
                extra = await self._storage.retrieve(str(extra_path))
                merger.append(io.BytesIO(extra))
            buf = io.BytesIO()
            merger.write(buf)
            merger.close()
            path = await self._storage.store(output_filename, buf.getvalue(), "application/pdf")
            return {"file_path": path, "filename": output_filename}

        return {"error": f"Unsupported modify action: {action} for {file_type}"}

    async def _convert(self, args: dict[str, Any]) -> dict[str, Any]:
        file_path = args["file_path"]
        source_type = args["source_type"].lower()
        target_type = args["target_type"].lower()
        output_filename = args["output_filename"]

        content = await self._storage.retrieve(file_path)

        if source_type == "xlsx" and target_type == "csv":
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            lines: list[str] = []
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                lines.append(",".join(cells))
            wb.close()
            csv_bytes = "\n".join(lines).encode("utf-8")
            path = await self._storage.store(output_filename, csv_bytes, "text/csv")
            return {"file_path": path, "filename": output_filename}

        if source_type == "docx" and target_type == "text":
            from docx import Document
            doc = Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
            path = await self._storage.store(output_filename, text.encode("utf-8"), "text/plain")
            return {"file_path": path, "filename": output_filename}

        return {"error": f"Unsupported conversion: {source_type} → {target_type}"}
```

4. Register document tools in `src/flydesk/tools/builtin.py`. In `BuiltinToolRegistry.get_tool_definitions()`, add after the existing tools:

```python
# Document tools (require knowledge:read or *)
if has_all or "knowledge:read" in user_permissions:
    from flydesk.tools.document_tools import (
        document_read_tool,
        document_create_tool,
        document_modify_tool,
        document_convert_tool,
    )
    tools.append(document_read_tool())
    tools.append(document_create_tool())
    tools.append(document_modify_tool())
    tools.append(document_convert_tool())
```

Also add document tool execution routing in `BuiltinToolExecutor.execute()`. Add a `_doc_executor` property and route document tool calls to `DocumentToolExecutor`:

```python
# In BuiltinToolExecutor.__init__, add:
self._doc_executor: DocumentToolExecutor | None = None

# Add property:
def set_document_executor(self, executor: DocumentToolExecutor) -> None:
    self._doc_executor = executor

# In execute(), add before the existing handlers dict:
if tool_name.startswith("document_") and self._doc_executor is not None:
    return await self._doc_executor.execute(tool_name, arguments)
```

5. Run tests:
   ```bash
   uv run python -m pytest tests/tools/test_document_tools.py -v
   ```
   Expected: ALL PASS

6. Run existing tool tests for regression:
   ```bash
   uv run python -m pytest tests/tools/ -v
   ```

7. Commit:
   ```bash
   git add src/flydesk/tools/document_tools.py src/flydesk/tools/builtin.py tests/tools/test_document_tools.py
   git commit -m "feat: add document tools for read, create, modify, convert office documents"
   ```

---

## Task 5: Result Transformation Tools

**Problem:** Agent needs tools to grep, parse, extract, and filter API results.

**Files:**
- Create: `src/flydesk/tools/transform_tools.py`
- Modify: `src/flydesk/tools/builtin.py` — Register transform tools
- Create: `tests/tools/test_transform_tools.py`

**Steps:**

1. Write tests in `tests/tools/test_transform_tools.py`:

```python
"""Tests for result transformation tools."""

from __future__ import annotations

import pytest

from flydesk.tools.transform_tools import TransformToolExecutor


@pytest.fixture
def executor():
    return TransformToolExecutor()


class TestGrepResult:
    @pytest.mark.anyio
    async def test_grep_lines(self, executor):
        result = await executor.execute("grep_result", {
            "data": "line one\nline two\nerror: failed\nline four",
            "pattern": "error",
        })
        assert result["matches"] == ["error: failed"]

    @pytest.mark.anyio
    async def test_grep_json_array(self, executor):
        result = await executor.execute("grep_result", {
            "data": '[{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]',
            "pattern": "Ali",
        })
        assert len(result["matches"]) == 2


class TestParseJson:
    @pytest.mark.anyio
    async def test_extract_path(self, executor):
        result = await executor.execute("parse_json", {
            "data": '{"user": {"name": "Alice", "address": {"city": "NYC"}}}',
            "path": "user.address.city",
        })
        assert result["value"] == "NYC"

    @pytest.mark.anyio
    async def test_keys(self, executor):
        result = await executor.execute("parse_json", {
            "data": '{"a": 1, "b": 2, "c": 3}',
            "action": "keys",
        })
        assert result["keys"] == ["a", "b", "c"]


class TestFilterRows:
    @pytest.mark.anyio
    async def test_filter_equals(self, executor):
        result = await executor.execute("filter_rows", {
            "data": '[{"status": "active", "name": "A"}, {"status": "inactive", "name": "B"}, {"status": "active", "name": "C"}]',
            "field": "status",
            "operator": "eq",
            "value": "active",
        })
        assert len(result["rows"]) == 2

    @pytest.mark.anyio
    async def test_filter_contains(self, executor):
        result = await executor.execute("filter_rows", {
            "data": '[{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]',
            "field": "name",
            "operator": "contains",
            "value": "Ali",
        })
        assert len(result["rows"]) == 2


class TestTransformData:
    @pytest.mark.anyio
    async def test_sort(self, executor):
        result = await executor.execute("transform_data", {
            "data": '[{"name": "C"}, {"name": "A"}, {"name": "B"}]',
            "action": "sort",
            "field": "name",
        })
        assert [r["name"] for r in result["rows"]] == ["A", "B", "C"]

    @pytest.mark.anyio
    async def test_group_by(self, executor):
        result = await executor.execute("transform_data", {
            "data": '[{"type": "a", "v": 1}, {"type": "b", "v": 2}, {"type": "a", "v": 3}]',
            "action": "group",
            "field": "type",
        })
        assert "a" in result["groups"]
        assert len(result["groups"]["a"]) == 2
```

2. Run to verify they fail:
   ```bash
   uv run python -m pytest tests/tools/test_transform_tools.py -v
   ```

3. Create `src/flydesk/tools/transform_tools.py`:

```python
# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Result transformation tools for processing API and tool output."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.tools.factory import ToolDefinition

logger = logging.getLogger(__name__)

BUILTIN_SYSTEM_ID = "__flydesk__"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def grep_result_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__grep_result",
        name="grep_result",
        description=(
            "Filter lines or objects from text/JSON data matching a regex pattern. "
            "Use when: you need to find specific entries in a large API response, "
            "log output, or any text data."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/grep",
        parameters={
            "data": {"type": "string", "description": "Text or JSON string to search", "required": True},
            "pattern": {"type": "string", "description": "Regex pattern to match", "required": True},
        },
    )


def parse_json_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__parse_json",
        name="parse_json",
        description=(
            "Parse JSON data and extract values by path, list keys, or validate structure. "
            "Use when: you need to extract specific fields from a JSON API response."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/parse_json",
        parameters={
            "data": {"type": "string", "description": "JSON string to parse", "required": True},
            "path": {"type": "string", "description": "Dot-separated path to extract (e.g. 'user.address.city')", "required": False},
            "action": {"type": "string", "description": "Action: extract (default), keys, validate", "required": False},
        },
    )


def filter_rows_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__filter_rows",
        name="filter_rows",
        description=(
            "Filter an array of objects by field conditions. "
            "Operators: eq, neq, gt, lt, gte, lte, contains. "
            "Use when: you need to narrow down results from an API call."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/filter",
        parameters={
            "data": {"type": "string", "description": "JSON array of objects", "required": True},
            "field": {"type": "string", "description": "Field name to filter on", "required": True},
            "operator": {"type": "string", "description": "Operator: eq, neq, gt, lt, gte, lte, contains", "required": True},
            "value": {"type": "string", "description": "Value to compare against", "required": True},
        },
    )


def transform_data_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__transform_data",
        name="transform_data",
        description=(
            "Transform an array of objects: sort, group, count, or pick fields. "
            "Use when: you need to reorganize or aggregate API results."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/transform/data",
        parameters={
            "data": {"type": "string", "description": "JSON array of objects", "required": True},
            "action": {"type": "string", "description": "Action: sort, group, count, pick", "required": True},
            "field": {"type": "string", "description": "Field to act on", "required": True},
            "order": {"type": "string", "description": "Sort order: asc (default), desc", "required": False},
        },
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class TransformToolExecutor:
    """Execute result transformation tools."""

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "grep_result": self._grep,
            "parse_json": self._parse_json,
            "filter_rows": self._filter_rows,
            "transform_data": self._transform_data,
        }
        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown transform tool: {tool_name}"}
        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Transform tool %s failed: %s", tool_name, exc, exc_info=True)
            return {"error": str(exc)}

    def is_transform_tool(self, tool_name: str) -> bool:
        return tool_name in {"grep_result", "parse_json", "filter_rows", "transform_data"}

    async def _grep(self, args: dict[str, Any]) -> dict[str, Any]:
        data = args["data"]
        pattern = args["pattern"]
        regex = re.compile(pattern, re.IGNORECASE)

        # Try JSON array first
        try:
            items = json.loads(data)
            if isinstance(items, list):
                matches = [item for item in items if regex.search(json.dumps(item))]
                return {"matches": matches, "count": len(matches)}
        except (json.JSONDecodeError, TypeError):
            pass

        # Fall back to line-by-line
        lines = data.split("\n")
        matches = [line for line in lines if regex.search(line)]
        return {"matches": matches, "count": len(matches)}

    async def _parse_json(self, args: dict[str, Any]) -> dict[str, Any]:
        data = json.loads(args["data"])
        action = args.get("action", "extract")
        path = args.get("path")

        if action == "keys":
            if isinstance(data, dict):
                return {"keys": list(data.keys())}
            return {"error": "Data is not an object"}

        if action == "validate":
            return {"valid": True}

        # Default: extract by path
        if path:
            current = data
            for key in path.split("."):
                if isinstance(current, dict):
                    current = current.get(key)
                elif isinstance(current, list) and key.isdigit():
                    current = current[int(key)]
                else:
                    return {"error": f"Cannot traverse path at '{key}'", "value": None}
            return {"value": current}

        return {"value": data}

    async def _filter_rows(self, args: dict[str, Any]) -> dict[str, Any]:
        rows = json.loads(args["data"])
        field = args["field"]
        op = args["operator"]
        value = args["value"]

        filtered = []
        for row in rows:
            cell = row.get(field)
            if cell is None:
                continue
            cell_str = str(cell)
            if op == "eq" and cell_str == value:
                filtered.append(row)
            elif op == "neq" and cell_str != value:
                filtered.append(row)
            elif op == "contains" and value in cell_str:
                filtered.append(row)
            elif op in ("gt", "lt", "gte", "lte"):
                try:
                    cell_num = float(cell_str)
                    val_num = float(value)
                    if op == "gt" and cell_num > val_num:
                        filtered.append(row)
                    elif op == "lt" and cell_num < val_num:
                        filtered.append(row)
                    elif op == "gte" and cell_num >= val_num:
                        filtered.append(row)
                    elif op == "lte" and cell_num <= val_num:
                        filtered.append(row)
                except ValueError:
                    pass

        return {"rows": filtered, "count": len(filtered)}

    async def _transform_data(self, args: dict[str, Any]) -> dict[str, Any]:
        rows = json.loads(args["data"])
        action = args["action"]
        field = args["field"]

        if action == "sort":
            order = args.get("order", "asc")
            reverse = order == "desc"
            sorted_rows = sorted(rows, key=lambda r: str(r.get(field, "")), reverse=reverse)
            return {"rows": sorted_rows}

        if action == "group":
            groups: dict[str, list] = defaultdict(list)
            for row in rows:
                key = str(row.get(field, ""))
                groups[key].append(row)
            return {"groups": dict(groups)}

        if action == "count":
            counts: dict[str, int] = defaultdict(int)
            for row in rows:
                key = str(row.get(field, ""))
                counts[key] += 1
            return {"counts": dict(counts)}

        if action == "pick":
            fields = [f.strip() for f in field.split(",")]
            picked = [{k: row.get(k) for k in fields} for row in rows]
            return {"rows": picked}

        return {"error": f"Unknown action: {action}"}
```

4. Register in `src/flydesk/tools/builtin.py`. In `BuiltinToolRegistry.get_tool_definitions()`, add:

```python
# Transform tools (always available)
from flydesk.tools.transform_tools import (
    grep_result_tool,
    parse_json_tool,
    filter_rows_tool,
    transform_data_tool,
)
tools.append(grep_result_tool())
tools.append(parse_json_tool())
tools.append(filter_rows_tool())
tools.append(transform_data_tool())
```

In `BuiltinToolExecutor.execute()`, add routing for transform tools:

```python
# Add to __init__:
self._transform_executor = TransformToolExecutor()

# Add before existing handlers dict:
if self._transform_executor.is_transform_tool(tool_name):
    return await self._transform_executor.execute(tool_name, arguments)
```

Add the import at the top of `builtin.py`:
```python
from flydesk.tools.transform_tools import TransformToolExecutor
```

5. Run tests:
   ```bash
   uv run python -m pytest tests/tools/test_transform_tools.py -v
   ```
   Expected: ALL PASS

6. Run all tool tests:
   ```bash
   uv run python -m pytest tests/tools/ -v
   ```

7. Commit:
   ```bash
   git add src/flydesk/tools/transform_tools.py src/flydesk/tools/builtin.py tests/tools/test_transform_tools.py
   git commit -m "feat: add result transformation tools (grep, parse_json, filter_rows, transform_data)"
   ```

---

## Task 6: File Viewer Widget (Frontend)

**Problem:** No way to preview uploaded files. Need a click-to-open modal viewer.

**Files:**
- Create: `frontend/src/lib/components/widgets/FileViewer.svelte`
- Create: `frontend/src/lib/components/chat/FileViewerModal.svelte`
- Modify: `frontend/src/lib/widgets/registry.ts` — Register `file_viewer`
- Modify: `frontend/src/lib/components/chat/MessageBubble.svelte` — Open viewer on file click

**Steps:**

1. Create `frontend/src/lib/components/chat/FileViewerModal.svelte`:

```svelte
<script lang="ts">
	import { X, Download, ChevronLeft, ChevronRight } from 'lucide-svelte';
	import { fade, fly } from 'svelte/transition';

	interface FileViewerModalProps {
		fileId: string;
		fileName: string;
		contentType: string;
		onClose: () => void;
	}

	let { fileId, fileName, contentType, onClose }: FileViewerModalProps = $props();

	let renderData: any = $state(null);
	let loading = $state(true);
	let error = $state('');
	let activeSheet = $state(0);
	let activeSlide = $state(0);

	const isPdf = $derived(contentType === 'application/pdf');
	const isImage = $derived(contentType.startsWith('image/'));
	const isDocx = $derived(
		contentType.includes('wordprocessingml') || contentType === 'application/msword'
	);
	const isXlsx = $derived(
		contentType.includes('spreadsheetml') || contentType === 'application/vnd.ms-excel'
	);
	const isPptx = $derived(
		contentType.includes('presentationml') || contentType === 'application/vnd.ms-powerpoint'
	);

	$effect(() => {
		if (isPdf || isImage) {
			loading = false;
			return;
		}
		fetchRenderData();
	});

	async function fetchRenderData() {
		loading = true;
		error = '';
		try {
			const resp = await fetch(`/api/files/${fileId}/render?format=${isXlsx ? 'json' : 'html'}`);
			if (!resp.ok) throw new Error(`Failed to render: ${resp.statusText}`);
			renderData = await resp.json();
		} catch (e: any) {
			error = e.message || 'Failed to load file preview';
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- Backdrop -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
	transition:fade={{ duration: 200 }}
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<!-- Modal -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="relative flex h-[85vh] w-[85vw] max-w-6xl flex-col overflow-hidden rounded-xl border border-border bg-surface shadow-2xl"
		transition:fly={{ y: 20, duration: 250 }}
		onclick|stopPropagation={() => {}}
		onkeydown={() => {}}
	>
		<!-- Header -->
		<div class="flex items-center justify-between border-b border-border px-4 py-3">
			<h3 class="truncate text-sm font-semibold text-text-primary">{fileName}</h3>
			<div class="flex items-center gap-2">
				<a
					href="/api/files/{fileId}/download"
					target="_blank"
					rel="noopener noreferrer"
					class="rounded-md p-1.5 text-text-secondary hover:bg-surface-secondary hover:text-text-primary transition-colors"
				>
					<Download size={16} />
				</a>
				<button
					type="button"
					class="rounded-md p-1.5 text-text-secondary hover:bg-surface-secondary hover:text-text-primary transition-colors"
					onclick={onClose}
				>
					<X size={16} />
				</button>
			</div>
		</div>

		<!-- Content -->
		<div class="flex-1 overflow-auto p-4">
			{#if loading}
				<div class="flex h-full items-center justify-center">
					<div class="h-8 w-8 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
				</div>
			{:else if error}
				<div class="flex h-full items-center justify-center text-sm text-danger">{error}</div>
			{:else if isPdf}
				<iframe
					src="/api/files/{fileId}/download"
					class="h-full w-full rounded-lg border border-border"
					title={fileName}
				></iframe>
			{:else if isImage}
				<div class="flex h-full items-center justify-center">
					<img
						src="/api/files/{fileId}/download"
						alt={fileName}
						class="max-h-full max-w-full rounded-lg object-contain"
					/>
				</div>
			{:else if isDocx && renderData?.html}
				<div class="prose prose-sm max-w-none dark:prose-invert">
					{@html renderData.html}
				</div>
			{:else if isXlsx && renderData?.sheets}
				{#if renderData.sheets.length > 1}
					<div class="mb-3 flex gap-1 border-b border-border">
						{#each renderData.sheets as sheet, i}
							<button
								type="button"
								class="px-3 py-1.5 text-xs font-medium transition-colors {activeSheet === i
									? 'border-b-2 border-accent text-accent'
									: 'text-text-secondary hover:text-text-primary'}"
								onclick={() => (activeSheet = i)}
							>
								{sheet.title}
							</button>
						{/each}
					</div>
				{/if}
				{#if renderData.sheets[activeSheet]}
					<div class="overflow-auto">
						<table class="w-full text-left text-xs">
							<thead>
								<tr class="border-b border-border bg-surface-secondary">
									{#each renderData.sheets[activeSheet].columns as col}
										<th class="px-3 py-2 font-semibold text-text-primary">{col.label}</th>
									{/each}
								</tr>
							</thead>
							<tbody>
								{#each renderData.sheets[activeSheet].rows as row, i}
									<tr class="border-b border-border/50 {i % 2 === 0 ? '' : 'bg-surface-secondary/50'}">
										{#each renderData.sheets[activeSheet].columns as col}
											<td class="px-3 py-1.5 text-text-primary">{row[col.key] ?? ''}</td>
										{/each}
									</tr>
								{/each}
							</tbody>
						</table>
					</div>
				{/if}
			{:else if isPptx && renderData?.slides}
				<div class="flex h-full flex-col">
					<div class="flex-1 flex items-center justify-center p-4">
						{#if renderData.slides[activeSlide]}
							<div class="w-full max-w-2xl rounded-lg border border-border bg-white p-8 shadow-md dark:bg-surface-elevated">
								{#each renderData.slides[activeSlide].texts as text}
									<p class="mb-2 text-sm text-text-primary">{text}</p>
								{/each}
							</div>
						{/if}
					</div>
					<div class="flex items-center justify-center gap-4 border-t border-border py-2">
						<button
							type="button"
							class="rounded p-1 text-text-secondary hover:text-text-primary disabled:opacity-30"
							disabled={activeSlide === 0}
							onclick={() => (activeSlide -= 1)}
						>
							<ChevronLeft size={20} />
						</button>
						<span class="text-xs text-text-secondary">
							Slide {activeSlide + 1} of {renderData.slides.length}
						</span>
						<button
							type="button"
							class="rounded p-1 text-text-secondary hover:text-text-primary disabled:opacity-30"
							disabled={activeSlide === renderData.slides.length - 1}
							onclick={() => (activeSlide += 1)}
						>
							<ChevronRight size={20} />
						</button>
					</div>
				</div>
			{:else if renderData?.text}
				<pre class="whitespace-pre-wrap text-sm text-text-primary">{renderData.text}</pre>
			{:else}
				<div class="flex h-full items-center justify-center text-sm text-text-secondary">
					Preview not available for this file type
				</div>
			{/if}
		</div>
	</div>
</div>
```

2. Create `frontend/src/lib/components/widgets/FileViewer.svelte`:

```svelte
<script lang="ts">
	import { Eye } from 'lucide-svelte';
	import FileViewerModal from '$lib/components/chat/FileViewerModal.svelte';

	interface FileViewerProps {
		file_id: string;
		file_name?: string;
		content_type?: string;
	}

	let { file_id, file_name = 'File', content_type = 'application/octet-stream' }: FileViewerProps = $props();

	let showModal = $state(false);
</script>

<button
	type="button"
	class="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:bg-surface-secondary"
	onclick={() => (showModal = true)}
>
	<Eye size={14} />
	{file_name}
</button>

{#if showModal}
	<FileViewerModal
		fileId={file_id}
		fileName={file_name}
		contentType={content_type}
		onClose={() => (showModal = false)}
	/>
{/if}
```

3. Register in `frontend/src/lib/widgets/registry.ts`. Add import and entry:

```typescript
import FileViewer from '$lib/components/widgets/FileViewer.svelte';

// In widgetRegistry:
'file-viewer': FileViewer,
```

4. Modify `frontend/src/lib/components/chat/MessageBubble.svelte` to open the viewer on file click. Replace the non-image file `<a>` link (around line 135-147) with a button that opens the viewer, and replace the image click handler similarly:

Import `FileViewerModal` at the top and add state:
```typescript
import FileViewerModal from '$lib/components/chat/FileViewerModal.svelte';

let viewerFile: { id: string; filename: string; content_type: string } | null = $state(null);
```

Replace the file attachment click to open the viewer instead of downloading:
- For images: change the `onclick` to `() => viewerFile = { id: file.id, filename: file.filename, content_type: file.content_type }`
- For non-images: change the `<a>` to a `<button>` with the same onclick

Add at the end of the component template:
```svelte
{#if viewerFile}
	<FileViewerModal
		fileId={viewerFile.id}
		fileName={viewerFile.filename}
		contentType={viewerFile.content_type}
		onClose={() => (viewerFile = null)}
	/>
{/if}
```

5. Run frontend check:
   ```bash
   cd frontend && npm run check
   ```

6. Commit:
   ```bash
   git add frontend/src/lib/components/widgets/FileViewer.svelte frontend/src/lib/components/chat/FileViewerModal.svelte frontend/src/lib/widgets/registry.ts frontend/src/lib/components/chat/MessageBubble.svelte
   git commit -m "feat: add file viewer widget with click-to-open modal for PDF, DOCX, XLSX, PPTX"
   ```

---

## Task 7: Editable Table Widget (Frontend)

**Files:**
- Create: `frontend/src/lib/components/widgets/EditableDataTable.svelte`
- Modify: `frontend/src/lib/widgets/registry.ts` — Register

**Steps:**

1. Create `frontend/src/lib/components/widgets/EditableDataTable.svelte`:

This is a complex widget. Key features:
- Props: `columns` (with `editable`, `type`, `options`), `rows`, `save_endpoint`, `save_method`, `title`
- Click cell → inline editor (text input, number input, select dropdown, date input)
- Dirty tracking via `Map<rowIndex, Map<colKey, newValue>>`
- "Save Changes" / "Cancel" buttons appear when dirty
- Save calls `save_endpoint` with modified rows via fetch
- Styling matches existing DataTable (Tailwind, surface colors, border tokens)

```svelte
<script lang="ts">
	interface Column {
		key: string;
		label: string;
		editable?: boolean;
		type?: 'text' | 'number' | 'select' | 'date';
		options?: string[];
	}

	interface EditableDataTableProps {
		columns: Column[];
		rows: Record<string, unknown>[];
		title?: string;
		save_endpoint?: string;
		save_method?: string;
	}

	let { columns, rows: initialRows, title, save_endpoint, save_method = 'PATCH' }: EditableDataTableProps = $props();

	let rows = $state(structuredClone(initialRows));
	let editingCell: { row: number; col: string } | null = $state(null);
	let editValue = $state('');
	let dirty = $state(new Set<number>());
	let saving = $state(false);
	let saveError = $state('');

	let isDirty = $derived(dirty.size > 0);

	function startEdit(rowIdx: number, col: Column) {
		if (!col.editable) return;
		editingCell = { row: rowIdx, col: col.key };
		editValue = String(rows[rowIdx][col.key] ?? '');
	}

	function commitEdit() {
		if (!editingCell) return;
		const { row, col } = editingCell;
		const colDef = columns.find((c) => c.key === col);
		let finalValue: unknown = editValue;
		if (colDef?.type === 'number') finalValue = Number(editValue);
		if (rows[row][col] !== finalValue) {
			rows[row] = { ...rows[row], [col]: finalValue };
			dirty = new Set([...dirty, row]);
		}
		editingCell = null;
	}

	function cancelEdit() {
		editingCell = null;
	}

	function cancelAll() {
		rows = structuredClone(initialRows);
		dirty = new Set();
		editingCell = null;
	}

	async function saveChanges() {
		if (!save_endpoint || !isDirty) return;
		saving = true;
		saveError = '';
		try {
			const modifiedRows = [...dirty].map((i) => rows[i]);
			const resp = await fetch(save_endpoint, {
				method: save_method,
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ rows: modifiedRows }),
			});
			if (!resp.ok) throw new Error(`Save failed: ${resp.statusText}`);
			dirty = new Set();
		} catch (e: any) {
			saveError = e.message || 'Save failed';
		} finally {
			saving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') commitEdit();
		if (e.key === 'Escape') cancelEdit();
	}
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	{#if title || isDirty}
		<div class="flex items-center justify-between border-b border-border px-4 py-2">
			{#if title}
				<h4 class="text-sm font-semibold text-text-primary">{title}</h4>
			{:else}
				<div></div>
			{/if}
			{#if isDirty}
				<div class="flex items-center gap-2">
					{#if saveError}
						<span class="text-xs text-danger">{saveError}</span>
					{/if}
					<button
						type="button"
						class="rounded px-2.5 py-1 text-xs text-text-secondary hover:bg-surface-secondary"
						onclick={cancelAll}
					>
						Cancel
					</button>
					{#if save_endpoint}
						<button
							type="button"
							class="rounded bg-accent px-2.5 py-1 text-xs font-medium text-white hover:bg-accent/90 disabled:opacity-50"
							onclick={saveChanges}
							disabled={saving}
						>
							{saving ? 'Saving...' : `Save ${dirty.size} change${dirty.size === 1 ? '' : 's'}`}
						</button>
					{/if}
				</div>
			{/if}
		</div>
	{/if}

	<div class="overflow-auto">
		<table class="w-full text-left text-xs">
			<thead>
				<tr class="border-b border-border bg-surface-secondary">
					{#each columns as col}
						<th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
							{col.label}
						</th>
					{/each}
				</tr>
			</thead>
			<tbody>
				{#each rows as row, rowIdx}
					<tr class="border-b border-border/50 {dirty.has(rowIdx) ? 'bg-accent/5' : rowIdx % 2 === 0 ? '' : 'bg-surface-secondary/50'}">
						{#each columns as col}
							<td
								class="px-3 py-1.5 {col.editable ? 'cursor-pointer hover:bg-accent/10' : ''}"
								onclick={() => startEdit(rowIdx, col)}
								onkeydown={() => {}}
								role={col.editable ? 'button' : undefined}
								tabindex={col.editable ? 0 : undefined}
							>
								{#if editingCell?.row === rowIdx && editingCell?.col === col.key}
									{#if col.type === 'select' && col.options}
										<select
											class="w-full rounded border border-accent bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none"
											bind:value={editValue}
											onblur={commitEdit}
											onkeydown={handleKeydown}
										>
											{#each col.options as opt}
												<option value={opt}>{opt}</option>
											{/each}
										</select>
									{:else}
										<input
											type={col.type === 'number' ? 'number' : col.type === 'date' ? 'date' : 'text'}
											class="w-full rounded border border-accent bg-surface px-1.5 py-0.5 text-xs text-text-primary outline-none"
											bind:value={editValue}
											onblur={commitEdit}
											onkeydown={handleKeydown}
										/>
									{/if}
								{:else}
									<span class="text-text-primary">{row[col.key] ?? ''}</span>
								{/if}
							</td>
						{/each}
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
</div>
```

2. Register in `frontend/src/lib/widgets/registry.ts`:
```typescript
import EditableDataTable from '$lib/components/widgets/EditableDataTable.svelte';

// In widgetRegistry:
'editable-table': EditableDataTable,
```

3. Run frontend check:
   ```bash
   cd frontend && npm run check
   ```

4. Commit:
   ```bash
   git add frontend/src/lib/components/widgets/EditableDataTable.svelte frontend/src/lib/widgets/registry.ts
   git commit -m "feat: add editable table widget with inline cell editing and save-back"
   ```

---

## Task 8: Paginated Table Widget (Frontend)

**Files:**
- Create: `frontend/src/lib/components/widgets/PaginatedTable.svelte`
- Modify: `frontend/src/lib/widgets/registry.ts`

**Steps:**

1. Create `frontend/src/lib/components/widgets/PaginatedTable.svelte`. Key features:
- Props: `columns`, `data_endpoint`, `page_size`, `total_count`, `title`
- Fetches pages from `data_endpoint?offset=N&limit=M`
- prev/next buttons, page indicator, rows-per-page selector
- Loading state, error handling
- Listens for custom `filter-change` events on `target_widget_id`

```svelte
<script lang="ts">
	interface Column {
		key: string;
		label: string;
	}

	interface PaginatedTableProps {
		columns: Column[];
		data_endpoint: string;
		page_size?: number;
		total_count?: number;
		title?: string;
		widget_id?: string;
	}

	let {
		columns,
		data_endpoint,
		page_size = 25,
		total_count = 0,
		title,
		widget_id
	}: PaginatedTableProps = $props();

	let rows: Record<string, unknown>[] = $state([]);
	let offset = $state(0);
	let loading = $state(false);
	let error = $state('');
	let totalRows = $state(total_count);
	let filterParams = $state('');

	let currentPage = $derived(Math.floor(offset / page_size) + 1);
	let totalPages = $derived(Math.max(1, Math.ceil(totalRows / page_size)));
	let hasPrev = $derived(offset > 0);
	let hasNext = $derived(offset + page_size < totalRows);

	$effect(() => {
		fetchPage();
	});

	$effect(() => {
		if (!widget_id) return;
		function handleFilter(e: CustomEvent) {
			if (e.detail?.targetId === widget_id) {
				filterParams = e.detail.queryString || '';
				offset = 0;
				fetchPage();
			}
		}
		window.addEventListener('widget-filter-change', handleFilter as EventListener);
		return () => window.removeEventListener('widget-filter-change', handleFilter as EventListener);
	});

	async function fetchPage() {
		loading = true;
		error = '';
		try {
			const sep = data_endpoint.includes('?') ? '&' : '?';
			const url = `${data_endpoint}${sep}offset=${offset}&limit=${page_size}${filterParams ? '&' + filterParams : ''}`;
			const resp = await fetch(url);
			if (!resp.ok) throw new Error(resp.statusText);
			const body = await resp.json();
			rows = body.rows ?? body.items ?? body.data ?? [];
			if (body.total != null) totalRows = body.total;
			if (body.total_count != null) totalRows = body.total_count;
		} catch (e: any) {
			error = e.message;
		} finally {
			loading = false;
		}
	}

	function prevPage() {
		offset = Math.max(0, offset - page_size);
		fetchPage();
	}

	function nextPage() {
		offset += page_size;
		fetchPage();
	}
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	{#if title}
		<div class="border-b border-border px-4 py-2">
			<h4 class="text-sm font-semibold text-text-primary">{title}</h4>
		</div>
	{/if}

	<div class="overflow-auto">
		{#if loading}
			<div class="flex items-center justify-center py-8">
				<div class="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent"></div>
			</div>
		{:else if error}
			<div class="px-4 py-8 text-center text-sm text-danger">{error}</div>
		{:else}
			<table class="w-full text-left text-xs">
				<thead>
					<tr class="border-b border-border bg-surface-secondary">
						{#each columns as col}
							<th class="px-3 py-2 text-xs font-semibold uppercase tracking-wider text-text-secondary">
								{col.label}
							</th>
						{/each}
					</tr>
				</thead>
				<tbody>
					{#each rows as row, i}
						<tr class="border-b border-border/50 {i % 2 === 0 ? '' : 'bg-surface-secondary/50'}">
							{#each columns as col}
								<td class="px-3 py-1.5 text-text-primary">{row[col.key] ?? ''}</td>
							{/each}
						</tr>
					{/each}
					{#if rows.length === 0}
						<tr>
							<td colspan={columns.length} class="px-4 py-8 text-center text-sm text-text-secondary">
								No data
							</td>
						</tr>
					{/if}
				</tbody>
			</table>
		{/if}
	</div>

	<!-- Pagination controls -->
	<div class="flex items-center justify-between border-t border-border px-4 py-2">
		<span class="text-xs text-text-secondary">
			{totalRows > 0 ? `${offset + 1}–${Math.min(offset + page_size, totalRows)} of ${totalRows}` : 'No results'}
		</span>
		<div class="flex items-center gap-2">
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-secondary disabled:opacity-30"
				disabled={!hasPrev}
				onclick={prevPage}
			>
				Previous
			</button>
			<span class="text-xs text-text-secondary">Page {currentPage} of {totalPages}</span>
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:bg-surface-secondary disabled:opacity-30"
				disabled={!hasNext}
				onclick={nextPage}
			>
				Next
			</button>
		</div>
	</div>
</div>
```

2. Register in `frontend/src/lib/widgets/registry.ts`:
```typescript
import PaginatedTable from '$lib/components/widgets/PaginatedTable.svelte';

// In widgetRegistry:
'paginated-table': PaginatedTable,
```

3. Run frontend check:
   ```bash
   cd frontend && npm run check
   ```

4. Commit:
   ```bash
   git add frontend/src/lib/components/widgets/PaginatedTable.svelte frontend/src/lib/widgets/registry.ts
   git commit -m "feat: add paginated table widget with server-side pagination"
   ```

---

## Task 9: Dynamic Filter Widget (Frontend)

**Files:**
- Create: `frontend/src/lib/components/widgets/DynamicFilter.svelte`
- Modify: `frontend/src/lib/widgets/registry.ts`

**Steps:**

1. Create `frontend/src/lib/components/widgets/DynamicFilter.svelte`:

```svelte
<script lang="ts">
	import { Search } from 'lucide-svelte';

	interface FilterField {
		field: string;
		label: string;
		type: 'text' | 'date_range' | 'select' | 'number_range';
		options?: string[];
	}

	interface DynamicFilterProps {
		filters: FilterField[];
		target_widget_id?: string;
		title?: string;
	}

	let { filters, target_widget_id, title }: DynamicFilterProps = $props();

	let values: Record<string, any> = $state({});

	function dispatchFilter() {
		const params = new URLSearchParams();
		for (const f of filters) {
			const val = values[f.field];
			if (f.type === 'date_range') {
				if (val?.from) params.set(`${f.field}_from`, val.from);
				if (val?.to) params.set(`${f.field}_to`, val.to);
			} else if (f.type === 'number_range') {
				if (val?.min != null && val.min !== '') params.set(`${f.field}_min`, String(val.min));
				if (val?.max != null && val.max !== '') params.set(`${f.field}_max`, String(val.max));
			} else if (val != null && val !== '') {
				params.set(f.field, String(val));
			}
		}
		window.dispatchEvent(
			new CustomEvent('widget-filter-change', {
				detail: { targetId: target_widget_id, queryString: params.toString() },
			})
		);
	}

	function clearAll() {
		values = {};
		dispatchFilter();
	}

	let hasValues = $derived(
		Object.values(values).some((v) => {
			if (v == null || v === '') return false;
			if (typeof v === 'object') return Object.values(v).some((sv) => sv != null && sv !== '');
			return true;
		})
	);
</script>

<div class="rounded-lg border border-border bg-surface p-3">
	{#if title}
		<h4 class="mb-2 text-xs font-semibold text-text-secondary uppercase tracking-wider">{title}</h4>
	{/if}

	<div class="flex flex-wrap items-end gap-3">
		{#each filters as f}
			<div class="flex flex-col gap-1">
				<label class="text-xs text-text-secondary" for="filter-{f.field}">{f.label}</label>

				{#if f.type === 'text'}
					<div class="relative">
						<Search size={12} class="absolute left-2 top-1/2 -translate-y-1/2 text-text-secondary" />
						<input
							id="filter-{f.field}"
							type="text"
							class="w-40 rounded border border-border bg-surface-secondary py-1 pl-7 pr-2 text-xs text-text-primary outline-none focus:border-accent"
							bind:value={values[f.field]}
							oninput={dispatchFilter}
							placeholder="Search..."
						/>
					</div>
				{:else if f.type === 'select' && f.options}
					<select
						id="filter-{f.field}"
						class="w-36 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
						bind:value={values[f.field]}
						onchange={dispatchFilter}
					>
						<option value="">All</option>
						{#each f.options as opt}
							<option value={opt}>{opt}</option>
						{/each}
					</select>
				{:else if f.type === 'date_range'}
					<div class="flex items-center gap-1">
						<input
							type="date"
							class="w-32 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							bind:value={values[f.field] && values[f.field].from}
							oninput={(e) => {
								values[f.field] = { ...values[f.field], from: e.currentTarget.value };
								dispatchFilter();
							}}
						/>
						<span class="text-xs text-text-secondary">–</span>
						<input
							type="date"
							class="w-32 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							bind:value={values[f.field] && values[f.field].to}
							oninput={(e) => {
								values[f.field] = { ...values[f.field], to: e.currentTarget.value };
								dispatchFilter();
							}}
						/>
					</div>
				{:else if f.type === 'number_range'}
					<div class="flex items-center gap-1">
						<input
							type="number"
							class="w-20 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Min"
							bind:value={values[f.field] && values[f.field].min}
							oninput={(e) => {
								values[f.field] = { ...values[f.field], min: e.currentTarget.value };
								dispatchFilter();
							}}
						/>
						<span class="text-xs text-text-secondary">–</span>
						<input
							type="number"
							class="w-20 rounded border border-border bg-surface-secondary px-2 py-1 text-xs text-text-primary outline-none focus:border-accent"
							placeholder="Max"
							bind:value={values[f.field] && values[f.field].max}
							oninput={(e) => {
								values[f.field] = { ...values[f.field], max: e.currentTarget.value };
								dispatchFilter();
							}}
						/>
					</div>
				{/if}
			</div>
		{/each}

		{#if hasValues}
			<button
				type="button"
				class="rounded px-2 py-1 text-xs text-text-secondary hover:text-text-primary hover:bg-surface-secondary"
				onclick={clearAll}
			>
				Clear
			</button>
		{/if}
	</div>
</div>
```

2. Register in `frontend/src/lib/widgets/registry.ts`:
```typescript
import DynamicFilter from '$lib/components/widgets/DynamicFilter.svelte';

// In widgetRegistry:
'dynamic-filter': DynamicFilter,
```

3. Run frontend check:
   ```bash
   cd frontend && npm run check
   ```

4. Commit:
   ```bash
   git add frontend/src/lib/components/widgets/DynamicFilter.svelte frontend/src/lib/widgets/registry.ts
   git commit -m "feat: add dynamic filter widget with text, select, date range, and number range"
   ```

---

## Task 10: 360° Entity View Widget (Frontend)

**Files:**
- Create: `frontend/src/lib/components/widgets/EntityView.svelte`
- Modify: `frontend/src/lib/widgets/registry.ts`

**Steps:**

1. Create `frontend/src/lib/components/widgets/EntityView.svelte`:

```svelte
<script lang="ts">
	import { TrendingUp, TrendingDown, Minus, Clock, Link, Table } from 'lucide-svelte';

	interface HeaderData {
		title: string;
		subtitle?: string;
		avatar_url?: string;
		status?: string;
		status_color?: 'success' | 'warning' | 'danger' | 'default';
	}

	interface DetailsItem {
		label: string;
		value: string;
		icon?: string;
	}

	interface MetricItem {
		label: string;
		value: string;
		trend?: 'up' | 'down' | 'stable';
		change?: string;
	}

	interface TimelineEvent {
		date: string;
		title: string;
		description?: string;
	}

	interface RelatedItem {
		name: string;
		type?: string;
		description?: string;
	}

	interface TableSection {
		columns: { key: string; label: string }[];
		rows: Record<string, unknown>[];
	}

	interface Section {
		type: 'details' | 'metrics' | 'timeline' | 'related' | 'table';
		title: string;
		items?: (DetailsItem | MetricItem | TimelineEvent | RelatedItem)[];
		columns?: { key: string; label: string }[];
		rows?: Record<string, unknown>[];
		events?: TimelineEvent[];
	}

	interface EntityViewProps {
		header: HeaderData;
		sections: Section[];
	}

	let { header, sections }: EntityViewProps = $props();

	let activeTab = $state(0);

	const statusColorMap: Record<string, string> = {
		success: 'bg-success text-white',
		warning: 'bg-warning text-white',
		danger: 'bg-danger text-white',
		default: 'bg-surface-secondary text-text-secondary',
	};
</script>

<div class="overflow-hidden rounded-lg border border-border bg-surface">
	<!-- Header -->
	<div class="border-b border-border bg-surface-secondary/50 px-5 py-4">
		<div class="flex items-center gap-4">
			{#if header.avatar_url}
				<img
					src={header.avatar_url}
					alt={header.title}
					class="h-12 w-12 rounded-full object-cover border border-border"
				/>
			{:else}
				<div class="flex h-12 w-12 items-center justify-center rounded-full bg-accent/10 text-accent text-lg font-bold">
					{header.title.charAt(0).toUpperCase()}
				</div>
			{/if}
			<div class="flex-1 min-w-0">
				<h3 class="text-base font-semibold text-text-primary truncate">{header.title}</h3>
				{#if header.subtitle}
					<p class="text-sm text-text-secondary">{header.subtitle}</p>
				{/if}
			</div>
			{#if header.status}
				<span class="rounded-full px-2.5 py-0.5 text-xs font-medium {statusColorMap[header.status_color ?? 'default']}">
					{header.status}
				</span>
			{/if}
		</div>
	</div>

	<!-- Section tabs -->
	{#if sections.length > 1}
		<div class="flex border-b border-border overflow-x-auto">
			{#each sections as section, i}
				<button
					type="button"
					class="shrink-0 px-4 py-2 text-xs font-medium transition-colors {activeTab === i
						? 'border-b-2 border-accent text-accent'
						: 'text-text-secondary hover:text-text-primary'}"
					onclick={() => (activeTab = i)}
				>
					{section.title}
				</button>
			{/each}
		</div>
	{/if}

	<!-- Active section content -->
	{#if sections[activeTab]}
		{@const section = sections[activeTab]}
		<div class="p-4">
			{#if sections.length === 1}
				<h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-text-secondary">{section.title}</h4>
			{/if}

			{#if section.type === 'details' && section.items}
				<div class="grid grid-cols-2 gap-3">
					{#each section.items as item}
						<div class="flex flex-col">
							<span class="text-xs text-text-secondary">{item.label}</span>
							<span class="text-sm font-medium text-text-primary">{item.value}</span>
						</div>
					{/each}
				</div>
			{:else if section.type === 'metrics' && section.items}
				<div class="grid grid-cols-2 gap-3 sm:grid-cols-3">
					{#each section.items as item}
						<div class="rounded-lg border border-border bg-surface-secondary/50 p-3">
							<span class="text-xs text-text-secondary">{item.label}</span>
							<div class="mt-1 flex items-baseline gap-2">
								<span class="text-lg font-bold text-text-primary">{item.value}</span>
								{#if item.trend === 'up'}
									<span class="flex items-center gap-0.5 text-xs text-success">
										<TrendingUp size={12} />{item.change ?? ''}
									</span>
								{:else if item.trend === 'down'}
									<span class="flex items-center gap-0.5 text-xs text-danger">
										<TrendingDown size={12} />{item.change ?? ''}
									</span>
								{:else if item.trend === 'stable'}
									<span class="flex items-center gap-0.5 text-xs text-text-secondary">
										<Minus size={12} />{item.change ?? ''}
									</span>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'timeline' && (section.events || section.items)}
				{@const events = section.events || section.items || []}
				<div class="space-y-3">
					{#each events as event}
						<div class="flex gap-3">
							<div class="flex flex-col items-center">
								<div class="h-2 w-2 rounded-full bg-accent mt-1.5"></div>
								<div class="w-px flex-1 bg-border"></div>
							</div>
							<div class="pb-3">
								<div class="flex items-baseline gap-2">
									<span class="text-sm font-medium text-text-primary">{event.title}</span>
									<span class="text-xs text-text-secondary">{event.date}</span>
								</div>
								{#if event.description}
									<p class="mt-0.5 text-xs text-text-secondary">{event.description}</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'related' && section.items}
				<div class="space-y-2">
					{#each section.items as item}
						<div class="flex items-center gap-3 rounded-lg border border-border p-2.5">
							<div class="flex h-8 w-8 items-center justify-center rounded-full bg-accent/10 text-accent text-xs font-bold">
								{item.name.charAt(0).toUpperCase()}
							</div>
							<div class="flex-1 min-w-0">
								<span class="text-sm font-medium text-text-primary">{item.name}</span>
								{#if item.type}
									<span class="ml-1.5 text-xs text-text-secondary">· {item.type}</span>
								{/if}
								{#if item.description}
									<p class="text-xs text-text-secondary truncate">{item.description}</p>
								{/if}
							</div>
						</div>
					{/each}
				</div>
			{:else if section.type === 'table' && section.columns && section.rows}
				<div class="overflow-auto">
					<table class="w-full text-left text-xs">
						<thead>
							<tr class="border-b border-border">
								{#each section.columns as col}
									<th class="px-3 py-2 font-semibold text-text-secondary">{col.label}</th>
								{/each}
							</tr>
						</thead>
						<tbody>
							{#each section.rows as row, i}
								<tr class="border-b border-border/50 {i % 2 === 0 ? '' : 'bg-surface-secondary/50'}">
									{#each section.columns as col}
										<td class="px-3 py-1.5 text-text-primary">{row[col.key] ?? ''}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/if}
		</div>
	{/if}
</div>
```

2. Register in `frontend/src/lib/widgets/registry.ts`:
```typescript
import EntityView from '$lib/components/widgets/EntityView.svelte';

// In widgetRegistry:
'entity-view': EntityView,
```

3. Run frontend check:
   ```bash
   cd frontend && npm run check
   ```

4. Commit:
   ```bash
   git add frontend/src/lib/components/widgets/EntityView.svelte frontend/src/lib/widgets/registry.ts
   git commit -m "feat: add 360° entity view widget with details, metrics, timeline, related, table sections"
   ```

---

## Task 11: Wire Document Tool Executor in Server Lifespan

**Problem:** DocumentToolExecutor needs storage access, must be wired in server startup.

**Files:**
- Modify: `src/flydesk/server.py` — Wire DocumentToolExecutor into BuiltinToolExecutor during lifespan

**Steps:**

1. In `src/flydesk/server.py`, find the lifespan function where `BuiltinToolExecutor` is created. Add:

```python
from flydesk.tools.document_tools import DocumentToolExecutor

# After creating file_storage and builtin_executor:
doc_executor = DocumentToolExecutor(file_storage)
builtin_executor.set_document_executor(doc_executor)
```

2. Similarly, wire `file_storage` into DeskAgent constructor:

```python
# When creating DeskAgent, add file_storage parameter:
desk_agent = DeskAgent(
    ...,
    file_storage=file_storage,
)
```

3. Run the test suite:
   ```bash
   uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py --ignore=tests/knowledge/test_pinecone_store.py
   ```

4. Commit:
   ```bash
   git add src/flydesk/server.py
   git commit -m "feat: wire document tool executor and file storage into server lifespan"
   ```

---

## Task 12: Integration Verification

**Steps:**

1. Backend tests:
   ```bash
   uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py --ignore=tests/knowledge/test_pinecone_store.py
   ```

2. Frontend checks:
   ```bash
   cd frontend && npm run check && npm run build
   ```

3. Verify widget registry has all 25 widgets (20 original + 5 new):
   ```bash
   grep -c "'" frontend/src/lib/widgets/registry.ts  # Should show ~25 entries
   ```

4. Verify built-in tools now include document + transform tools:
   ```bash
   uv run python -c "
   from flydesk.tools.builtin import BuiltinToolRegistry
   tools = BuiltinToolRegistry.get_tool_definitions(['*'])
   print(f'Total built-in tools: {len(tools)}')
   for t in tools:
       print(f'  - {t.name}')
   "
   ```
   Expected: 14 tools (6 original + 4 document + 4 transform)

5. Commit any remaining fixes.

---

## Dependency Graph

```
T0  (Dependencies)              — No deps
T1  (Content extractor)         — Depends on T0
T2  (File render endpoint)      — Depends on T1
T3  (Multimodal wiring)         — Depends on T1
T4  (Document tools)            — Depends on T0
T5  (Transform tools)           — No deps
T6  (File viewer widget FE)     — Depends on T2
T7  (Editable table widget FE)  — No deps
T8  (Paginated table widget FE) — No deps
T9  (Dynamic filter widget FE)  — No deps
T10 (Entity view widget FE)     — No deps
T11 (Server wiring)             — Depends on T3, T4
T12 (Verification)              — ALL previous tasks
```

**Execution order:**
1. T0 (dependencies)
2. T1, T5 (parallel — content extractor, transform tools)
3. T2, T3, T4, T7, T8, T9, T10 (parallel — independent after T0/T1)
4. T6 (needs T2)
5. T11 (needs T3, T4)
6. T12 (final)

---

## Summary Table

| # | Task | Key Files | Priority |
|---|------|-----------|----------|
| 0 | Document processing dependencies | `pyproject.toml` | P0 |
| 1 | Enhanced content extractor | `files/extractor.py` | P0 |
| 2 | File render API endpoint | `api/files.py` | P0 |
| 3 | Multimodal agent wiring | `agent/desk_agent.py` | P0 |
| 4 | Document tools (read/create/modify/convert) | `tools/document_tools.py` | P0 |
| 5 | Result transformation tools | `tools/transform_tools.py` | P0 |
| 6 | File viewer widget (FE) | `FileViewer.svelte`, `FileViewerModal.svelte` | P1 |
| 7 | Editable table widget (FE) | `EditableDataTable.svelte` | P1 |
| 8 | Paginated table widget (FE) | `PaginatedTable.svelte` | P1 |
| 9 | Dynamic filter widget (FE) | `DynamicFilter.svelte` | P1 |
| 10 | 360° entity view widget (FE) | `EntityView.svelte` | P1 |
| 11 | Server wiring | `server.py` | P1 |
| 12 | Integration verification | — | Final |
