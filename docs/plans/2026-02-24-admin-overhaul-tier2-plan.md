# Admin Overhaul Tier 2: Endpoint Wizard + SSO Mapping UX + Knowledge Lifecycle

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add a multi-protocol endpoint creation wizard, improve SSO mapping with system-targeted dropdowns, and enhance knowledge documents with status tracking, content editing, and bulk operations.

**Architecture:** Frontend-heavy tier. Three new/enhanced Svelte components backed by targeted API additions. Endpoint wizard handles REST/GraphQL/SOAP/gRPC with protocol-specific form sections. SSO mapper gains a system dropdown populated from the catalog. Knowledge documents get a `status` field for lifecycle tracking and bulk toolbar for multi-document operations.

**Tech Stack:** Python 3.13, SQLAlchemy 2 (async), FastAPI, Pydantic v2, Svelte 5 (runes), TailwindCSS

**Design doc:** `docs/plans/2026-02-24-admin-overhaul-design.md` (sections 3, 4, 5)

---

## Task 1: Fix Repository `_row_to_endpoint()` + Add PUT Endpoint API

The repository mapper `_row_to_endpoint()` doesn't populate protocol-specific fields (graphql_query, soap_action, grpc_service, etc.) even though the ORM columns exist. Also, the catalog API has no PUT endpoint for updating endpoints.

**Files:**
- Modify: `src/flydesk/catalog/repository.py:378-397` — Add protocol fields to mapper
- Modify: `src/flydesk/catalog/repository.py:178-203` — Enhance `update_endpoint()` with protocol fields
- Modify: `src/flydesk/api/catalog.py` — Add PUT endpoint route
- Test: `tests/api/test_catalog_api.py`

**Steps:**

1. Read `src/flydesk/catalog/repository.py` lines 378-397 (`_row_to_endpoint()`) and lines 178-203 (`update_endpoint()`).

2. Update `_row_to_endpoint()` to include all protocol fields from `ServiceEndpointRow`:
   ```python
   @staticmethod
   def _row_to_endpoint(row: ServiceEndpointRow) -> ServiceEndpoint:
       return ServiceEndpoint(
           id=row.id,
           system_id=row.system_id,
           name=row.name,
           description=row.description,
           method=row.method,
           path=row.path,
           path_params=_from_json_or_none(row.path_params),
           query_params=_from_json_or_none(row.query_params),
           request_body=_from_json_or_none(row.request_body),
           response_schema=_from_json_or_none(row.response_schema),
           when_to_use=row.when_to_use,
           examples=_from_json(row.examples),
           risk_level=row.risk_level,
           required_permissions=_from_json(row.required_permissions),
           rate_limit=_from_json_or_none(row.rate_limit),
           timeout_seconds=row.timeout_seconds,
           retry_policy=_from_json_or_none(row.retry_policy),
           tags=_from_json(row.tags),
           # Protocol-specific fields
           protocol_type=getattr(row, 'protocol_type', 'rest') or 'rest',
           graphql_query=getattr(row, 'graphql_query', None),
           graphql_operation_name=getattr(row, 'graphql_operation_name', None),
           soap_action=getattr(row, 'soap_action', None),
           soap_body_template=getattr(row, 'soap_body_template', None),
           grpc_service=getattr(row, 'grpc_service', None),
           grpc_method_name=getattr(row, 'grpc_method_name', None),
       )
   ```

   Note: Check if the `ServiceEndpointRow` ORM actually has these protocol columns. If not, they need to be added. Read `src/flydesk/models/catalog.py` lines 50-76 to verify.

3. Update `update_endpoint()` to handle all fields including protocol-specific ones:
   ```python
   async def update_endpoint(self, endpoint: ServiceEndpoint) -> None:
       async with self._session_factory() as session:
           row = await session.get(ServiceEndpointRow, endpoint.id)
           if row is None:
               raise ValueError(f"Endpoint {endpoint.id} not found")
           row.name = endpoint.name
           row.description = endpoint.description
           row.method = endpoint.method.value
           row.path = endpoint.path
           row.path_params = _to_json(
               {k: v.model_dump() for k, v in endpoint.path_params.items()}
               if endpoint.path_params else None
           )
           row.query_params = _to_json(
               {k: v.model_dump() for k, v in endpoint.query_params.items()}
               if endpoint.query_params else None
           )
           row.request_body = _to_json(endpoint.request_body)
           row.response_schema = _to_json(endpoint.response_schema)
           row.when_to_use = endpoint.when_to_use
           row.examples = _to_json(endpoint.examples)
           row.risk_level = endpoint.risk_level.value
           row.required_permissions = _to_json(endpoint.required_permissions)
           row.rate_limit = _to_json(
               endpoint.rate_limit.model_dump() if endpoint.rate_limit else None
           )
           row.timeout_seconds = endpoint.timeout_seconds
           row.retry_policy = _to_json(
               endpoint.retry_policy.model_dump() if endpoint.retry_policy else None
           )
           row.tags = _to_json(endpoint.tags)
           await session.commit()
   ```

