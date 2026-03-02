---
type: reference
---

# Architecture

## Overview

Firefly Desk is structured around a **hexagonal architecture** (ports and adapters), where core business logic is expressed through Python Protocols and concrete implementations are wired at startup through dependency injection. This pattern was chosen because an AI agent platform has many integration surfaces -- LLM providers, embedding models, databases, external APIs, identity providers -- and each surface needs to be swappable without rewriting the business logic it connects to.

The application is async-first. Every I/O operation, from database queries to external HTTP calls to embedding generation, runs on Python's asyncio event loop. This is not an optimization afterthought; it is a structural requirement. A single agent turn may involve parallel knowledge retrieval, multiple tool calls, and streaming LLM output, all of which must proceed concurrently to keep response latency acceptable.

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Backend runtime | Python 3.13 | Modern type hints, performance improvements, async-native |
| Web framework | FastAPI | Async HTTP, dependency injection, auto-generated OpenAPI spec |
| ORM | SQLAlchemy (async) | Database abstraction with async session management |
| Migrations | Alembic | Schema versioning and incremental migration |
| Agent framework | Pydantic AI | LLM invocation, tool binding, structured output |
| Frontend | SvelteKit | Reactive UI with server-side rendering |
| Styling | Tailwind CSS | Utility-first CSS, consistent design system |
| Streaming | Server-Sent Events (SSE) | Real-time agent response delivery |
| Embedding storage | pgvector (PostgreSQL) | Vector similarity search within the relational database |
| Package management | uv | Deterministic, fast Python dependency resolution |

## Hexagonal Architecture

### Ports

Ports are Python `Protocol` classes that define what the system needs from its environment. They live in the domain layer and have no knowledge of concrete implementations. For example:

- `EmbeddingProvider` defines a method to generate vector embeddings from text.
- `CredentialStore` defines how credentials are retrieved and decrypted for external system calls.
- `VectorStore` defines similarity search operations against stored embeddings.

Protocols are `@runtime_checkable`, which means the system can verify at startup that an adapter actually satisfies its contract. This catches wiring mistakes early rather than at request time.

### Adapters

Adapters implement port contracts for specific technologies. The application ships with concrete adapters for:

- **LLMEmbeddingProvider** -- Generates embeddings via configurable LLM providers (OpenAI, etc.).
- **FernetKMSProvider** -- Encrypts and decrypts credentials using Fernet symmetric encryption.
- **CatalogCredentialStore** -- Resolves credentials from the catalog repository with KMS decryption.
- **LocalFileStorage** -- Stores uploaded files on the local filesystem.
- **PostgreSQLStore / InMemoryStore** -- Conversation memory backends for production and development.

Because adapters are injected through FastAPI's dependency override system, swapping an implementation requires changing one line in the lifespan initializer, not refactoring call sites throughout the codebase.

## Component Graph

The application's lifespan function in `server.py` orchestrates startup by delegating to focused `_init_*` helpers. Each helper creates a related group of services, wires FastAPI dependency overrides, and returns objects needed by later phases. The initialization order reflects real dependency relationships -- later phases consume what earlier phases produce.

### Phase 1: Database

`_init_database` creates the SQLAlchemy `AsyncEngine` and session factory. For PostgreSQL databases, the pgvector extension is enabled automatically. Database tables are created via `Base.metadata.create_all`.

**Produces:** `AsyncEngine`, `async_sessionmaker[AsyncSession]`

### Phase 2: Core Repositories

`_init_repositories` creates the foundational data access layer:

| Repository | Responsibility |
|-----------|---------------|
| `CatalogRepository` | External systems and endpoints |
| `AuditLogger` | Append-only audit trail |
| `ConversationRepository` | Chat conversations and messages |
| `WorkspaceRepository` | Multi-workspace isolation |
| `SettingsRepository` | Application settings (DB-backed) |
| `MemoryRepository` | User-scoped memories |
| `CustomToolRepository` | User-defined custom tools |
| `LLMProviderRepository` | LLM provider configurations (encrypted keys) |
| `RoleRepository` | Roles and permissions (seeds built-in roles) |
| `SandboxExecutor` | Sandboxed code execution for custom tools |

