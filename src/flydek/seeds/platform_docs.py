# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Platform documentation seed data for the knowledge base."""

from __future__ import annotations

import logging

from flydek.knowledge.models import KnowledgeDocument

logger = logging.getLogger(__name__)

PLATFORM_DOCUMENTS: list[KnowledgeDocument] = [
    # -- overview ----------------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-overview",
        title="Firefly Desk Overview",
        content=(
            "Firefly Desk is a conversational backoffice platform designed to"
            " fundamentally change how operations teams interact with their backend"
            " systems. Rather than requiring operators to navigate through multiple"
            " admin panels, memorize API endpoints, or context-switch between"
            " dashboards, Firefly Desk consolidates all of these interactions into a"
            " single, natural-language interface. The core idea is simple but"
            " powerful: if an operator can describe what they need, the platform"
            " should be able to do it.\n\n"
            "This concept, which we call \"Backoffice as Agent,\" replaces the"
            " traditional model of point-and-click administration with a"
            " conversational paradigm. Operations teams no longer need specialized"
            " training on each individual system's interface. Instead, they"
            " communicate their intent in plain language, and the platform translates"
            " that intent into the precise API calls, queries, and actions required"
            " to fulfill it. This approach dramatically reduces onboarding time for"
            " new team members, eliminates the cognitive overhead of managing"
            " multiple tools, and creates a single audit trail for all"
            " administrative actions.\n\n"
            "At the heart of Firefly Desk is Ember, the built-in conversational"
            " agent. Ember is not a generic chatbot; it is purpose-built for"
            " operational work. Ember understands the systems your organization has"
            " registered, knows which endpoints are available, respects user"
            " permissions, and can present structured data through an integrated"
            " widget system directly within the chat interface.\n\n"
            "Ember's personality is warm but professional. It communicates in short,"
            " clear sentences without unnecessary filler. When Ember does not know"
            " something or lacks access to a requested system, it says so directly"
            " rather than guessing. This design choice reflects a core principle of"
            " Firefly Desk: in operations work, accuracy and honesty are more"
            " important than appearing helpful. Every action Ember takes is logged in"
            " an immutable audit trail, providing the accountability that enterprise"
            " environments require.\n\n"
            "Key features of Firefly Desk include:\n\n"
            "- Service Catalog: A registry of external systems and API endpoints"
            " with descriptions, risk levels, and usage guidance that Ember uses for"
            " tool resolution.\n"
            "- Knowledge Base: Operational documents, runbooks, and policies indexed"
            " for semantic retrieval, complemented by a knowledge graph for"
            " relational reasoning.\n"
            "- Safety Safeguards: Risk-level classification for every endpoint with"
            " mandatory confirmation flows for high-risk and destructive"
            " operations.\n"
            "- RBAC: A granular permission system with 20 discrete permissions"
            " across seven domains, enforced at both the API and agent layers.\n"
            "- Export System: CSV, JSON, and PDF export generation with reusable"
            " templates for consistent output formatting.\n"
            "- SSO/OIDC: Authentication through any OIDC-compliant identity"
            " provider, with configurable claim mapping for roles and"
            " permissions.\n"
            "- File Uploads: Users can upload files into conversations, with"
            " automatic content extraction for text-based formats.\n"
            "- Audit Trail: An immutable record of every conversation, tool"
            " invocation, and administrative action.\n"
            "- Widget System: Rich, interactive components rendered within the chat"
            " interface for structured data display."
        ),
        source="platform-docs://overview",
        tags=["platform", "documentation", "overview"],
        metadata={"document_type": "PLATFORM_DOCS", "section": "overview"},
    ),
    # -- knowledge-base ----------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-knowledge-base",
        title="Firefly Desk Knowledge Base",
        content=(
            "The Knowledge Base gives Ember access to operational documentation,"
            " runbooks, policies, and domain-specific information that is not"
            " available through the Service Catalog's structured API metadata. While"
            " the Service Catalog tells Ember what actions it can perform, the"
            " Knowledge Base tells Ember how things work, why they work that way,"
            " and what procedures to follow in specific situations.\n\n"
            "Document Types\n\n"
            "Every knowledge document is classified with a document type:\n"
            "- manual: Operational manuals and runbooks with step-by-step"
            " procedures.\n"
            "- tutorial: Instructional guides and how-to documentation.\n"
            "- api_spec: API specifications, service contracts, and integration"
            " documentation.\n"
            "- faq: Frequently asked questions and troubleshooting checklists.\n"
            "- policy: Organizational policies, compliance rules, and governance"
            " documents.\n"
            "- reference: Architecture diagrams, data dictionaries, and"
            " configuration guides.\n"
            "- other: Uncategorized documents.\n\n"
            "Adding Documents\n\n"
            "Documents can be added through several methods:\n\n"
            "1. Manual creation via the API or Admin Console by providing a title,"
            " content, document type, and tags.\n"
            "2. URL import: The Knowledge Importer fetches content from a URL,"
            " automatically converts HTML to clean markdown, and detects the"
            " document type from the URL structure. OpenAPI specifications are"
            " detected and parsed into structured API reference documents.\n"
            "3. File upload: Files can be uploaded and their text content extracted"
            " for indexing.\n\n"
            "Chunking and Indexing\n\n"
            "Documents are split into chunks of 500 characters with 50-character"
            " overlap. Each chunk is embedded using the configured embedding model"
            " (default: openai:text-embedding-3-small with 1536 dimensions) and"
            " stored for similarity search. Indexing happens synchronously, so"
            " documents are searchable immediately after submission.\n\n"
            "Knowledge Graph\n\n"
            "The Knowledge Graph captures structured relationships between entities."
            " While vector search finds documents that sound similar to a query, the"
            " knowledge graph answers \"what is related to X\" through explicit"
            " entity-to-entity connections. The Admin Console includes a Graph"
            " Explorer that visualizes entities and relationships as an interactive"
            " force-directed graph powered by D3.\n\n"
            "Context Enrichment\n\n"
            "During each conversation turn, two retrieval processes run in parallel:"
            " Knowledge Graph retrieval traverses entity relationships, and RAG"
            " retrieval performs vector similarity search. Results are merged and"
            " injected into the agent's system prompt as authoritative context."
        ),
        source="platform-docs://knowledge-base",
        tags=[
            "platform",
            "documentation",
            "knowledge-base",
            "rag",
            "embeddings",
            "graph",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "knowledge-base"},
    ),
    # -- rbac-security -----------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-rbac-security",
        title="Firefly Desk RBAC and Security",
        content=(
            "Firefly Desk enforces security at multiple layers through role-based"
            " access control, safety safeguards, credential encryption, and audit"
            " logging.\n\n"
            "RBAC Model\n\n"
            "The system uses a permission-based RBAC model with 20 discrete"
            " permissions across seven domains: knowledge (read, write, delete),"
            " catalog (read, write, delete), chat (send), exports (create, download,"
            " delete, templates), audit (read), credentials (read, write), and"
            " administration (users, settings, roles, SSO, LLM, dashboard).\n\n"
            "Three built-in roles are provided:\n\n"
            "- Administrator: Wildcard (*) permission granting full access. Bypasses"
            " high_write confirmation but not destructive confirmation.\n"
            "- Operator: Read access to knowledge and catalog, write access to"
            " catalog, create and download exports, chat access, and audit"
            " reading.\n"
            "- Viewer: Read-only access to knowledge, catalog, and chat.\n\n"
            "Custom roles can be created through the Role Manager in the admin"
            " console or via the API.\n\n"
            "Permission Enforcement\n\n"
            "Permissions are enforced at two layers: the API middleware rejects"
            " unauthorized requests before they reach the route handler, and the"
            " agent's tool resolution layer filters available tools based on the"
            " user's permissions. This dual enforcement ensures security does not"
            " depend solely on the LLM following instructions.\n\n"
            "Safety Safeguards\n\n"
            "Every endpoint is classified by risk level:\n"
            "- read: No side effects. Executes freely.\n"
            "- low_write: Limited impact. Executes with logging.\n"
            "- high_write: Significant modification. Requires user confirmation"
            " (admin with wildcard bypasses).\n"
            "- destructive: Irreversible operations. Always requires confirmation.\n\n"
            "The ConfirmationService intercepts high-risk tool calls before"
            " execution and sends a confirmation request to the frontend. The user"
            " must explicitly approve or reject the action. Pending confirmations"
            " expire after 5 minutes.\n\n"
            "Credential Encryption\n\n"
            "All credentials stored in the Credential Vault, LLM provider API keys,"
            " and OIDC provider secrets are encrypted at rest using the"
            " FLYDEK_CREDENTIAL_ENCRYPTION_KEY. Credentials are decrypted only at"
            " the moment of use and are never logged or cached in plaintext.\n\n"
            "Audit System\n\n"
            "Every conversation turn, tool invocation, confirmation decision, and"
            " administrative action is recorded in an append-only audit trail."
            " Records include timestamps, user identities, and full detail payloads."
            " The trail is retained for FLYDEK_AUDIT_RETENTION_DAYS (default: 365)."
        ),
        source="platform-docs://rbac-security",
        tags=[
            "platform",
            "documentation",
            "rbac",
            "security",
            "permissions",
            "safety",
            "audit",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "rbac-security"},
    ),
    # -- export-system -----------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-export-system",
        title="Firefly Desk Export System",
        content=(
            "The export system allows users to extract structured data from Firefly"
            " Desk conversations into standard file formats for reporting,"
            " compliance, or integration with other tools.\n\n"
            "Supported Formats\n\n"
            "- CSV: Comma-separated values with a header row. Best for"
            " spreadsheets.\n"
            "- JSON: Pretty-printed array of objects. Best for programmatic"
            " processing.\n"
            "- PDF: Formatted HTML table with header and footer. Requires"
            " weasyprint for true PDF output; falls back to HTML if unavailable.\n\n"
            "Creating Exports\n\n"
            "Exports can be created through the API (POST /api/exports), through"
            " the agent in conversation (ask Ember to export data), or through the"
            " Export Manager in the admin console. Source data accepts two formats:"
            " table format ({\"columns\": [...], \"rows\": [...]}) or list-of-dicts"
            " format ({\"items\": [{...}, ...]}).\n\n"
            "Export Lifecycle\n\n"
            "Each export progresses through: pending, generating, completed, or"
            " failed. Completed exports are stored and available for download until"
            " deleted.\n\n"
            "Export Templates\n\n"
            "Templates define reusable formatting configurations with column"
            " mappings (rename and filter columns), header text, and footer text."
            " They ensure consistent output when the same type of data is exported"
            " regularly. System templates cannot be deleted.\n\n"
            "Permissions\n\n"
            "The export system uses four permissions: exports:create, exports:download,"
            " exports:delete, and exports:templates. Administrators have all four."
            " Operators have create and download. Viewers have none."
        ),
        source="platform-docs://export-system",
        tags=[
            "platform",
            "documentation",
            "exports",
            "csv",
            "json",
            "pdf",
            "templates",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "export-system"},
    ),
    # -- sso-oidc ----------------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-sso-oidc",
        title="Firefly Desk SSO and OIDC",
        content=(
            "Firefly Desk authenticates users through OpenID Connect (OIDC)."
            " Any OIDC-compliant identity provider can be used, including Keycloak,"
            " Google, Microsoft Entra ID, Auth0, Amazon Cognito, and Okta.\n\n"
            "Authentication is only enforced when FLYDEK_DEV_MODE=false. In"
            " development mode, the platform uses a synthetic admin user.\n\n"
            "Authentication Flow\n\n"
            "1. User clicks Sign In.\n"
            "2. Redirected to the identity provider.\n"
            "3. User authenticates with the provider.\n"
            "4. Provider redirects back with an authorization code.\n"
            "5. Backend exchanges the code for tokens.\n"
            "6. Roles and permissions are extracted from JWT claims.\n"
            "7. Session is established.\n\n"
            "Claim Mapping\n\n"
            "The FLYDEK_OIDC_ROLES_CLAIM and FLYDEK_OIDC_PERMISSIONS_CLAIM"
            " variables specify the dot-path to roles and permissions arrays in the"
            " JWT. Different providers use different structures:\n"
            "- Keycloak: realm_access.roles\n"
            "- Auth0: https://your-domain.com/roles (custom namespace)\n"
            "- Microsoft Entra ID: roles (top-level)\n"
            "- Okta: groups\n"
            "- Cognito: cognito:groups\n"
            "- Google: does not provide roles natively\n\n"
            "Provider Configuration\n\n"
            "The FLYDEK_OIDC_PROVIDER_TYPE variable selects provider-specific"
            " handling. Supported values: keycloak, google, microsoft, auth0,"
            " cognito, okta. Each provider requires its issuer URL, client ID,"
            " client secret, and redirect URI.\n\n"
            "OIDC providers can also be configured through the SSO Manager in the"
            " admin console at /admin/sso, which provides pre-configured templates"
            " for common providers.\n\n"
            "Troubleshooting\n\n"
            "If users authenticate but have no permissions, decode the JWT at"
            " jwt.io and verify the roles claim path matches the"
            " FLYDEK_OIDC_ROLES_CLAIM value. Use GET /api/auth/me to see what"
            " roles the system extracted from the token."
        ),
        source="platform-docs://sso-oidc",
        tags=[
            "platform",
            "documentation",
            "sso",
            "oidc",
            "authentication",
            "keycloak",
            "auth0",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "sso-oidc"},
    ),
    # -- file-uploads ------------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-file-uploads",
        title="Firefly Desk File Uploads",
        content=(
            "Firefly Desk supports file uploads directly within conversations."
            " Uploaded files are stored on the server and their content is extracted"
            " for text-based formats, making the text available to Ember as"
            " additional context.\n\n"
            "Supported Formats with Content Extraction\n\n"
            "- Plain text (.txt)\n"
            "- Markdown (.md)\n"
            "- HTML (.html)\n"
            "- JSON (.json)\n"
            "- YAML (.yaml, .yml)\n"
            "- CSV (.csv)\n\n"
            "Binary formats (PDF, Word, images, archives) are stored and available"
            " for download but their content is not automatically extracted.\n\n"
            "Uploading Files\n\n"
            "Files can be uploaded through drag-and-drop onto the chat area, the"
            " file picker button in the input bar, or via the API (POST"
            " /api/files/upload with multipart/form-data). Files are uploaded"
            " immediately and associated with the conversation turn.\n\n"
            "Content Extraction\n\n"
            "For supported text-based formats, the ContentExtractor processes the"
            " file and extracts textual content during upload. HTML is converted to"
            " plain text preserving structure. JSON is pretty-printed. The extracted"
            " text is stored alongside the file record and provided to Ember when"
            " the file is referenced in conversation.\n\n"
            "Chat Integration\n\n"
            "When files are uploaded in a conversation, Ember can read their"
            " extracted content, answer questions about the file, analyze data in"
            " CSV or JSON files, and compare content across multiple files.\n\n"
            "Configuration\n\n"
            "FLYDEK_FILE_STORAGE_PATH (default: ./uploads) controls where files are"
            " stored. FLYDEK_FILE_MAX_SIZE_MB (default: 50) sets the maximum file"
            " size. Use an absolute path in production."
        ),
        source="platform-docs://file-uploads",
        tags=[
            "platform",
            "documentation",
            "file-uploads",
            "files",
            "content-extraction",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "file-uploads"},
    ),
    # -- service-catalog ---------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-service-catalog",
        title="Firefly Desk Service Catalog",
        content=(
            "The Service Catalog is the registry of all external systems that"
            " Firefly Desk can interact with. It exists because the agent needs"
            " structured, machine-readable metadata about each system and endpoint"
            " in order to determine which API calls to make, what parameters to"
            " provide, and what level of risk a particular action carries.\n\n"
            "External Systems\n\n"
            "An external system represents a backend service or API. Each system"
            " record contains: a unique ID, name, description, base URL,"
            " authentication configuration, health check path, tags, status"
            " (active/degraded/offline), and metadata. The description field is"
            " critical because Ember uses it during tool resolution.\n\n"
            "Service Endpoints\n\n"
            "Each system contains one or more endpoints representing specific API"
            " operations. Endpoint fields include: name, HTTP method, path,"
            " parameter schema, when_to_use guidance, examples, risk level"
            " (read/low_write/high_write/destructive), required permissions, rate"
            " limit, and timeout settings.\n\n"
            "The when_to_use field is injected into the agent's prompt to guide"
            " tool selection. Writing effective when_to_use instructions is one of"
            " the most impactful things an administrator can do to improve the"
            " agent's accuracy.\n\n"
            "Authentication Methods\n\n"
            "Five methods are supported: oauth2 (client credentials or auth code"
            " flow), api_key (static key as header/query), basic (username and"
            " password), bearer (static token), and mutual_tls (client"
            " certificates). Credentials are stored in the encrypted Credential"
            " Vault and referenced by ID.\n\n"
            "Risk Levels\n\n"
            "- read: No side effects. Agent invokes freely.\n"
            "- low_write: Limited impact. Logged prominently.\n"
            "- high_write: Significant modification. Requires user confirmation.\n"
            "- destructive: Irreversible. Always requires confirmation.\n\n"
            "Risk levels are enforced at the platform level. Even if the LLM"
            " attempts to invoke a destructive endpoint without confirmation, the"
            " execution layer blocks the call."
        ),
        source="platform-docs://service-catalog",
        tags=[
            "platform",
            "documentation",
            "service-catalog",
            "endpoints",
            "systems",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "service-catalog"},
    ),
    # -- architecture ------------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-architecture",
        title="Firefly Desk Architecture",
        content=(
            "Firefly Desk is built on hexagonal architecture (ports and adapters)."
            " Core business logic never depends on specific infrastructure"
            " technologies. Ports define capabilities as protocols, adapters provide"
            " concrete implementations.\n\n"
            "Agent Pipeline\n\n"
            "Every message passes through a six-stage pipeline:\n\n"
            "1. Context Enrichment: Knowledge Graph and RAG retrieval run in"
            " parallel to gather relevant context.\n"
            "2. Prompt Assembly: SystemPromptBuilder constructs the prompt from"
            " modular sections (identity, user context, tools, widgets,"
            " guidelines, knowledge, history).\n"
            "3. LLM Execution: Model-agnostic execution layer.\n"
            "4. Safety Check: Risk-level evaluation and confirmation gating for"
            " high_write and destructive operations.\n"
            "5. Post-Processing: WidgetParser extracts widget directives from the"
            " response.\n"
            "6. SSE Streaming: Response delivered via Server-Sent Events with typed"
            " events (token, widget, tool_start, tool_end, confirmation, error,"
            " done).\n\n"
            "Audit logging captures every stage for accountability.\n\n"
            "Knowledge Architecture\n\n"
            "Two complementary layers: a vector store for semantic similarity"
            " search and a knowledge graph for relational reasoning. Combined, they"
            " handle both \"what sounds like X\" and \"what is related to X\""
            " queries.\n\n"
            "Dependency Injection\n\n"
            "All components are wired through FastAPI's dependency_overrides during"
            " the application lifespan. Configuration determines which adapters to"
            " instantiate (SQLite vs PostgreSQL, no-op vs real embeddings).\n\n"
            "Technology Stack\n\n"
            "Backend: FastAPI, SQLAlchemy 2 (async), Python 3.13. Frontend:"
            " SvelteKit, Svelte 5 (runes), Tailwind CSS 4, D3 for graph"
            " visualization. Development: SQLite, no external services. Production:"
            " PostgreSQL 16 + pgvector, Redis 7, any OIDC provider."
        ),
        source="platform-docs://architecture",
        tags=["platform", "documentation", "architecture", "hexagonal", "pipeline"],
        metadata={"document_type": "PLATFORM_DOCS", "section": "architecture"},
    ),
    # -- configuration -----------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-configuration",
        title="Firefly Desk Configuration",
        content=(
            "Firefly Desk is configured via environment variables with the FLYDEK_"
            " prefix, or a .env file at the project root.\n\n"
            "Mode: FLYDEK_DEV_MODE (default: true) -- development mode disables"
            " auth, uses SQLite, and a synthetic user.\n\n"
            "Database: FLYDEK_DATABASE_URL (default:"
            " sqlite+aiosqlite:///flydek_dev.db), FLYDEK_REDIS_URL (optional).\n\n"
            "OIDC (required when dev_mode=false): FLYDEK_OIDC_ISSUER_URL,"
            " FLYDEK_OIDC_CLIENT_ID, FLYDEK_OIDC_CLIENT_SECRET,"
            " FLYDEK_OIDC_SCOPES (default: openid,profile,email,roles),"
            " FLYDEK_OIDC_REDIRECT_URI (default:"
            " http://localhost:3000/auth/callback), FLYDEK_OIDC_ROLES_CLAIM"
            " (default: roles), FLYDEK_OIDC_PERMISSIONS_CLAIM (default:"
            " permissions), FLYDEK_OIDC_PROVIDER_TYPE (default: keycloak),"
            " FLYDEK_OIDC_TENANT_ID.\n\n"
            "CORS: FLYDEK_CORS_ORIGINS (default:"
            " http://localhost:3000,http://localhost:5173).\n\n"
            "Agent: FLYDEK_AGENT_NAME (default: Ember),"
            " FLYDEK_AGENT_INSTRUCTIONS, FLYDEK_MAX_TURNS_PER_CONVERSATION"
            " (default: 200), FLYDEK_MAX_TOOLS_PER_TURN (default: 10).\n\n"
            "Knowledge: FLYDEK_EMBEDDING_MODEL (default:"
            " openai:text-embedding-3-small), FLYDEK_EMBEDDING_DIMENSIONS"
            " (default: 1536), FLYDEK_RAG_TOP_K (default: 3),"
            " FLYDEK_KG_MAX_ENTITIES_IN_CONTEXT (default: 5).\n\n"
            "Security: FLYDEK_CREDENTIAL_ENCRYPTION_KEY,"
            " FLYDEK_AUDIT_RETENTION_DAYS (default: 365),"
            " FLYDEK_RATE_LIMIT_PER_USER (default: 60).\n\n"
            "File Uploads: FLYDEK_FILE_STORAGE_PATH (default: ./uploads),"
            " FLYDEK_FILE_MAX_SIZE_MB (default: 50).\n\n"
            "Branding: FLYDEK_APP_TITLE (default: Firefly Desk),"
            " FLYDEK_APP_LOGO_URL, FLYDEK_ACCENT_COLOR (default: #2563EB)."
        ),
        source="platform-docs://configuration",
        tags=[
            "platform",
            "documentation",
            "configuration",
            "environment-variables",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "configuration"},
    ),
    # -- safety-safeguards -------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-safety-safeguards",
        title="Firefly Desk Safety Safeguards",
        content=(
            "Firefly Desk enforces safety safeguards to prevent accidental or"
            " unauthorized destructive actions when the agent executes tool calls"
            " against external systems.\n\n"
            "Risk Level Classification\n\n"
            "Every endpoint in the Service Catalog is classified with a risk"
            " level:\n\n"
            "- read: Information retrieval only. No side effects. Executes"
            " without confirmation.\n"
            "- low_write: Creates or modifies data with limited, easily"
            " reversible impact. Executes without confirmation but is logged"
            " prominently.\n"
            "- high_write: Significant data modification that may be difficult"
            " to reverse. Requires explicit user confirmation before execution."
            " Users with the wildcard (*) admin permission bypass this"
            " requirement.\n"
            "- destructive: Irreversible operations such as deletions, account"
            " closures, or data purges. Always requires explicit user"
            " confirmation, regardless of the user's permissions.\n\n"
            "Confirmation Flow\n\n"
            "When the agent resolves a tool call for a high_write or destructive"
            " endpoint, the ConfirmationService intercepts the call before"
            " execution. A confirmation request is sent to the frontend as a"
            " confirmation SSE event, which renders a ConfirmationCard widget"
            " displaying the tool name, parameters, and risk level. The user"
            " can approve or reject the action.\n\n"
            "Only after explicit approval does the platform execute the tool"
            " call. This enforcement is at the platform level, independent of"
            " the LLM's behavior.\n\n"
            "Confirmation Rules\n\n"
            "- Pending confirmations expire after 5 minutes (300 seconds).\n"
            "- Maximum 10 confirmations can be pending simultaneously per"
            " conversation.\n"
            "- Expired confirmations are automatically evicted.\n"
            "- If the maximum is exceeded, the oldest pending confirmation is"
            " evicted.\n\n"
            "Safety Plan Cards\n\n"
            "For complex multi-step operations, the agent can present a"
            " SafetyPlanCard widget that outlines the complete plan before"
            " execution begins, giving the user visibility into the full scope"
            " of the operation."
        ),
        source="platform-docs://safety-safeguards",
        tags=[
            "platform",
            "documentation",
            "safety",
            "confirmation",
            "risk-levels",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "safety-safeguards"},
    ),
    # -- admin-console -----------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-admin-console",
        title="Firefly Desk Admin Console",
        content=(
            "The Admin Console is the graphical management interface for Firefly"
            " Desk, accessible through the sidebar navigation. It requires the"
            " admin role.\n\n"
            "Admin Dashboard (/admin): Platform health overview with statistics"
            " on conversations, tool invocations, active users, and system"
            " health.\n\n"
            "Catalog Manager (/admin/catalog): Register and configure external"
            " systems and endpoints. Every new system registered here immediately"
            " becomes available to Ember.\n\n"
            "Credential Vault (/admin/credentials): Manage encrypted credentials"
            " for external system authentication. Supports OAuth2, API key,"
            " basic, bearer, and mutual TLS.\n\n"
            "Knowledge Base Manager (/admin/knowledge): Three tabs -- Documents"
            " (view, edit, delete), Add Document (manual entry, URL import, file"
            " upload), and Graph Explorer (interactive D3 visualization of"
            " entity relationships).\n\n"
            "Role Manager (/admin/roles): View and manage RBAC roles. Built-in"
            " roles (Administrator, Operator, Viewer) are protected. Custom"
            " roles can be created with arbitrary permission combinations.\n\n"
            "User Manager (/admin/users): View user accounts and manage role"
            " assignments.\n\n"
            "Export Manager (/admin/exports): View all exports, download files,"
            " manage export templates with column mappings, headers, and"
            " footers.\n\n"
            "SSO Manager (/admin/sso): Configure OIDC identity providers with"
            " pre-configured templates for Keycloak, Google, Microsoft, Auth0,"
            " Cognito, and Okta.\n\n"
            "LLM Provider Manager (/admin/llm-providers): Configure language"
            " model provider API keys.\n\n"
            "Audit Viewer (/admin/audit): Searchable interface for the audit"
            " trail with filtering by user, event type, and date range.\n\n"
            "Settings (/admin/settings): Runtime configuration for branding and"
            " operational parameters."
        ),
        source="platform-docs://admin-console",
        tags=[
            "platform",
            "documentation",
            "admin-console",
            "catalog-manager",
            "credential-vault",
            "knowledge-manager",
            "role-manager",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "admin-console"},
    ),
    # -- troubleshooting ---------------------------------------------------
    KnowledgeDocument(
        id="doc-platform-troubleshooting",
        title="Firefly Desk Troubleshooting",
        content=(
            "Backend Will Not Start\n\n"
            "Verify Python 3.13+ with python --version. Run uv sync to install"
            " dependencies. Check FLYDEK_DATABASE_URL for connection errors. For"
            " PostgreSQL, verify the server is running and the pgvector extension"
            " is installed.\n\n"
            "Frontend Cannot Reach the API\n\n"
            "Verify FLYDEK_CORS_ORIGINS includes the frontend's origin. The match"
            " is exact: http://localhost:5173 is not http://127.0.0.1:5173. Check"
            " that the backend is running on port 8000.\n\n"
            "OIDC Authentication Failures\n\n"
            "Callback failures: Verify FLYDEK_OIDC_REDIRECT_URI exactly matches"
            " the provider's configuration. Missing roles: Verify"
            " FLYDEK_OIDC_ROLES_CLAIM matches the JWT structure. Decode tokens at"
            " jwt.io to inspect. Common claim paths: Keycloak"
            " (realm_access.roles), Auth0 (https://domain.com/roles), Microsoft"
            " (roles), Okta (groups), Cognito (cognito:groups).\n\n"
            "Export Issues\n\n"
            "Stuck exports: Check backend logs for errors. PDF fallback: Install"
            " weasyprint system dependencies for true PDF. File not found on"
            " download: Verify FLYDEK_FILE_STORAGE_PATH is consistent across"
            " instances.\n\n"
            "Knowledge Base Issues\n\n"
            "Documents not in search: Verify chunk count is non-zero. In dev"
            " mode, the no-op embedding provider produces zero vectors. URL"
            " import failures: Check network connectivity and SSL certificates."
            " Graph entities missing relationships: Relationships must be"
            " explicitly created via the API.\n\n"
            "RBAC Issues\n\n"
            "Missing features: Check role permissions in the Role Manager."
            " Permission denied with correct role: Verify OIDC claim parsing"
            " with GET /api/auth/me. Custom role changes require a new session"
            " (log out and log back in).\n\n"
            "File Upload Issues\n\n"
            "Size errors: Increase FLYDEK_FILE_MAX_SIZE_MB. Empty extraction:"
            " Only text-based formats are extracted. Permission errors: Ensure"
            " FLYDEK_FILE_STORAGE_PATH exists and is writable.\n\n"
            "Widget Rendering\n\n"
            "If widgets show as raw text, check the directive format:"
            " :::widget{type=\"...\" panel=true} followed by JSON and closing"
            " :::. Supported types: status-badge, entity-card, data-table,"
            " confirmation, key-value, alert, diff-viewer, timeline, export,"
            " safety-plan."
        ),
        source="platform-docs://troubleshooting",
        tags=[
            "platform",
            "documentation",
            "troubleshooting",
            "debugging",
            "errors",
        ],
        metadata={"document_type": "PLATFORM_DOCS", "section": "troubleshooting"},
    ),
]


async def seed_platform_docs(knowledge_indexer, catalog_repo=None) -> None:
    """Seed platform documentation into the knowledge base.

    Idempotent: checks for existing documents before indexing.
    """
    for doc in PLATFORM_DOCUMENTS:
        try:
            # Check if doc already exists (by checking via catalog_repo if available)
            if catalog_repo:
                existing = await catalog_repo.get_knowledge_document(doc.id)
                if existing is not None:
                    logger.debug("Platform doc %s already exists, skipping.", doc.id)
                    continue
            await knowledge_indexer.index_document(doc)
            logger.debug("Indexed platform doc: %s", doc.id)
        except Exception:
            # Document may already exist (duplicate key), skip silently
            logger.debug("Skipping platform doc %s (may already exist).", doc.id)
            continue
    logger.info(
        "Platform documentation seeding complete (%d documents).",
        len(PLATFORM_DOCUMENTS),
    )


async def unseed_platform_docs(knowledge_indexer) -> None:
    """Remove all platform documentation from the knowledge base."""
    for doc in PLATFORM_DOCUMENTS:
        try:
            await knowledge_indexer.delete_document(doc.id)
        except Exception:
            continue
    logger.info("Platform documentation removed.")