4. Add PUT endpoint route in `src/flydesk/api/catalog.py` (after `create_endpoint`):
   ```python
   @router.put("/endpoints/{endpoint_id}", dependencies=[CatalogWrite])
   async def update_endpoint(
       endpoint_id: str, endpoint: ServiceEndpoint, repo: Repo, trigger: Trigger
   ) -> ServiceEndpoint:
       """Update an existing service endpoint."""
       existing = await repo.get_endpoint(endpoint_id)
       if existing is None:
           raise HTTPException(status_code=404, detail=f"Endpoint {endpoint_id} not found")
       await repo.update_endpoint(endpoint)
       if trigger is not None:
           await trigger.on_catalog_updated(endpoint.system_id)
       return endpoint
   ```

5. Run tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x -q
   ```

6. Commit:
   ```bash
   git add src/flydesk/catalog/repository.py src/flydesk/api/catalog.py
   git commit -m "feat(catalog): fix endpoint mapper protocol fields + add PUT endpoint route"
   ```

---

## Task 2: Add Protocol Columns to ServiceEndpointRow ORM (if missing)

Check whether `ServiceEndpointRow` has protocol-specific ORM columns. The `ServiceEndpoint` Pydantic model has `protocol_type`, `graphql_query`, `graphql_operation_name`, `soap_action`, `soap_body_template`, `grpc_service`, `grpc_method_name` — but the ORM may be missing these.

**Files:**
- Modify: `src/flydesk/models/catalog.py:49-76` — Add missing protocol columns if needed
- Modify: `src/flydesk/catalog/repository.py:113-149` — Update `create_endpoint()` to persist protocol fields

**Steps:**

1. Read `src/flydesk/models/catalog.py` and check if `ServiceEndpointRow` has columns for: `protocol_type`, `graphql_query`, `graphql_operation_name`, `soap_action`, `soap_body_template`, `grpc_service`, `grpc_method_name`.

2. If any are missing, add them:
   ```python
   protocol_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rest")
   graphql_query: Mapped[str | None] = mapped_column(Text, nullable=True)
   graphql_operation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
   soap_action: Mapped[str | None] = mapped_column(String(500), nullable=True)
   soap_body_template: Mapped[str | None] = mapped_column(Text, nullable=True)
   grpc_service: Mapped[str | None] = mapped_column(String(255), nullable=True)
   grpc_method_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
   ```

3. If already present (columns exist), skip this task — mark complete.

4. Update `create_endpoint()` in `src/flydesk/catalog/repository.py` to include protocol fields in the Row constructor.

5. Run tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x -q
   ```

6. Commit (only if changes were needed):
   ```bash
   git add src/flydesk/models/catalog.py src/flydesk/catalog/repository.py
   git commit -m "feat(catalog): add protocol-specific columns to ServiceEndpointRow"
   ```

---

## Task 3: EndpointWizard.svelte Component

Create a 4-step wizard for creating/editing service endpoints with protocol-specific configuration.

**Step 1:** Endpoint Basics (name, description, when_to_use, risk_level, required_permissions)
**Step 2:** Protocol Configuration (protocol_type selector, then dynamic fields per protocol)
**Step 3:** Parameters & Body (path_params, query_params, request_body, response_schema)
**Step 4:** Advanced & Review (rate_limit, timeout, retry_policy, tags, examples + summary)

**Files:**
- Create: `frontend/src/lib/components/admin/EndpointWizard.svelte`

**Steps:**

1. Read the existing `SystemWizard.svelte` to replicate the same wizard pattern (modal, step indicators, navigation, validation).

