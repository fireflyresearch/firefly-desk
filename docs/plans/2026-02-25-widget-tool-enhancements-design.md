# Widget & Tool Enhancements Design

## Goal

Introduce rich interactive widgets (file viewer, editable table, paginated table, dynamic filters, 360° entity view), full-lifecycle office document tools, multimodal agent support, chat upload fixes, and API result transformation tools.

## Architecture

Three vertical slices organized by feature domain:

- **Document Domain** — File viewer widget + office document tools + multimodal wiring + upload fix
- **Table Domain** — Editable table + server-side pagination + standalone filter widget
- **Entity Domain** — Generic 360° entity view widget

Plus a cross-cutting **Transformation Tools** layer for API result processing.

## Tech Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy async, python-docx, openpyxl, python-pptx, reportlab, PyPDF2
- **Frontend**: SvelteKit, Svelte 5 runes, Tailwind, lucide-svelte
- **Agent**: fireflyframework-genai multimodal types (BinaryContent, DocumentUrl, ImageUrl)
- **Tests**: pytest (backend), Svelte check + build (frontend)

---

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File viewer | Click-to-open modal | Non-intrusive; user controls when to view |
| Editable table | Inline cell editing | Best UX for quick edits; agent specifies save endpoint |
| Pagination | Server-side | Scales to large datasets; API-driven |
| Dynamic filtering | Standalone widget | Reusable; connects to any table via shared ID |
| 360° entity view | Generic sections | Agent defines structure dynamically; works for any entity type |
| Document tools | Full lifecycle | Read, modify, create, convert documents |
| Result transforms | Agent-callable tools | Agent decides when to use; maximum flexibility |

---

## Slice A: Document Domain

### File Viewer Widget (`file_viewer`)

**Trigger**: Clicking file attachments in `MessageBubble.svelte` opens a modal overlay.

**Rendering by type**:
- PDF: `<iframe>` with browser-native PDF viewer
- DOCX: Server-side conversion to HTML via `python-docx`, rendered in modal
- XLSX: Server-side parsing via `openpyxl`, rendered as interactive table
- PPTX: Server-side slide-to-image conversion via `python-pptx`, slide carousel
- Images: Native `<img>` display

**Backend endpoint**: `GET /api/files/{file_id}/render?format=html|json|images`
- Returns rendered content based on file type and requested format
- HTML format for DOCX, JSON format for XLSX (columns + rows), image URLs for PPTX

**Agent emission**: `:::widget{type="file_viewer"}\n{"file_id": "...", "file_name": "..."}\n:::`

### Office Document Tools

Four agent-callable tools registered in `BuiltinToolExecutor`:

1. **`document_read`** — Extract text, tables, metadata from PDF/DOCX/XLSX/PPTX
2. **`document_create`** — Generate new documents:
   - PDF from HTML/markdown (reportlab)
   - DOCX from structured content (python-docx)
   - XLSX from tabular data (openpyxl)
3. **`document_modify`** — Edit existing documents:
   - DOCX: replace text, add paragraphs, update styles
   - XLSX: update cells, add rows/sheets
   - PDF: merge, split, add pages (PyPDF2)
4. **`document_convert`** — Convert between formats (DOCX→PDF, XLSX→CSV, etc.)

Libraries: `python-docx`, `openpyxl`, `python-pptx`, `reportlab`, `PyPDF2`

### Multimodal Agent Wiring

- Modify `DeskAgent._build_file_context()` to pass actual binary content as `BinaryContent`/`ImageUrl` to `FireflyAgent.run()` instead of only extracted text
- Check LLM provider multimodal capability before sending binary content
- Keep text extraction as fallback for non-multimodal models
- Wire `fireflyframework-genai` multimodal types: `ImageUrl`, `DocumentUrl`, `BinaryContent`

### Chat Upload Fix

- Audit `ContentExtractor` for all supported file types
- Fix error handling in upload pipeline
- Add proper error reporting to frontend when extraction fails
- Ensure file metadata is preserved through the pipeline

---

## Slice B: Table Domain

### Editable Table Widget (`editable_table`)

**Props**:
```json
{
  "columns": [
    {"key": "name", "label": "Name", "editable": true, "type": "text"},
    {"key": "status", "label": "Status", "editable": true, "type": "select", "options": ["active", "inactive"]},
    {"key": "count", "label": "Count", "editable": true, "type": "number"},
    {"key": "id", "label": "ID", "editable": false}
  ],
  "rows": [...],
  "save_endpoint": "/api/catalog/systems/{id}",
  "save_method": "PATCH"
}
```

