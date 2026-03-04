# Changelog

All notable changes to Firefly Desk are documented in this file.

## [Unreleased]

### Added

- **LLM Runtime Settings** — Admin page (`/admin/llm-runtime`) with dual-mode UI: guided 4-step wizard and enhanced settings page with collapsible sections. Three preset profiles (Conservative, Balanced, Performance) for one-click configuration. 21 admin-tunable fields covering retry policies, timeouts, context truncation budgets, and token limits, all stored in the database and editable at runtime.
- **Smart Model Routing** — Automatic complexity classification that routes simple messages to cheaper/faster models and complex queries to more capable models. Configurable via `/admin/llm-providers` (Model Routing tab) with per-tier model mappings, confidence thresholds, and a default tier fallback.
- **Fallback Models** — Per-provider fallback model configuration with setup wizard in the LLM Configuration page. When the primary model is rate-limited or unavailable, the agent automatically retries with lighter models.
- **Follow-up Response Streaming** — Follow-up LLM calls (e.g., summarizing tool results) now stream tokens in real-time rather than waiting for the full response.
- **Service Catalog Enhancements** — Unified import wizard with method picker (curl import, file upload, KB detection, manual), first-class tags with join-table architecture, system-document linking, credential mapping with target/transform support, and LLM-driven system relationship discovery that accepts knowledge documents.
- **Credential Mapping** — Credentials can now be injected into headers, query parameters, path parameters, or request body with optional transforms (base64, prefix). `ResolvedAuth` dataclass replaces the previous headers-only approach.
- **Email Channel** — Full email integration with Resend and AWS SES providers. Includes setup wizard, identity configuration, HTML signature editor with live preview, behavior controls (auto-reply, CC handling, email-specific persona), inbound webhook processing, and built-in ngrok/cloudflared tunnel for local development.
- **Callbacks** — Outbound webhook system for event notifications (email.sent, email.received, email.failed, conversation.created, conversation.updated, agent.error). HMAC-SHA256 signed payloads with exponential backoff retries and a delivery log.
- **Background Job Controls** — Pause, resume, and cancel running jobs with checkpoint support. Live timestamps and inline controls in the admin UI and notifications panel.
- **Knowledge Graph Explorer** — Interactive Cytoscape.js visualization with force-directed layout, typed color-coded nodes, hover-to-highlight neighbors, entity detail panel, and batch relations endpoint.
- **Workflow Engine** — Durable workflow execution with start, resume, and cancel operations. Webhook-triggered steps, scheduler, and full CRUD repository.
- **Notification Panel** — Real-time notification system integrated into the top bar, showing job progress, email events, and agent errors.
- **Dynamic Form Widget** — Interactive form widget for collecting structured user input directly in the chat interface.
- **Conversation Folders** — Drag-and-drop conversation organization with folder management.
- **File Upload Error Feedback** — Upload failures in the chat input bar now display an inline error message with dismiss action instead of silently failing.
- **Entity Embeddings** — Knowledge graph entities are now embedded for semantic search alongside structural graph traversal.
- **Document Chunked Reading** — Large documents can be read in chunks by the agent, preventing context overflow.
- **In-app Help** — 22 help pages covering all admin console sections, accessible from the Help & Guides sidebar group.
- **Platform Self-Documentation** — The `docs/` directory is auto-indexed into the knowledge base on startup, so Ember can answer questions about its own platform.

### Changed

- **Sidebar Navigation** — Redesigned with collapsible grouped sections (Content & Data, AI Configuration, Security & Access, Operations, Help & Guides) and left-bar accent indicators.
- **LLM Configuration** — Refactored from a single page into a tabbed layout with Providers, Model Routing, and Embedding tabs.
- **Catalog Tags** — Migrated from a JSON column on systems to a proper join-table architecture with CRUD endpoints.
- **Context Enrichment** — Now accepts a `settings_repo` parameter for runtime-configurable timeouts and top-k values.
- **DeskConfig.max_knowledge_tokens** — Deprecated in favor of `LLMRuntimeSettings.max_knowledge_tokens` (DB-backed, admin-tunable).
- **Dev Tools** — Webhooks page restructured into separate Callbacks and Dev Tools pages with tunnel wizard.

### Fixed

- Silent exception swallowing replaced with diagnostic logging (`logger.debug(..., exc_info=True)`) across 8 Python modules.
- Removed 12 unnecessary `type: ignore` suppressions by adding proper None guards and assertions.
- `rowcount` type safety across 4 repository modules (now `result.rowcount or 0`).
- Malformed date filters in audit logger now log warnings instead of failing silently.
- Frontend silent catch blocks in `settings.ts` and `user.ts` now include `console.error`.
- Large document handling across all LLM content paths with configurable truncation.
- Context truncation budgets prevent 429 rate-limit errors from oversized prompts.
- Session cookie name consistency across all environments.
- Test assertions tightened to catch truncation regressions.

## [0.1.0] — Initial Release

### Added

- **Core Platform** — FastAPI async backend with hexagonal architecture, SvelteKit frontend with Tailwind CSS.
- **Conversational Agent** — Ember, a purpose-built AI agent with Pydantic AI, streaming SSE responses, multi-turn conversations, and tool execution.
- **Service Catalog** — Registry for external systems and API endpoints with risk levels, permissions, and natural-language usage guidance.
- **Knowledge Base** — Document ingestion with chunking, embedding, RAG retrieval, and knowledge graph extraction.
- **Process Discovery** — LLM-driven business process identification from systems, endpoints, and knowledge documents.
- **RBAC** — 20 permissions across 7 domains with 3 built-in roles (Administrator, Operator, Viewer) and custom role support.
- **Audit Trail** — Append-only audit logger with PII sanitization for all agent actions and administrative operations.
- **Export System** — CSV, JSON, and PDF exports with configurable templates.
- **SSO/OIDC** — Authentication with Keycloak, Google, Microsoft Entra ID, Auth0, Cognito, and Okta.
- **Widget System** — 19 interactive chat widget types for rendering structured data.
- **File Uploads** — Multi-format upload with content extraction (PDF, DOCX, XLSX, PPTX, images).
- **Credential Vault** — AES-encrypted storage for API keys, OAuth secrets, and bearer tokens.
- **Setup Wizard** — 12-step guided configuration for first-time setup.
- **Agent Customization** — Configurable name, personality, tone, greeting, behavior rules, and custom instructions.
- **User Memory** — Per-user memory system for persistent context across conversations.
- **Custom Tools** — User-defined tools with sandboxed code execution.
- **OpenAPI Import** — Auto-register systems and endpoints from OpenAPI specifications.
- **Web Search** — Tavily integration for real-time internet search.
- **Git Import** — Import knowledge documents from GitHub, GitLab, and Bitbucket repositories.
- **Document Sources** — Cloud storage integration (S3, Azure Blob, GCS, OneDrive, SharePoint, Google Drive).