2. Read `src/flydesk/catalog/enums.py` for the exact enum values: `ProtocolType` (rest, graphql, soap, grpc), `HttpMethod` (GET, POST, PUT, PATCH, DELETE), `RiskLevel` (read, low_write, high_write, destructive).

3. Create `frontend/src/lib/components/admin/EndpointWizard.svelte` with:

   **Props:**
   ```typescript
   interface Props {
       systemId: string;
       editingEndpoint?: any | null;
       onClose: () => void;
       onSaved: () => void;
   }
   ```

   **Form data structure:**
   ```typescript
   let formData = $state({
       // Step 1: Basics
       id: '',
       name: '',
       description: '',
       when_to_use: '',
       risk_level: 'read',
       required_permissions: '',  // comma-separated

       // Step 2: Protocol
       protocol_type: 'rest',
       method: 'GET',
       path: '',
       graphql_query: '',
       graphql_operation_name: '',
       soap_action: '',
       soap_body_template: '',
       grpc_service: '',
       grpc_method_name: '',

       // Step 3: Parameters
       // Use simple JSON text areas for path_params, query_params, request_body, response_schema
       path_params_json: '',
       query_params_json: '',
       request_body_json: '',
       response_schema_json: '',

       // Step 4: Advanced
       timeout_seconds: 30,
       rate_limit_max: '',
       rate_limit_window: '',
       retry_max: '',
       retry_backoff: '',
       tags: '',
       examples: '',  // one per line
   });
   ```

   **Step 2 dynamic fields by protocol:**
   - **REST:** Method dropdown + Path input (with `{param}` placeholder highlighting)
   - **GraphQL:** Query textarea + Operation Name input
   - **SOAP:** SOAP Action input + Body Template textarea
   - **gRPC:** Service Name input + Method Name input

   **Step 3:**
   - For REST: Auto-detect path params from `{param}` in the path
   - JSON textareas for query_params, request_body, response_schema
   - Validation: try JSON.parse() and show error if invalid

   **Submit** builds the full `ServiceEndpoint` payload and calls:
   - POST `/catalog/systems/${systemId}/endpoints` (create)
   - PUT `/catalog/endpoints/${endpoint.id}` (update)

4. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

5. Commit:
   ```bash
   git add frontend/src/lib/components/admin/EndpointWizard.svelte
   git commit -m "feat(frontend): add multi-protocol EndpointWizard component"
   ```

---

## Task 4: Integrate EndpointWizard into CatalogManager

Add "Add Endpoint" and "Edit Endpoint" actions to the expanded endpoint rows in `CatalogManager.svelte`.

**Files:**
- Modify: `frontend/src/lib/components/admin/CatalogManager.svelte`

**Steps:**

1. Read current `CatalogManager.svelte`, specifically:
   - The `Endpoint` interface (lines 27-33) — expand it with all fields
   - The expanded endpoints table (lines 444-488) — add action buttons
   - The endpoint cache loading (lines 77-85) — needs to return full endpoint data

2. Import `EndpointWizard`:
   ```typescript
   import EndpointWizard from './EndpointWizard.svelte';
   ```

3. Add state:
   ```typescript
   let showEndpointWizard = $state(false);
   let endpointWizardSystemId = $state('');
   let editingEndpoint = $state<any | null>(null);
   ```

4. Add functions:
   ```typescript
   function openAddEndpoint(systemId: string) {
       endpointWizardSystemId = systemId;
       editingEndpoint = null;
       showEndpointWizard = true;
   }

   async function openEditEndpoint(endpointId: string, systemId: string) {
       try {
           editingEndpoint = await apiJson(`/catalog/endpoints/${endpointId}`);
           endpointWizardSystemId = systemId;
           showEndpointWizard = true;
       } catch (e) {
           error = e instanceof Error ? e.message : 'Failed to load endpoint';
       }
   }
   ```

5. Update the expanded endpoints table to add:
   - "Add Endpoint" button below the endpoints table
   - Edit/Delete action buttons per endpoint row
   - Protocol badge (REST/GraphQL/SOAP/gRPC) next to method

6. Expand the `Endpoint` interface to include `name`, `risk_level`, `protocol_type`.