**Produces:** Named service references passed to later phases.

### Phase 3: File System and Exports

`_init_file_system` creates the file handling and export pipeline:

- `LocalFileStorage` -- Stores uploaded files on disk.
- `FileUploadRepository` -- Tracks file metadata in the database.
- `ContentExtractor` -- Extracts text content from uploaded files for indexing.
- `ExportRepository` and `ExportService` -- Generate and manage data exports (CSV, JSON, PDF).

### Phase 4: Security

`_init_security` creates the encryption and credential management layer:

- `KMSProvider` (Fernet) -- Symmetric encryption for stored secrets. In development mode with no configured key, a dev key is used with a warning.
- `CatalogCredentialStore` -- Resolves and decrypts credentials when the agent calls external systems.
- `CatalogDocumentStore` -- Manages knowledge document storage through the catalog layer.

### Phase 5: HTTP Client

A shared `httpx.AsyncClient` is created for all outbound HTTP calls. This shared client enables connection pooling and consistent timeout management across the application.

### Phase 6: Knowledge

`_init_knowledge` creates the embedding and indexing pipeline:

- `LLMEmbeddingProvider` -- Generates vector embeddings using the configured model (default: `openai:text-embedding-3-small`, 1536 dimensions).
- `KnowledgeIndexer` -- Orchestrates document chunking, embedding, and persistence. Chunking parameters (size, overlap, mode) are loaded from database settings, falling back to environment variable defaults.
- `VectorStore` -- Created via `create_vector_store` factory, selecting the appropriate implementation based on the database backend (pgvector for PostgreSQL, in-memory for SQLite).

### Phase 7: Background Jobs

`_init_jobs` creates the asynchronous job execution system:

- `JobRepository` -- Persists job records and status.
- `JobRunner` -- Executes jobs asynchronously with registered handlers. Handlers are registered for: `indexing`, `process_discovery`, `system_discovery`, `kg_recompute`, and `kg_extract_single`.
- `IndexingQueue` -- An internal task queue (in-memory or Redis-backed) that decouples document submission from indexing execution.

### Phase 8: Agent and Intelligence Layer

`_init_agent` is the largest initialization phase, assembling the full agent pipeline:

| Component | Responsibility |
|-----------|---------------|
| `KnowledgeGraph` | Entity and relationship storage, graph traversal |
| `KnowledgeRetriever` | Vector similarity search over document chunks |
| `ContextEnricher` | Parallel KG + RAG + memory retrieval for context enrichment |
| `SystemPromptBuilder` | Jinja2-based system prompt composition |
| `ToolFactory` | Generates tool definitions from catalog endpoints, filtered by user permissions |
| `WidgetParser` | Parses widget directives from agent output |
| `ToolExecutor` | Routes tool calls to external systems with credential injection and audit logging |
| `BuiltinToolExecutor` | Handles internal tools (knowledge search, audit queries, memory operations) |
| `DocumentToolExecutor` | Document read, create, modify, and convert operations |
| `ConfirmationService` | Intercepts high-risk tool calls, requires user approval |
| `ProcessDiscoveryEngine` | LLM-driven business process discovery |
| `SystemDiscoveryEngine` | LLM-driven system relationship discovery |
| `KGExtractor` | Extracts entities and relationships from text using LLM |
| `DocumentAnalyzer` | LLM-driven document analysis and classification |
| `AutoTriggerService` | Debounced auto-analysis on data change events |
| `AgentCustomizationService` | Loads and caches agent personality settings |
| `RoutingConfigRepository` | Database-backed routing config with 60-second in-memory cache |
| `ComplexityClassifier` | Classifies message complexity using a cheap LLM call |
| `ModelRouter` | Orchestrates classification, confidence thresholding, and tier-to-model mapping |
| `DeskAgentFactory` | Creates Pydantic AI agent instances with memory management |
| `DeskAgent` | Top-level orchestrator that ties the entire pipeline together |
| `MemoryManager` | Conversation memory with summarization and token management |

### Phase 9: Authentication

`_init_auth` creates the authentication and identity layer:

