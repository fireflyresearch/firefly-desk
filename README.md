# Firefly Desk

**Backoffice as Agent** -- an AI-powered operational backoffice that replaces traditional admin panels with a single conversational interface.

Firefly Desk consolidates backend system management, operational knowledge, and administrative workflows into a natural-language interface powered by Ember, a purpose-built conversational agent. Operations teams describe what they need in plain language, and the platform translates their intent into the precise API calls, queries, and actions required to fulfill it.

## Key Features

**Knowledge Base with Knowledge Graph.** Documents are chunked, embedded, and indexed for semantic retrieval. A knowledge graph layer captures entity relationships, enabling Ember to answer questions that require both similarity search and relational reasoning. Documents can be added manually, imported from URLs (with automatic HTML-to-markdown conversion), or parsed from OpenAPI specifications.

**Service Catalog and Tool Execution.** External systems and their API endpoints are registered in a structured catalog with descriptions, parameter schemas, risk levels, and usage guidance. Ember automatically resolves user intent to the correct tool and executes API calls against registered systems, with full parameter validation and error handling.

**Safety Safeguards and Confirmation Flow.** Every endpoint is classified by risk level: `read`, `low_write`, `high_write`, or `destructive`. High-risk and destructive operations require explicit user confirmation before execution. The confirmation flow is enforced at the platform level, independent of the LLM's behavior, ensuring that dangerous operations cannot be executed without human approval.

**Export System.** Structured data from conversations can be exported to CSV, JSON, or PDF formats. Export templates allow administrators to define column mappings, headers, and footers for consistent output. All exports are tracked with full audit records.

**SSO and OIDC Authentication.** Production deployments authenticate users through any OpenID Connect compliant identity provider, including Keycloak, Google, Microsoft Entra ID, Auth0, Amazon Cognito, and Okta. Claim mapping is fully configurable to support provider-specific JWT structures.

**Role-Based Access Control.** A granular RBAC system with 20 discrete permissions across knowledge, catalog, chat, exports, audit, credentials, and administration domains. Three built-in roles (Administrator, Operator, Viewer) provide sensible defaults, and custom roles can be created through the admin interface. Permissions are enforced at both the API layer and the agent's tool resolution layer, providing defense-in-depth security.

**Audit Trail.** Every conversation turn, tool invocation, and administrative action is recorded with timestamps, user identities, and full request and response details. The audit trail is append-only and retained according to configurable retention policies.

**Widget System.** The agent can render structured data as interactive components within the chat interface, including data tables, entity cards, status badges, timelines, diff viewers, alert banners, export cards, and safety plan cards.

**File Uploads.** Users can upload files directly into conversations. Content is extracted from supported formats and made available to the agent as additional context.

## Architecture Overview

Firefly Desk follows hexagonal architecture (ports and adapters). The core business logic never depends on specific infrastructure technologies. Ports define capabilities as Python protocols, and adapters provide concrete implementations for specific backends.

```
User Message
    |
    v
[Context Enrichment] -- Knowledge Graph + RAG retrieval in parallel
    |
    v
[Prompt Assembly] -- Identity, tools, widgets, knowledge, history
    |
    v
[LLM Execution] -- Model-agnostic execution layer
    |
    v
[Safety Check] -- Risk-level evaluation, confirmation gating
    |
    v
[Post-Processing] -- Widget directive parsing
    |
    v
[Audit Logging] -- Immutable record of every action
    |
    v
[SSE Streaming] -- Typed events: token, widget, tool_start, tool_end, confirmation, done
```

The knowledge system combines two complementary layers: vector similarity search for semantic retrieval and a knowledge graph for relational reasoning. Both run in parallel during context enrichment to minimize latency.

## Quick Start

### Prerequisites