7. Add the wizard render:
   ```svelte
   {#if showEndpointWizard}
       <EndpointWizard
           systemId={endpointWizardSystemId}
           editingEndpoint={editingEndpoint}
           onClose={() => { showEndpointWizard = false; editingEndpoint = null; }}
           onSaved={() => {
               showEndpointWizard = false;
               editingEndpoint = null;
               endpointCache = {};  // force reload
               loadSystems();
           }}
       />
   {/if}
   ```

8. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

9. Commit:
   ```bash
   git add frontend/src/lib/components/admin/CatalogManager.svelte
   git commit -m "feat(frontend): integrate EndpointWizard into CatalogManager"
   ```

---

## Task 5: SSO Mapping System Dropdown

Replace the free-text `system_filter` input in `SSOAttributeMapper.svelte` with a dual-mode selector: "All Systems" checkbox or system multi-select dropdown populated from the catalog API.

**Files:**
- Modify: `frontend/src/lib/components/admin/SSOAttributeMapper.svelte`

**Steps:**

1. Read `frontend/src/lib/components/admin/SSOAttributeMapper.svelte` fully.

2. Add system loading:
   ```typescript
   interface CatalogSystem {
       id: string;
       name: string;
       status: string;
   }
   let availableSystems = $state<CatalogSystem[]>([]);
   let allSystems = $state(true);  // "Apply to all" mode

   async function loadSystems() {
       try {
           availableSystems = await apiJson<CatalogSystem[]>('/catalog/systems');
       } catch { /* silent — systems are optional enhancement */ }
   }
   ```

3. Call `loadSystems()` in the existing `$effect`.

4. Replace the `system_filter` text input in the form with a dual-mode selector:
   ```svelte
   <div class="col-span-2 flex flex-col gap-1">
       <span class="text-xs font-medium text-text-secondary">System Targeting</span>
       <label class="flex items-center gap-2">
           <input type="checkbox" bind:checked={allSystems}
               class="h-3.5 w-3.5 rounded border-border text-accent" />
           <span class="text-sm text-text-primary">Apply to all systems</span>
       </label>
       {#if !allSystems}
           <select bind:value={formData.system_filter}
               class="mt-1 rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent">
               <option value="">Select a system...</option>
               {#each availableSystems as sys}
                   <option value={sys.id}>{sys.name}</option>
               {/each}
           </select>
       {/if}
   </div>
   ```

5. When `allSystems` is toggled on, clear `formData.system_filter`. When submitting, send `system_filter: null` if allSystems is true.

6. In the mappings table, replace the raw `system_filter` text with the system name (look up from `availableSystems`):
   ```typescript
   function systemName(systemId: string | null): string {
       if (!systemId) return 'All systems';
       const sys = availableSystems.find(s => s.id === systemId);
       return sys?.name || systemId;
   }
   ```

7. When editing a mapping, pre-set `allSystems = !formData.system_filter`.

8. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

9. Commit:
   ```bash
   git add frontend/src/lib/components/admin/SSOAttributeMapper.svelte
   git commit -m "feat(frontend): add system dropdown to SSO attribute mapper"
   ```

---

## Task 6: Add `status` Field to Knowledge Document

Add a `status` field to track document lifecycle state: `draft` → `indexing` → `published` → `error` → `archived`.

**Files:**
- Modify: `src/flydesk/knowledge/models.py` — Add `DocumentStatus` enum + `status` field
- Modify: `src/flydesk/models/knowledge_base.py` — Add `status` column to ORM
- Modify: `src/flydesk/catalog/repository.py:292-362` — Update knowledge doc mapping
- Modify: `src/flydesk/api/knowledge.py` — Return status in responses

**Steps:**

1. Add `DocumentStatus` enum to `src/flydesk/knowledge/models.py`:
   ```python
   class DocumentStatus(StrEnum):
       DRAFT = "draft"
       INDEXING = "indexing"
       PUBLISHED = "published"
       ERROR = "error"
       ARCHIVED = "archived"
   ```

2. Add `status` field to `KnowledgeDocument` model:
   ```python
   status: DocumentStatus = DocumentStatus.DRAFT
   ```

3. Add `status` column to `KnowledgeDocumentRow` in `src/flydesk/models/knowledge_base.py`:
   ```python
   status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
   ```

4. Update the knowledge document mapping in `src/flydesk/catalog/repository.py` (`list_knowledge_documents`, `get_knowledge_document`) to include `status`.

5. Update `update_knowledge_document()` to accept an optional `status` parameter.