- `OIDCProviderRepository` -- Manages OIDC provider configurations (encrypted secrets).
- `GitProviderRepository` -- Manages Git provider configurations for knowledge import.
- `OIDCClient` -- Handles token exchange and validation with the configured identity provider.
- `LocalUserRepository` -- Manages local user accounts for environments without external OIDC.

### Phase 10: Platform Documentation

`_seed_platform_docs` uses `DocsLoader` to auto-index the `docs/` directory into the knowledge base. This means Ember can answer questions about its own platform documentation out of the box. The loader detects changes (new, updated, removed docs) to avoid redundant re-indexing on restart.

## Agent Pipeline

When a user sends a message, the platform processes it through a multi-stage pipeline. Understanding this pipeline is essential because it explains why the agent's responses are contextual, permission-aware, and auditable.

```
User Message
    |
    v
+-------------------+
| Context Enrichment | -- Parallel execution:
|   - Knowledge Graph |    KG traversal (entity neighbors)
|   - RAG retrieval   |    Vector similarity search (top-k chunks)
|   - Memory recall   |    User-scoped memory search
+-------------------+
    |
    v
+-------------------+
| Prompt Building    | -- Jinja2 templates compose:
|   - Agent profile  |    personality, tone, behavioral rules
|   - Enriched context|   KG entities, RAG chunks, memories
|   - Available tools |    filtered by user permissions
|   - Conversation   |    message history
+-------------------+
    |
    v
+-------------------+
| LLM Invocation     | -- Pydantic AI agent with tool bindings
+-------------------+
    |
    v  (may loop for multi-tool turns)
+-------------------+
| Tool Execution     | -- Routes to:
|   - External APIs  |    ToolExecutor (HTTP + credential injection)
|   - Internal tools |    BuiltinToolExecutor (search, audit, memory)
|   - Document ops   |    DocumentToolExecutor (read, create, modify)
|   - Confirmations  |    ConfirmationService (high_write, destructive)
+-------------------+
    |
    v
+-------------------+
| Response Streaming | -- SSE events:
|   - routing        |    model selection (when smart routing enabled)
|   - token          |    text chunks
|   - widget         |    structured UI directives
|   - tool_start/end |    execution status
|   - confirmation   |    approval requests
|   - done           |    stream complete
+-------------------+
```

Context enrichment runs its three retrieval strategies in parallel because they are independent and latency-sensitive. The merged results are deduplicated and formatted into a context section that the LLM treats as authoritative reference material.

The tool execution phase may iterate multiple times in a single turn. The LLM can request multiple tool calls, each of which is executed, and the results are fed back to the LLM for further reasoning. The `max_tools_per_turn` configuration (default: 10) prevents runaway loops.

## Middleware Stack

The FastAPI application applies middleware in the following order (outermost first):

### CORS Middleware

Configured through `FLYDESK_CORS_ORIGINS`. Defaults to `http://localhost:3000,http://localhost:5173` for development. In production, restrict this to your actual frontend domain. Credentials are always allowed to support cookie-based session management.

### Auth Middleware

In **development mode**, `DevAuthMiddleware` injects a synthetic development user with admin privileges on every request. This eliminates the need for an OIDC provider during local development.

In **production mode**, `AuthMiddleware` validates OIDC bearer tokens, extracts user identity, roles, and permissions from JWT claims, and rejects unauthorized requests. The middleware supports multiple OIDC providers (Keycloak, Auth0, Entra ID, Google, Okta, Cognito) through configurable claim mapping.

## API Surface

The application registers 30 routers, each responsible for a specific domain:

