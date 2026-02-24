# Admin Console Overhaul & Agent Call Whitelisting

> **Date:** 2026-02-24
> **Status:** Approved
> **Approach:** Monolithic overhaul, phased into 3 tiers

## Problem Statement

The admin console has significant gaps: wizard forms expose only a fraction of the backend model fields, there's no guided flow for system/endpoint creation, SSO mappings lack system-level targeting UX, knowledge documents have no edit/version/bulk capabilities, and the agent can potentially call arbitrary URLs outside the catalog with no whitelist enforcement.

## Implementation Tiers

| Tier | Scope | Priority |
|------|-------|----------|
| 1 | Whitelist enforcement backend + System Catalog wizard | Critical |
| 2 | Endpoint wizard (all protocols) + SSO mapping UX + Knowledge lifecycle | High |
| 3 | Skill wizard enhancements + bulk operations + edge case polish | Medium |

---

## 1. Agent Call Whitelisting & Security Model

### 1.1 Whitelist-by-Default

New `tool_access_mode` app setting:
- `"whitelist"` (default): Catalog tools must be explicitly enabled.
- `"all_enabled"`: All catalog tools available (dev/demo mode).

### 1.2 System-Level Agent Access

Add `agent_enabled: bool = False` to `ExternalSystemRow`.

`ToolFactory.build_tool_definitions()` gains an additional filter:
```
if tool_access_mode == "whitelist" and not system.agent_enabled:
    skip system's endpoints
```

Individual endpoint overrides (`tool_config` settings) still apply for fine-grained control.

### 1.3 Safe Internal Calls

Embedding providers, LLM providers, and other infrastructure use their own `httpx` clients — they do NOT pass through `ToolExecutor`. The whitelist only affects `ToolExecutor.execute_parallel()`. No changes needed to protect internal calls.

### 1.4 URL Enforcement

Add a guard in `ToolExecutor._execute_single()`:
```python
resolved_url = system.base_url + resolved_path
if not resolved_url.startswith(system.base_url):
    raise ToolExecutionError("URL does not match system base_url")
```

This prevents prompt injection attacks where manipulated path parameters redirect calls to arbitrary hosts.

### Key Files
- `src/flydesk/models/catalog.py` — Add `agent_enabled` column
- `src/flydesk/tools/factory.py` — Add whitelist filter
- `src/flydesk/tools/executor.py` — Add URL enforcement guard
- `src/flydesk/api/catalog.py` — Expose `agent_enabled` in API
- `src/flydesk/api/tools_admin.py` — Add whitelist mode setting endpoint

---

## 2. System Catalog Wizard

### 2.1 System Creation Wizard (4 Steps)

**Step 1 — System Basics**
- Name (required)
- Description (textarea, required)
- Base URL (required, URL validation)
- Status (active/inactive/degraded dropdown)
- Tags (tag input with autocomplete)
- Health check path (optional, with "Test" button)

**Step 2 — Authentication**
- Auth type selector (OAuth2, API Key, Basic, Bearer, Mutual TLS)
- Dynamic fields per auth type:
  - **OAuth2:** Token URL, scopes, client credential ID (link to Credential Vault)
  - **API Key:** Header name, credential ID
  - **Basic:** Credential ID
  - **Bearer:** Credential ID
  - **Mutual TLS:** Custom headers, cert credential ID
- "Create Credential" inline shortcut
- "Test Authentication" button

**Step 3 — Agent Access**
- `agent_enabled` toggle
- Brief explanation of whitelist mode
- Whitelist mode notice when active

**Step 4 — Review & Create**
- Summary card of all configured values
- "Create System" button
- Post-creation: "Add endpoints?" prompt → navigates to endpoint wizard

### Key Files
- `frontend/src/lib/components/admin/CatalogManager.svelte` — Replace simple form with wizard
- New: `frontend/src/lib/components/admin/SystemWizard.svelte` — Multi-step wizard component

---

## 3. Endpoint Wizard (All Protocols)

### 3.1 Endpoint Creation Wizard (4 Steps)

**Step 1 — Endpoint Basics**
- Protocol type selector (REST, GraphQL, SOAP, gRPC)
- Name, description
- `when_to_use` (agent guidance text)

**Step 2 — Protocol Configuration** (dynamic per protocol)
- **REST:** Method (GET/POST/PUT/PATCH/DELETE), Path (with `{param}` highlighting)
- **GraphQL:** Query editor, operation name
- **SOAP:** SOAP action, body template editor
- **gRPC:** Service name, method name

**Step 3 — Parameters**
- Path params (auto-detected from REST path template)
- Query params (name, type, required, description)
- Request body (JSON schema editor or simple field list)
- Response schema (optional JSON schema)

**Step 4 — Safety & Permissions**
- Risk level (read, low_write, high_write, destructive)
- Required permissions (multi-select)
- Confirmation toggle (auto-set for high_write/destructive)
- Rate limit (requests/second, burst size)
- Timeout (seconds)
- Retry policy (max retries, backoff multiplier)
- Examples (multi-line, agent usage examples)