6. Run tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x -q
   ```

7. Commit:
   ```bash
   git add src/flydesk/knowledge/models.py src/flydesk/models/knowledge_base.py src/flydesk/catalog/repository.py
   git commit -m "feat(knowledge): add document status lifecycle field"
   ```

---

## Task 7: Knowledge Bulk Operations Backend

Add bulk operation endpoints: bulk delete, bulk archive, bulk re-index.

**Files:**
- Modify: `src/flydesk/api/knowledge.py` — Add bulk endpoints

**Steps:**

1. Read `src/flydesk/api/knowledge.py` to understand existing patterns (dependencies, guards, etc.).

2. Add request model:
   ```python
   class BulkDocumentRequest(BaseModel):
       document_ids: list[str]
   ```

3. Add bulk endpoints:

   **POST /api/knowledge/documents/bulk-delete:**
   ```python
   @router.post("/documents/bulk-delete", status_code=200, dependencies=[KnowledgeDelete])
   async def bulk_delete_documents(
       body: BulkDocumentRequest, indexer: Indexer, store: DocStore
   ) -> dict[str, Any]:
       deleted = 0
       errors = []
       for doc_id in body.document_ids:
           try:
               await indexer.delete_document(doc_id)
               deleted += 1
           except Exception as exc:
               errors.append({"document_id": doc_id, "error": str(exc)})
       return {"deleted": deleted, "errors": errors}
   ```

   **POST /api/knowledge/documents/bulk-archive:**
   ```python
   @router.post("/documents/bulk-archive", status_code=200, dependencies=[KnowledgeWrite])
   async def bulk_archive_documents(
       body: BulkDocumentRequest, store: DocStore
   ) -> dict[str, Any]:
       archived = 0
       for doc_id in body.document_ids:
           await store.update_document(doc_id, status="archived")
           archived += 1
       return {"archived": archived}
   ```

   **POST /api/knowledge/documents/bulk-reindex:**
   ```python
   @router.post("/documents/bulk-reindex", status_code=202, dependencies=[KnowledgeWrite])
   async def bulk_reindex_documents(
       body: BulkDocumentRequest, store: DocStore, producer: Producer
   ) -> dict[str, Any]:
       queued = 0
       for doc_id in body.document_ids:
           doc = await store.get_document(doc_id)
           if doc:
               task = IndexingTask(
                   document_id=doc.id, title=doc.title, content=doc.content,
                   document_type=str(doc.document_type), source=doc.source or "",
                   tags=doc.tags, metadata=doc.metadata,
               )
               await producer.enqueue(task)
               queued += 1
       return {"queued": queued}
   ```

4. Run tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x -q
   ```

5. Commit:
   ```bash
   git add src/flydesk/api/knowledge.py
   git commit -m "feat(knowledge): add bulk delete/archive/reindex endpoints"
   ```

---

## Task 8: Knowledge Manager UI Enhancement

Update `KnowledgeBaseManager.svelte` with:
- Status badges on documents
- Bulk toolbar (archive, re-index, delete)
- Status filter dropdown

**Files:**
- Modify: `frontend/src/lib/components/admin/KnowledgeBaseManager.svelte`

**Steps:**

1. Read the full `KnowledgeBaseManager.svelte`.

2. Add status badge helper:
   ```typescript
   function statusBadge(status: string): { color: string; label: string } {
       switch (status) {
           case 'published': return { color: 'bg-success/10 text-success', label: 'Published' };
           case 'indexing': return { color: 'bg-accent/10 text-accent', label: 'Indexing' };
           case 'draft': return { color: 'bg-text-secondary/10 text-text-secondary', label: 'Draft' };
           case 'error': return { color: 'bg-danger/10 text-danger', label: 'Error' };
           case 'archived': return { color: 'bg-warning/10 text-warning', label: 'Archived' };
           default: return { color: 'bg-text-secondary/10 text-text-secondary', label: status };
       }
   }
   ```

3. Add status filter state:
   ```typescript
   let statusFilter = $state('all');
   let filteredDocuments = $derived(
       documents.filter(d => {
           const matchesSearch = !searchQuery || d.title.toLowerCase().includes(searchQuery.toLowerCase());
           const matchesStatus = statusFilter === 'all' || d.status === statusFilter;
           return matchesSearch && matchesStatus;
       })
   );
   ```