| Domain | Router | Key Endpoints |
|--------|--------|--------------|
| Health | `health_router` | `GET /api/health` |
| Setup | `setup_router` | `GET /api/setup/status`, `POST /api/setup/seed` |
| Auth | `auth_router` | `GET /api/auth/login`, `GET /api/auth/callback`, `GET /api/auth/me` |
| Chat | `chat_router` | `POST /api/chat/conversations/{id}/send` (SSE) |
| Conversations | `conversations_router` | CRUD for conversation records |
| Catalog | `catalog_router` | CRUD for systems and endpoints |
| Credentials | `credentials_router` | Encrypted credential management |
| Knowledge | `knowledge_router` | Documents, chunks, import, graph |
| Processes | `processes_router` | Process discovery and management |
| Exports | `exports_router` | CSV, JSON, PDF export generation |
| Files | `files_router` | File upload and download |
| Audit | `audit_router` | Audit trail query |
| Memory | `memory_router` | User-scoped memory CRUD |
| Jobs | `jobs_router` | Background job status |
| LLM Providers | `llm_providers_router` | LLM provider configuration |
| Model Routing | `model_routing_router` | Smart model routing configuration |
| OIDC Providers | `oidc_providers_router` | SSO provider configuration |
| Roles | `roles_router` | Role and permission management |
| Users | `users_router` | User account management |
| Settings | `settings_router` | Application settings |
| Dashboard | `dashboard_router` | Platform statistics |
| Custom Tools | `custom_tools_router` | User-defined tools |
| OpenAPI Import | `openapi_import_router` | Auto-register from OpenAPI specs |
| Prompts | `prompts_router` | Prompt template management |
| Git Import | `git_import_router` | Import knowledge from Git repos |
| Git Providers | `git_providers_router` | Git provider configuration |
| GitHub | `github_router` | GitHub-specific integration |
| SSO Mappings | `sso_mappings_router` | SSO role/permission mapping |
| Tools Admin | `tools_admin_router` | Tool configuration management |
| Workspaces | `workspace_router` | Multi-workspace management |
| Help Docs | `help_docs_router` | In-app help documentation |
| Feedback | `feedback_router` | User feedback on agent responses |
| LLM Status | `llm_status_router` | LLM provider health checks |

All endpoints are served under the `/api` prefix. The auto-generated OpenAPI specification is available at `/docs` (Swagger UI) or `/openapi.json` when the server is running.

## Data Flow Summary

Understanding how data flows through the system clarifies the role of each component:

**Knowledge ingestion:** Document submitted (API, import, file upload) -> `KnowledgeIndexer` chunks and embeds -> stored in database (text + vectors) -> `KGExtractor` optionally extracts entities/relationships -> `KnowledgeGraph` updated.

**Conversation turn:** User message -> `ContextEnricher` retrieves relevant context (parallel KG + RAG + memory) -> `SystemPromptBuilder` composes prompt with Jinja2 templates -> `ModelRouter` classifies complexity and selects model tier (if enabled) -> `DeskAgentFactory` creates Pydantic AI agent (with optional model override) -> LLM generates response -> `ToolExecutor` handles tool calls -> `WidgetParser` extracts widget directives -> SSE stream delivers response.

**Background processing:** Data change event -> `AutoTriggerService` debounces (5s window) -> `JobRunner` submits job -> handler executes (process discovery, KG recompute, etc.) -> results persisted.

## Design Decisions

### Why hexagonal architecture?

An AI agent platform integrates with LLM providers, embedding models, databases, vector stores, identity providers, and arbitrary external systems. Each of these is a moving target with frequent API changes, new providers, and evolving best practices. The hexagonal pattern isolates the core agent logic from these external concerns, making it possible to swap providers, add new adapters, or change infrastructure without modifying business logic.

### Why async-first?

A single agent turn may involve 3-5 parallel I/O operations (KG query, RAG query, memory search, LLM call, tool execution). Synchronous execution would serialize these operations, multiplying latency. Async-first design means the application naturally exploits parallelism where operations are independent, which is critical for acceptable response times in a conversational interface.

### Why pgvector instead of a standalone vector database?

Keeping embeddings in the same PostgreSQL database as application data provides transactional consistency (a document and its embeddings are always in sync), simpler backups (one database to back up), and fewer operational components to manage. For the scale of a typical backoffice deployment (tens of thousands of documents, not billions), pgvector performs well without the operational overhead of a separate vector database cluster.

### Why SSE instead of WebSocket?

Server-Sent Events are simpler than WebSocket for the unidirectional streaming pattern that agent responses require. The client sends a message via a normal HTTP POST, and the server streams the response back through SSE. This maps naturally onto HTTP/2 multiplexing, works through standard reverse proxies without special configuration, and requires no bidirectional state management.