- Python 3.13 or later
- Node.js 20 or later
- [uv](https://github.com/astral-sh/uv) (Python package manager)

### Install and Run

```bash
# Clone the repository
git clone https://github.com/fireflyframework/firefly-desk.git
cd firefly-desk

# Copy the default environment configuration
cp .env.example .env

# Install Python dependencies
uv sync

# Start the backend server
uvicorn flydek.server:create_app --factory --port 8000
```

In a separate terminal:

```bash
# Install and start the frontend
cd frontend
npm install
npm run dev
```

### Seed Demo Data

```bash
# Populate the catalog with a sample banking system and knowledge documents
flydek-seed banking
```

### Open the Application

Navigate to `http://localhost:5173`. Ember will be ready to assist. Try asking "What systems are available?" or "Show me the endpoints for the banking system."

## Configuration Reference

All configuration uses environment variables with the `FLYDEK_` prefix, or a `.env` file at the project root.

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLYDEK_DEV_MODE` | `true` | Development mode (SQLite, no auth) |
| `FLYDEK_DATABASE_URL` | `sqlite+aiosqlite:///flydek_dev.db` | Database connection URL |
| `FLYDEK_REDIS_URL` | -- | Redis URL for caching and rate limiting |
| `FLYDEK_OIDC_ISSUER_URL` | -- | OIDC provider issuer URL |
| `FLYDEK_OIDC_CLIENT_ID` | -- | OIDC client identifier |
| `FLYDEK_OIDC_CLIENT_SECRET` | -- | OIDC client secret |
| `FLYDEK_OIDC_PROVIDER_TYPE` | `keycloak` | Provider type for claim mapping |
| `FLYDEK_AGENT_NAME` | `Ember` | Conversational agent display name |
| `FLYDEK_EMBEDDING_MODEL` | `openai:text-embedding-3-small` | Embedding model for knowledge indexing |
| `FLYDEK_CREDENTIAL_ENCRYPTION_KEY` | -- | Encryption key for stored credentials |
| `FLYDEK_FILE_STORAGE_PATH` | `./uploads` | File upload storage directory |
| `FLYDEK_FILE_MAX_SIZE_MB` | `50` | Maximum file upload size |
| `FLYDEK_AUDIT_RETENTION_DAYS` | `365` | Audit log retention period |
| `FLYDEK_RATE_LIMIT_PER_USER` | `60` | API requests per user per minute |

See [docs/configuration.md](docs/configuration.md) for the complete reference.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend framework | FastAPI (Python 3.13) |
| ORM | SQLAlchemy 2 (async) |
| Database (dev) | SQLite with aiosqlite |
| Database (prod) | PostgreSQL 16 with pgvector |
| Cache and rate limiting | Redis 7 |
| Authentication | OIDC (any compliant provider) |
| Frontend framework | SvelteKit with Svelte 5 (runes) |
| Styling | Tailwind CSS 4 |
| Graph visualization | D3 (d3-force, d3-selection) |
| Markdown rendering | Marked with DOMPurify |
| Package management | uv (Python), npm (frontend) |

## Project Structure

```
firefly-desk/
  src/flydek/              # Python backend
    agent/                 # Agent pipeline: context, prompt, confirmation
    api/                   # FastAPI route handlers
    audit/                 # Audit logging system
    auth/                  # OIDC authentication and middleware
    catalog/               # Service catalog domain
    conversation/          # Conversation persistence
    exports/               # Export service (CSV, JSON, PDF)
    files/                 # File upload and content extraction
    knowledge/             # Knowledge base: models, indexer, retriever, graph, importer
    llm/                   # LLM provider management
    models/                # SQLAlchemy ORM models
    rbac/                  # Role-based access control
    seeds/                 # Seed data (banking demo, platform docs)
    settings/              # Application settings
    tools/                 # Tool execution engine
    widgets/               # Widget directive parser
    config.py              # Pydantic Settings configuration
    server.py              # Application factory and DI wiring
  frontend/src/            # SvelteKit frontend
    lib/components/        # Svelte components (admin, chat, layout, widgets)
    lib/services/          # API client, SSE, auth services
    lib/stores/            # Svelte stores (chat, panel, user, theme)
    lib/widgets/           # Widget registry
    routes/                # SvelteKit file-based routing
  tests/                   # Backend test suite (pytest)
  docs/                    # Project documentation
```

## Documentation

- [Architecture](docs/architecture.md) -- Hexagonal design, agent pipeline, knowledge layers
- [Configuration](docs/configuration.md) -- All environment variables with explanations
- [Knowledge Base](docs/knowledge-base.md) -- Document types, import, graph exploration
- [Security](docs/security.md) -- RBAC model, permissions, safety safeguards, audit
- [Exports](docs/exports.md) -- Export formats, templates, API reference
- [SSO and OIDC](docs/sso-oidc.md) -- Setup guides per provider, claim mapping
- [File Uploads](docs/file-uploads.md) -- Upload system, supported formats, extraction
- [API Reference](docs/api-reference.md) -- All REST endpoints
- [Admin Console](docs/admin-console.md) -- Management interface guide
- [Troubleshooting](docs/troubleshooting.md) -- Common issues and solutions

## License

Copyright 2026 Firefly Software Solutions Inc.

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for details.