**Behavior**:
- Click cell → inline editor matching column type (text input, number input, select dropdown, date picker)
- Modified cells highlighted with visual indicator
- Dirty tracking: "Save Changes" button appears when edits exist
- Save sends modified rows through agent tool execution (audit + permissions)
- Cancel discards all pending edits

### Paginated Table Widget (`paginated_table`)

**Props**:
```json
{
  "columns": [...],
  "data_endpoint": "/api/catalog/systems",
  "page_size": 25,
  "total_count": 150
}
```

**Behavior**:
- Widget fetches pages from `data_endpoint` with `?offset=N&limit=M`
- Navigation: prev/next buttons, current page indicator, rows-per-page selector
- Agent emits initial configuration; widget handles pagination autonomously
- Loading state while fetching

### Dynamic Filter Widget (`dynamic_filter`)

**Props**:
```json
{
  "filters": [
    {"field": "name", "label": "Name", "type": "text"},
    {"field": "created_at", "label": "Created", "type": "date_range"},
    {"field": "status", "label": "Status", "type": "select", "options": ["active", "inactive", "pending"]},
    {"field": "score", "label": "Score", "type": "number_range"}
  ],
  "target_widget_id": "systems-table"
}
```

**Filter types**: text (search), date_range (from/to pickers), select (dropdown), number_range (min/max inputs)

**Connection**: Filter widget dispatches custom events with filter values. Connected paginated table listens and re-fetches with filter params as query string parameters.

---

## Slice C: Entity Domain

### 360° Entity View Widget (`entity_view`)

**Props**:
```json
{
  "header": {
    "title": "Acme Corp",
    "subtitle": "Enterprise Customer",
    "avatar_url": "https://...",
    "status": "Active",
    "status_color": "success"
  },
  "sections": [
    {
      "type": "details",
      "title": "Company Information",
      "items": [
        {"label": "Industry", "value": "Technology"},
        {"label": "Revenue", "value": "$50M", "icon": "DollarSign"}
      ]
    },
    {
      "type": "metrics",
      "title": "Key Metrics",
      "items": [
        {"label": "MRR", "value": "$125K", "trend": "up", "change": "+12%"},
        {"label": "NPS", "value": "72", "trend": "stable"}
      ]
    },
    {
      "type": "timeline",
      "title": "Recent Activity",
      "events": [
        {"date": "2026-02-20", "title": "Contract renewed", "description": "3-year renewal"}
      ]
    },
    {
      "type": "related",
      "title": "Related Contacts",
      "items": [
        {"name": "Jane Smith", "type": "Primary Contact", "description": "VP Engineering"}
      ]
    },
    {
      "type": "table",
      "title": "Open Tickets",
      "columns": [{"key": "id", "label": "#"}, {"key": "subject", "label": "Subject"}],
      "rows": [...]
    }
  ]
}
```

**Section types**: `details` (key-value pairs), `metrics` (with trend indicators), `timeline` (chronological events), `related` (linked entities), `table` (inline data table).

**Layout**: Full-width card with header banner, sections rendered as tabbed or stacked panels depending on count. Each section type has its own sub-renderer component.

---

## Cross-Cutting: Result Transformation Tools

Agent-callable tools for processing API/tool results:

1. **`grep_result`** — Filter lines/objects matching a regex pattern
2. **`parse_json`** — Parse JSON string, extract nested paths (dot notation)
3. **`extract_table`** — Extract tabular data from HTML/XML/text responses
4. **`filter_rows`** — Filter array of objects by field conditions (eq, gt, lt, contains)
5. **`transform_data`** — Map, reduce, group, sort operations on arrays

Leverages existing `JsonTool` and `TextTool` from `fireflyframework-genai` where applicable, wrapping them as Desk built-in tools.

---

## Widget Registry Updates

New widgets to register in `frontend/src/lib/widgets/registry.ts`:

| Type | Component | Slice |
|------|-----------|-------|
| `file_viewer` | `FileViewer.svelte` | A |
| `editable_table` | `EditableDataTable.svelte` | B |
| `paginated_table` | `PaginatedTable.svelte` | B |
| `dynamic_filter` | `DynamicFilter.svelte` | B |
| `entity_view` | `EntityView.svelte` | C |
