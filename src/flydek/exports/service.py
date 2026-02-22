# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Export service -- generates CSV, JSON and PDF exports."""

from __future__ import annotations

import csv
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from html import escape
from typing import Any

from flydek.exports.models import (
    ExportFormat,
    ExportRecord,
    ExportStatus,
    ExportTemplate,
)
from flydek.exports.repository import ExportRepository
from flydek.files.storage import FileStorageProvider

logger = logging.getLogger(__name__)

# Try importing weasyprint for real PDF generation; fall back to HTML.
try:
    from weasyprint import HTML as WeasyprintHTML  # type: ignore[import-untyped]

    _HAS_WEASYPRINT = True
except ImportError:
    _HAS_WEASYPRINT = False


class ExportService:
    """Orchestrates export generation, storage and record-keeping."""

    def __init__(
        self,
        repo: ExportRepository,
        storage: FileStorageProvider,
    ) -> None:
        self._repo = repo
        self._storage = storage

    # ------------------------------------------------------------------
    # Public generators
    # ------------------------------------------------------------------

    def generate_csv(
        self,
        source_data: dict[str, Any],
        template: ExportTemplate | None = None,
    ) -> tuple[bytes, int]:
        """Generate CSV bytes from *source_data*.

        Returns ``(file_bytes, row_count)``.

        Supports the data-table widget format::

            {"columns": ["col1", "col2"], "rows": [["a", "b"], ...]}

        If a *template* with ``column_mapping`` is provided the headers and
        values are remapped accordingly.
        """
        columns, rows = self._normalize_data(source_data, template)

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        return buf.getvalue().encode("utf-8"), len(rows)

    def generate_json(
        self,
        source_data: dict[str, Any],
        template: ExportTemplate | None = None,
    ) -> tuple[bytes, int]:
        """Generate pretty-printed JSON bytes from *source_data*.

        Returns ``(file_bytes, row_count)``.

        If a *template* with ``column_mapping`` is provided the output keys
        are filtered/renamed.
        """
        columns, rows = self._normalize_data(source_data, template)

        # If normalize returned nothing useful, try list-of-dicts or fallback
        if not columns and not rows:
            content = json.dumps(source_data, indent=2, default=str).encode("utf-8")
            return content, 0

        # Convert tabular data to list-of-dicts with final column names
        items = [dict(zip(columns, row)) for row in rows]

        content = json.dumps(items, indent=2, default=str).encode("utf-8")
        return content, len(items)

    def generate_pdf(
        self,
        source_data: dict[str, Any],
        template: ExportTemplate | None = None,
    ) -> tuple[bytes, int, str]:
        """Generate a PDF (or HTML fallback) from *source_data*.

        Returns ``(file_bytes, row_count, actual_format)`` where
        *actual_format* is ``"pdf"`` when weasyprint is available, otherwise
        ``"html"``.
        """
        columns, rows = self._normalize_data(source_data, template)

        header_text = (template.header_text if template else None) or "Export"
        footer_text = (template.footer_text if template else None) or ""

        html = self._build_html_table(columns, rows, header_text, footer_text)

        if _HAS_WEASYPRINT:
            pdf_bytes: bytes = WeasyprintHTML(string=html).write_pdf()
            return pdf_bytes, len(rows), "pdf"

        return html.encode("utf-8"), len(rows), "html"

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def create_export(
        self,
        user_id: str,
        fmt: ExportFormat,
        source_data: dict[str, Any],
        title: str,
        template_id: str | None = None,
    ) -> ExportRecord:
        """Full export lifecycle: create record, generate, store, update.

        On failure the record is updated with ``status=FAILED`` and the error
        message is persisted.
        """
        export_id = str(uuid.uuid4())

        record = ExportRecord(
            id=export_id,
            user_id=user_id,
            format=fmt,
            template_id=template_id,
            title=title,
            status=ExportStatus.PENDING,
            source_data=source_data,
        )
        await self._repo.create_export(record)

        # Transition to GENERATING
        record.status = ExportStatus.GENERATING
        await self._repo.update_export(record)

        try:
            # Resolve template if provided
            template: ExportTemplate | None = None
            if template_id:
                template = await self._repo.get_template(template_id)

            # Generate file bytes
            file_bytes: bytes
            row_count: int
            content_type: str
            filename: str
            actual_format = fmt.value

            if fmt == ExportFormat.CSV:
                file_bytes, row_count = self.generate_csv(source_data, template)
                content_type = "text/csv"
                filename = f"{export_id}.csv"
            elif fmt == ExportFormat.JSON:
                file_bytes, row_count = self.generate_json(source_data, template)
                content_type = "application/json"
                filename = f"{export_id}.json"
            else:
                # PDF
                file_bytes, row_count, actual_format = self.generate_pdf(
                    source_data, template
                )
                if actual_format == "html":
                    content_type = "text/html"
                    filename = f"{export_id}.html"
                else:
                    content_type = "application/pdf"
                    filename = f"{export_id}.pdf"

            # Store via FileStorageProvider
            file_path = await self._storage.store(filename, file_bytes, content_type)

            # Update record with results
            record.status = ExportStatus.COMPLETED
            record.file_path = file_path
            record.file_size = len(file_bytes)
            record.row_count = row_count
            record.completed_at = datetime.now(timezone.utc)

            # If PDF fell back to HTML, note it in the format but keep as
            # ExportFormat.PDF (the download handler will set content-type
            # based on the actual file extension).

            await self._repo.update_export(record)

        except Exception:
            logger.exception("Export %s failed", export_id)
            record.status = ExportStatus.FAILED
            record.error = "Export generation failed"
            record.completed_at = datetime.now(timezone.utc)
            await self._repo.update_export(record)

        return record

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_data(
        source_data: dict[str, Any],
        template: ExportTemplate | None,
    ) -> tuple[list[str], list[list[Any]]]:
        """Extract columns and rows from *source_data*, applying template mapping.

        Supports two input shapes:

        * **Table format**: ``{"columns": [...], "rows": [[...], ...]}``
        * **List-of-dicts**: ``{"items": [{...}, ...]}``

        If a *template* with ``column_mapping`` is supplied, columns are
        filtered and renamed accordingly.
        """
        columns: list[str] = source_data.get("columns", [])
        rows: list[list[Any]] = source_data.get("rows", [])

        # If no columns/rows structure, treat as list-of-dicts
        if not columns and not rows:
            items = source_data.get("items", [])
            if items and isinstance(items[0], dict):
                columns = list(items[0].keys())
                rows = [list(item.get(c, "") for c in columns) for item in items]

        # Apply column mapping from template
        if template and template.column_mapping:
            mapped_columns: list[str] = []
            mapped_indices: list[int] = []
            for idx, col in enumerate(columns):
                if col in template.column_mapping:
                    mapped_columns.append(template.column_mapping[col])
                    mapped_indices.append(idx)
            if mapped_columns:
                columns = mapped_columns
                rows = [[row[i] for i in mapped_indices if i < len(row)] for row in rows]

        return columns, rows

    @staticmethod
    def _build_html_table(
        columns: list[str],
        rows: list[list[Any]],
        header_text: str,
        footer_text: str,
    ) -> str:
        """Build a simple HTML document with an inline-styled table."""
        parts = [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head><meta charset=\"utf-8\"><title>",
            escape(header_text),
            "</title>",
            "<style>",
            "body{font-family:Arial,Helvetica,sans-serif;margin:24px;}",
            "h1{font-size:1.4em;}",
            "table{border-collapse:collapse;width:100%;}",
            "th,td{border:1px solid #ccc;padding:6px 10px;text-align:left;}",
            "th{background:#f5f5f5;}",
            "footer{margin-top:16px;font-size:0.85em;color:#666;}",
            "</style>",
            "</head><body>",
            f"<h1>{escape(header_text)}</h1>",
            "<table><thead><tr>",
        ]
        for col in columns:
            parts.append(f"<th>{escape(str(col))}</th>")
        parts.append("</tr></thead><tbody>")
        for row in rows:
            parts.append("<tr>")
            for cell in row:
                parts.append(f"<td>{escape(str(cell))}</td>")
            parts.append("</tr>")
        parts.append("</tbody></table>")
        if footer_text:
            parts.append(f"<footer>{escape(footer_text)}</footer>")
        parts.append("</body></html>")
        return "\n".join(parts)