4. Add status filter dropdown next to search bar.

5. Add status badge column to the documents table.

6. Enhance the bulk toolbar (already has bulk delete):
   - Add "Archive" and "Re-index" buttons when selectedIds is non-empty
   - Wire to `POST /knowledge/documents/bulk-archive` and `POST /knowledge/documents/bulk-reindex`

7. Run frontend check:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

8. Commit:
   ```bash
   git add frontend/src/lib/components/admin/KnowledgeBaseManager.svelte
   git commit -m "feat(frontend): add status badges, filter, and bulk operations to knowledge manager"
   ```

---

## Task 9: Knowledge Document Detail — Content Editing

Update `KnowledgeDocumentDetail.svelte` to support editing the document content (not just metadata). When content is edited, the document status resets to `draft` and can be re-indexed.

**Files:**
- Modify: `frontend/src/lib/components/admin/KnowledgeDocumentDetail.svelte`
- Modify: `src/flydesk/api/knowledge.py` — Extend PUT to accept content updates

**Steps:**

1. Read `frontend/src/lib/components/admin/KnowledgeDocumentDetail.svelte` fully.

2. Update the backend `PUT /knowledge/documents/{document_id}` to also accept optional `content` and `status` fields:
   ```python
   class DocumentMetadataUpdate(BaseModel):
       title: str | None = None
       document_type: str | None = None
       tags: list[str] | None = None
       content: str | None = None
       status: str | None = None
   ```

3. Update `update_knowledge_document()` in `src/flydesk/catalog/repository.py` to handle `content` and `status` fields.

4. In the frontend detail component:
   - Expand `editForm` to include `content`:
     ```typescript
     let editForm = $state({
         title: '',
         source: '',
         tags: '',
         content: '',
     });
     ```
   - Add a textarea for content editing in edit mode
   - Add a "Re-index" button that re-submits the document for indexing
   - Show document status badge
   - Show chunk count and embedding status info

5. Run frontend check + backend tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x -q
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

6. Commit:
   ```bash
   git add frontend/src/lib/components/admin/KnowledgeDocumentDetail.svelte src/flydesk/api/knowledge.py src/flydesk/catalog/repository.py
   git commit -m "feat(knowledge): add content editing and re-indexing to document detail"
   ```

---

## Task 10: Verification

1. Run backend tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py
   ```

2. Run frontend checks:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

---

## Dependency Graph

```
Task 1 (Endpoint mapper + PUT API)    — No deps
Task 2 (Protocol ORM columns)         — No deps
Task 3 (EndpointWizard.svelte)        — Depends on Tasks 1, 2
Task 4 (CatalogManager integration)   — Depends on Task 3
Task 5 (SSO system dropdown)          — No deps
Task 6 (Knowledge status field)       — No deps
Task 7 (Knowledge bulk operations)    — Depends on Task 6
Task 8 (Knowledge manager UI)         — Depends on Tasks 6, 7
Task 9 (Document detail editing)      — Depends on Task 6
Task 10 (Verification)                — ALL previous tasks
```

**Execution order:**
1. Tasks 1, 2, 5, 6 (parallel — all independent)
2. Tasks 3, 7, 9 (need 1/2/6)
3. Tasks 4, 8 (need 3/7)
4. Task 10 (final)

---

## Summary Table

| # | Task | Key Files | Impact |
|---|------|-----------|--------|
| 1 | Endpoint mapper + PUT API | `repository.py`, `catalog.py` | Foundation |
| 2 | Protocol ORM columns | `models/catalog.py` | Foundation |
| 3 | EndpointWizard.svelte | New component | **Critical** — multi-protocol wizard |
| 4 | CatalogManager integration | `CatalogManager.svelte` | **Critical** — endpoint CRUD UX |
| 5 | SSO system dropdown | `SSOAttributeMapper.svelte` | **UX** — targeted mappings |
| 6 | Knowledge status field | `models.py`, ORM, repository | Foundation |
| 7 | Knowledge bulk operations | `api/knowledge.py` | **API** — batch operations |
| 8 | Knowledge manager UI | `KnowledgeBaseManager.svelte` | **UX** — status + bulk |
| 9 | Document detail editing | `KnowledgeDocumentDetail.svelte` | **UX** — content editing |
| 10 | Verification | — | Quality gate |
