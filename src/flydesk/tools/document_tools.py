# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Document tools for reading, creating, modifying, and converting office documents.

These tools let the agent work with PDF, DOCX, XLSX, and PPTX files
stored in the platform's file storage backend.
"""

from __future__ import annotations

import csv
import io
import json
import logging
from typing import TYPE_CHECKING, Any

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.tools.builtin import BUILTIN_SYSTEM_ID
from flydesk.tools.factory import ToolDefinition

if TYPE_CHECKING:
    from flydesk.files.storage import FileStorageProvider

logger = logging.getLogger(__name__)


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Coerce *value* to a dict.

    LLMs sometimes send JSON-object parameters as a serialised string rather
    than an actual dict.  This helper transparently handles both cases.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def document_read_tool() -> ToolDefinition:
    """Tool definition for reading document content."""
    return ToolDefinition(
        endpoint_id="__builtin__document_read",
        name="document_read",
        description=(
            "Extract text, tables, and metadata from a document file "
            "(PDF, DOCX, XLSX, PPTX). Returns the textual content of the document. "
            "Use when: the user asks to read, view, or extract information from "
            "an uploaded document."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/documents/read",
        parameters={
            "file_path": {
                "type": "string",
                "description": "Storage path of the document to read",
                "required": True,
            },
        },
    )


def document_create_tool() -> ToolDefinition:
    """Tool definition for creating new documents."""
    return ToolDefinition(
        endpoint_id="__builtin__document_create",
        name="document_create",
        description=(
            "Generate a new document file (DOCX, XLSX, or PDF). "
            "Provide a format and content structure. "
            "Use when: the user asks to create a new report, spreadsheet, "
            "or document from scratch."
        ),
        risk_level=RiskLevel.LOW_WRITE,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/create",
        parameters={
            "format": {
                "type": "string",
                "description": "Output format: docx, xlsx, or pdf",
                "required": True,
            },
            "title": {
                "type": "string",
                "description": "Document title",
                "required": True,
            },
            "content": {
                "type": "object",
                "description": (
                    "Document content. For docx: {paragraphs: [str]}. "
                    "For xlsx: {sheets: [{name: str, rows: [[value]]}]}. "
                    "For pdf: {paragraphs: [str]}."
                ),
                "required": True,
            },
        },
    )


def document_modify_tool() -> ToolDefinition:
    """Tool definition for modifying existing documents."""
    return ToolDefinition(
        endpoint_id="__builtin__document_modify",
        name="document_modify",
        description=(
            "Edit an existing document: append paragraphs, replace text, "
            "update spreadsheet cells, or merge PDFs. "
            "Use when: the user asks to edit, update, or merge documents."
        ),
        risk_level=RiskLevel.LOW_WRITE,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/modify",
        parameters={
            "file_path": {
                "type": "string",
                "description": "Storage path of the document to modify",
                "required": True,
            },
            "operation": {
                "type": "string",
                "description": "Operation: append, replace, update_cells, or merge",
                "required": True,
            },
            "data": {
                "type": "object",
                "description": (
                    "Operation data. append: {paragraphs: [str]}. "
                    "replace: {old_text: str, new_text: str}. "
                    "update_cells: {updates: [{sheet: str, cell: str, value: any}]}. "
                    "merge: {file_paths: [str]}."
                ),
                "required": True,
            },
        },
    )


def document_convert_tool() -> ToolDefinition:
    """Tool definition for converting documents between formats."""
    return ToolDefinition(
        endpoint_id="__builtin__document_convert",
        name="document_convert",
        description=(
            "Convert a document between formats: XLSX to CSV, DOCX to plain text. "
            "Use when: the user needs a document in a different format."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.POST.value,
        path="/__builtin__/documents/convert",
        parameters={
            "file_path": {
                "type": "string",
                "description": "Storage path of the source document",
                "required": True,
            },
            "target_format": {
                "type": "string",
                "description": "Target format: csv or text",
                "required": True,
            },
        },
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class DocumentToolExecutor:
    """Execute document tools against the file storage backend.

    Each handler lazily imports the required document library so that
    the dependency is only loaded when the tool is actually invoked.
    """

    _TOOL_NAMES = frozenset({
        "document_read",
        "document_create",
        "document_modify",
        "document_convert",
    })

    def __init__(self, storage: FileStorageProvider) -> None:
        self._storage = storage

    @classmethod
    def is_document_tool(cls, tool_name: str) -> bool:
        """Return True if *tool_name* is handled by this executor."""
        return tool_name in cls._TOOL_NAMES

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to the appropriate document handler."""
        handlers: dict[str, Any] = {
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

    # ---- Read ----

    async def _read(self, arguments: dict[str, Any]) -> dict[str, Any]:
        file_path: str = arguments.get("file_path", "")
        if not file_path:
            return {"error": "file_path is required"}

        data = await self._storage.retrieve(file_path)
        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

        if ext == "pdf":
            return self._read_pdf(data)
        if ext == "docx":
            return self._read_docx(data)
        if ext == "xlsx":
            return self._read_xlsx(data)
        if ext == "pptx":
            return self._read_pptx(data)
        return {"error": f"Unsupported file format: .{ext}"}

    @staticmethod
    def _read_pdf(data: bytes) -> dict[str, Any]:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return {
            "format": "pdf",
            "page_count": len(pages),
            "text": "\n\n".join(pages),
        }

    @staticmethod
    def _read_docx(data: bytes) -> dict[str, Any]:
        from docx import Document

        doc = Document(io.BytesIO(data))
        paragraphs = [p.text for p in doc.paragraphs]
        tables: list[list[list[str]]] = []
        for table in doc.tables:
            rows = []
            for row in table.rows:
                rows.append([cell.text for cell in row.cells])
            tables.append(rows)
        return {
            "format": "docx",
            "paragraphs": paragraphs,
            "tables": tables,
        }

    @staticmethod
    def _read_xlsx(data: bytes) -> dict[str, Any]:
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        sheets: dict[str, list[list[Any]]] = {}
        for name in wb.sheetnames:
            ws = wb[name]
            rows: list[list[Any]] = []
            for row in ws.iter_rows(values_only=True):
                rows.append([cell for cell in row])
            sheets[name] = rows
        wb.close()
        return {"format": "xlsx", "sheets": sheets}

    @staticmethod
    def _read_pptx(data: bytes) -> dict[str, Any]:
        from pptx import Presentation

        prs = Presentation(io.BytesIO(data))
        slides: list[dict[str, Any]] = []
        for slide in prs.slides:
            texts: list[str] = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    texts.append(shape.text_frame.text)
            slides.append({"texts": texts})
        return {"format": "pptx", "slide_count": len(slides), "slides": slides}

    # ---- Create ----

    async def _create(self, arguments: dict[str, Any]) -> dict[str, Any]:
        fmt: str = arguments.get("format", "")
        title: str = arguments.get("title", "")
        content: dict[str, Any] = _coerce_dict(arguments.get("content", {}))

        if not fmt:
            return {"error": "format is required"}
        if not title:
            return {"error": "title is required"}

        if fmt == "docx":
            return await self._create_docx(title, content)
        if fmt == "xlsx":
            return await self._create_xlsx(title, content)
        if fmt == "pptx":
            return await self._create_pptx(title, content)
        if fmt == "pdf":
            return await self._create_pdf(title, content)
        return {"error": f"Unsupported create format: {fmt}"}

    async def _create_docx(self, title: str, content: dict[str, Any]) -> dict[str, Any]:
        from docx import Document

        doc = Document()
        doc.add_heading(title, level=0)
        for para in content.get("paragraphs", []):
            doc.add_paragraph(str(para))

        buf = io.BytesIO()
        doc.save(buf)
        filename = f"{title}.docx"
        path = await self._storage.store(filename, buf.getvalue(), _CONTENT_TYPES["docx"])
        return {"format": "docx", "file_path": path, "filename": filename}

    async def _create_xlsx(self, title: str, content: dict[str, Any]) -> dict[str, Any]:
        from openpyxl import Workbook

        wb = Workbook()
        # Remove the default sheet so we start clean
        wb.remove(wb.active)  # type: ignore[arg-type]

        sheets_data = content.get("sheets", [])
        if not sheets_data:
            # Fallback: create a single sheet named after the title
            ws = wb.create_sheet(title=title)
            for row_data in content.get("rows", []):
                ws.append(row_data)
        else:
            for sheet_info in sheets_data:
                ws = wb.create_sheet(title=sheet_info.get("name", "Sheet"))
                for row_data in sheet_info.get("rows", []):
                    ws.append(row_data)

        buf = io.BytesIO()
        wb.save(buf)
        filename = f"{title}.xlsx"
        path = await self._storage.store(filename, buf.getvalue(), _CONTENT_TYPES["xlsx"])
        return {"format": "xlsx", "file_path": path, "filename": filename}

    async def _create_pdf(self, title: str, content: dict[str, Any]) -> dict[str, Any]:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter)
        styles = getSampleStyleSheet()

        story: list[Any] = []
        story.append(Paragraph(title, styles["Title"]))
        story.append(Spacer(1, 12))
        for para in content.get("paragraphs", []):
            story.append(Paragraph(str(para), styles["BodyText"]))
            story.append(Spacer(1, 6))

        doc.build(story)
        filename = f"{title}.pdf"
        path = await self._storage.store(filename, buf.getvalue(), _CONTENT_TYPES["pdf"])
        return {"format": "pdf", "file_path": path, "filename": filename}

    async def _create_pptx(self, title: str, content: dict[str, Any]) -> dict[str, Any]:
        from pptx import Presentation
        from pptx.util import Inches

        prs = Presentation()

        # Title slide
        title_layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(title_layout)
        slide.shapes.title.text = title
        if slide.placeholders[1]:
            slide.placeholders[1].text = content.get("subtitle", "")

        # Content slides
        body_layout = prs.slide_layouts[1]
        for slide_data in content.get("slides", []):
            s = prs.slides.add_slide(body_layout)
            s.shapes.title.text = slide_data.get("title", "")
            body = s.placeholders[1]
            tf = body.text_frame
            for i, bullet in enumerate(slide_data.get("bullets", [])):
                if i == 0:
                    tf.text = str(bullet)
                else:
                    tf.add_paragraph().text = str(bullet)

        buf = io.BytesIO()
        prs.save(buf)
        filename = f"{title}.pptx"
        path = await self._storage.store(filename, buf.getvalue(), _CONTENT_TYPES["pptx"])
        return {"format": "pptx", "file_path": path, "filename": filename}

    # ---- Modify ----

    async def _modify(self, arguments: dict[str, Any]) -> dict[str, Any]:
        file_path: str = arguments.get("file_path", "")
        operation: str = arguments.get("operation", "")
        data: dict[str, Any] = _coerce_dict(arguments.get("data", {}))

        if not file_path:
            return {"error": "file_path is required"}
        if not operation:
            return {"error": "operation is required"}

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

        if operation == "append" and ext == "docx":
            return await self._modify_docx_append(file_path, data)
        if operation == "replace" and ext == "docx":
            return await self._modify_docx_replace(file_path, data)
        if operation == "update_cells" and ext == "xlsx":
            return await self._modify_xlsx_update_cells(file_path, data)
        if operation == "merge" and ext == "pdf":
            return await self._modify_pdf_merge(file_path, data)

        return {"error": f"Unsupported operation '{operation}' for .{ext} files"}

    async def _modify_docx_append(
        self, file_path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        from docx import Document

        raw = await self._storage.retrieve(file_path)
        doc = Document(io.BytesIO(raw))
        for para in data.get("paragraphs", []):
            doc.add_paragraph(str(para))

        buf = io.BytesIO()
        doc.save(buf)
        new_path = await self._storage.store(
            file_path.rsplit("/", 1)[-1], buf.getvalue(), _CONTENT_TYPES["docx"]
        )
        return {"file_path": new_path, "operation": "append", "status": "ok"}

    async def _modify_docx_replace(
        self, file_path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        from docx import Document

        old_text: str = data.get("old_text", "")
        new_text: str = data.get("new_text", "")
        if not old_text:
            return {"error": "old_text is required for replace operation"}

        raw = await self._storage.retrieve(file_path)
        doc = Document(io.BytesIO(raw))

        count = 0
        for para in doc.paragraphs:
            if old_text in para.text:
                for run in para.runs:
                    if old_text in run.text:
                        run.text = run.text.replace(old_text, new_text)
                        count += 1

        buf = io.BytesIO()
        doc.save(buf)
        new_path = await self._storage.store(
            file_path.rsplit("/", 1)[-1], buf.getvalue(), _CONTENT_TYPES["docx"]
        )
        return {
            "file_path": new_path,
            "operation": "replace",
            "replacements": count,
            "status": "ok",
        }

    async def _modify_xlsx_update_cells(
        self, file_path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        from openpyxl import load_workbook

        raw = await self._storage.retrieve(file_path)
        wb = load_workbook(io.BytesIO(raw))

        updates = data.get("updates", [])
        for upd in updates:
            sheet_name = upd.get("sheet", wb.sheetnames[0])
            cell = upd.get("cell", "A1")
            value = upd.get("value")
            ws = wb[sheet_name]
            ws[cell] = value

        buf = io.BytesIO()
        wb.save(buf)
        wb.close()
        new_path = await self._storage.store(
            file_path.rsplit("/", 1)[-1], buf.getvalue(), _CONTENT_TYPES["xlsx"]
        )
        return {
            "file_path": new_path,
            "operation": "update_cells",
            "updates_applied": len(updates),
            "status": "ok",
        }

    async def _modify_pdf_merge(
        self, file_path: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        from PyPDF2 import PdfMerger

        merger = PdfMerger()
        # Append the primary file first
        primary = await self._storage.retrieve(file_path)
        merger.append(io.BytesIO(primary))

        extra_paths: list[str] = data.get("file_paths", [])
        for extra_path in extra_paths:
            extra_data = await self._storage.retrieve(extra_path)
            merger.append(io.BytesIO(extra_data))

        buf = io.BytesIO()
        merger.write(buf)
        merger.close()

        new_path = await self._storage.store(
            file_path.rsplit("/", 1)[-1], buf.getvalue(), _CONTENT_TYPES["pdf"]
        )
        return {
            "file_path": new_path,
            "operation": "merge",
            "merged_count": 1 + len(extra_paths),
            "status": "ok",
        }

    # ---- Convert ----

    async def _convert(self, arguments: dict[str, Any]) -> dict[str, Any]:
        file_path: str = arguments.get("file_path", "")
        target_format: str = arguments.get("target_format", "")

        if not file_path:
            return {"error": "file_path is required"}
        if not target_format:
            return {"error": "target_format is required"}

        ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

        if ext == "xlsx" and target_format == "csv":
            return await self._convert_xlsx_to_csv(file_path)
        if ext == "docx" and target_format == "text":
            return await self._convert_docx_to_text(file_path)

        return {"error": f"Unsupported conversion: .{ext} -> {target_format}"}

    async def _convert_xlsx_to_csv(self, file_path: str) -> dict[str, Any]:
        from openpyxl import load_workbook

        raw = await self._storage.retrieve(file_path)
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]

        buf = io.StringIO()
        writer = csv.writer(buf)
        for row in ws.iter_rows(values_only=True):
            writer.writerow([cell if cell is not None else "" for cell in row])
        wb.close()

        csv_bytes = buf.getvalue().encode("utf-8")
        base_name = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        filename = f"{base_name}.csv"
        new_path = await self._storage.store(filename, csv_bytes, "text/csv")
        return {"file_path": new_path, "target_format": "csv", "filename": filename}

    async def _convert_docx_to_text(self, file_path: str) -> dict[str, Any]:
        from docx import Document

        raw = await self._storage.retrieve(file_path)
        doc = Document(io.BytesIO(raw))
        text = "\n".join(p.text for p in doc.paragraphs)

        text_bytes = text.encode("utf-8")
        base_name = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        filename = f"{base_name}.txt"
        new_path = await self._storage.store(filename, text_bytes, "text/plain")
        return {"file_path": new_path, "target_format": "text", "filename": filename}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CONTENT_TYPES: dict[str, str] = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}