### Key Files
- New: `frontend/src/lib/components/admin/EndpointWizard.svelte`
- `src/flydesk/api/catalog.py` — Ensure all endpoint fields are accepted in create/update

---

## 4. SSO Mapping UX

### 4.1 Mapping Form Redesign

- **Claim path:** Text input with examples (`roles`, `groups[0]`, `custom:department`)
- **Target:** Dropdown (Header / Query Param) + target name input
- **System targeting (dual-mode):**
  - **Simple mode (default):** Multi-select dropdown of registered systems. "Apply to all" checkbox.
  - **Advanced mode:** Toggle to regex input with live preview showing matched systems.
  - Internal storage: Always regex. Dropdown selections converted to `^(sys-a|sys-b|sys-c)$`.
- **Transform:** Dropdown (lowercase, uppercase, JSON path, none) + "Custom" option.

### 4.2 Mapping List View

- Table: Claim Path, Target, Systems (names, not regex), Active toggle
- "Test Mapping" button: Enter sample JWT, see resolved headers per system

### Key Files
- `frontend/src/lib/components/admin/SSOAttributeMapper.svelte` — Redesign form
- `src/flydesk/api/sso_mappings.py` — Add endpoint to resolve system names from regex
- `src/flydesk/api/catalog.py` — Provide system list for dropdown population

---

## 5. Knowledge Document Lifecycle

### 5.1 Document States

`draft` → `indexing` → `published` → `archived`

Add `status: str` field to `KnowledgeDocumentRow` (default: `"draft"`). Transitions:
- Created → `draft`
- Queued for indexing → `indexing`
- Successfully indexed → `published`
- Soft-deleted → `archived`

Filter by status in list view.

### 5.2 Enhanced Document Detail

- **Edit mode:** Toggle view/edit for title, content, tags, metadata
- **Re-index button:** Triggers re-chunking + re-embedding
- **Version history:** `version: int` + `previous_version_id` fields. Each edit creates new version. Show version list with timestamps.
- **Chunk preview:** Show chunks + embedding status (has vector? dimensions?)

### 5.3 Bulk Operations

- Multi-select checkboxes in document list
- Bulk toolbar: Delete, Re-index, Archive, Export (JSON)
- Bulk file upload: Drag-drop zone accepting multiple files, upload queue with per-file progress

### 5.4 Better Error Handling

- Indexing status per document (pending, indexing, failed, success)
- Failed imports show error details + "Retry" button
- URL import: Preview fetched content before confirming
- OpenAPI import: Show parsed endpoint count before confirming
- File upload: File type/size validation before upload

### 5.5 Improved Ingestion UX

- URL tab: Content preview pane before indexing
- OpenAPI tab: Parsed endpoint summary before import
- File tab: Multi-file acceptance, upload queue
- All tabs: Tag autocomplete, document type dropdown (not free text)

### Key Files
- `src/flydesk/models/knowledge_base.py` — Add `status`, `version`, `previous_version_id`
- `src/flydesk/api/knowledge.py` — Add bulk endpoints, status transitions, re-index
- `frontend/src/lib/components/admin/KnowledgeBaseManager.svelte` — Multi-select, bulk toolbar
- `frontend/src/lib/components/admin/KnowledgeAddDocument.svelte` — Preview panes, multi-file
- `frontend/src/lib/components/admin/KnowledgeDocumentDetail.svelte` — Edit mode, versions, chunks

---

## 6. Skill Wizard Enhancement

### 6.1 Structured Skill Editor

Replace plain textarea with guided sections:
- **Steps:** Ordered list, each entry has description + endpoint selector (from catalog)
- **Guidelines:** Bulleted list editor
- **Referenced endpoints:** Multi-select from catalog (auto-links)
- **Referenced documents:** Multi-select from knowledge base (auto-links)

### 6.2 Preview & Validation

- **Preview mode:** Rendered markdown alongside editor
- **Test mode:** "Dry run" showing available tools/knowledge with this skill active
- **Endpoint validation:** Warn if referenced endpoints don't exist or aren't agent-enabled

The skill model stays unchanged (content is a string). The editor produces structured markdown.

### Key Files
- `frontend/src/lib/components/admin/SkillManager.svelte` — Replace form with structured editor
- New: `frontend/src/lib/components/admin/SkillEditor.svelte` — Structured editing component

---

## Non-Goals

- No changes to the chat interface or agent reasoning
- No changes to the RBAC permission model (reuse existing)
- No database migration tool (SQLite handles schema changes via CREATE IF NOT EXISTS)
- No multi-tenant isolation (single-instance architecture)

## Testing Strategy

- Backend: Unit tests for whitelist filtering, URL enforcement, document state transitions
- Frontend: `svelte-check` + build verification
- Integration: Manual walkthrough of all wizard flows
