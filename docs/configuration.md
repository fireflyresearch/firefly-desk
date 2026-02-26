# Configuration

## Overview

Firefly Desk is configured entirely through environment variables, following the twelve-factor app methodology. Every configuration variable uses the `FLYDESK_` prefix to avoid collisions with other applications in the same environment. This prefix convention also makes it straightforward to audit which environment variables belong to Firefly Desk in container orchestration systems where dozens of variables may be present.

All variables can be set in a `.env` file at the project root. The application loads this file automatically on startup. For production deployments, prefer setting variables through your orchestration platform's secrets management rather than committing a `.env` file.

## Mode

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_DEV_MODE` | bool | `true` | Controls whether the application runs in development or production mode. |

Development mode disables OIDC authentication, uses a synthetic development user, and relaxes several security constraints to make local development frictionless. Setting this to `false` activates authentication enforcement, rate limiting, and production logging. This single flag exists because toggling individual security features independently would create an error-prone matrix of configurations that is difficult to reason about.

## Database

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_DATABASE_URL` | str | `sqlite+aiosqlite:///flydesk_dev.db` | Async SQLAlchemy database connection URL. |
| `FLYDESK_REDIS_URL` | str or None | `None` | Redis connection URL for caching and rate limiting. |

The database URL determines which database backend the application uses. SQLite is the default because it requires no installation and is sufficient for development and small-scale deployments. For production, PostgreSQL with the asyncpg driver is recommended. The URL format follows SQLAlchemy conventions: `postgresql+asyncpg://user:password@host:port/dbname`.

Redis is optional in development mode. When provided, it enables distributed rate limiting and session caching, which are essential for multi-instance production deployments where in-memory state is not shared across processes.

**Example production configuration:**

```bash
FLYDESK_DATABASE_URL=postgresql+asyncpg://flydesk_user:strong_password@db-host:5432/flydesk
FLYDESK_REDIS_URL=redis://redis-host:6379/0
```

## OIDC Authentication

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_OIDC_ISSUER_URL` | str | -- | The issuer URL of your OIDC provider (e.g., `https://keycloak.example.com/realms/myorg`). |
| `FLYDESK_OIDC_CLIENT_ID` | str | -- | The client ID registered with your OIDC provider. |
| `FLYDESK_OIDC_CLIENT_SECRET` | str | -- | The client secret for confidential client authentication. |
| `FLYDESK_OIDC_SCOPES` | list | `openid,profile,email,roles` | Comma-separated list of OIDC scopes to request during authentication. |
| `FLYDESK_OIDC_REDIRECT_URI` | str | `http://localhost:3000/auth/callback` | The callback URI registered with your OIDC provider. |
| `FLYDESK_OIDC_ROLES_CLAIM` | str | `roles` | The JWT claim name that contains the user's roles. |
| `FLYDESK_OIDC_PERMISSIONS_CLAIM` | str | `permissions` | The JWT claim name that contains the user's fine-grained permissions. |
| `FLYDESK_OIDC_PROVIDER_TYPE` | str | `keycloak` | The OIDC provider type, used for provider-specific claim mapping. Supported values: `keycloak`, `google`, `microsoft`, `auth0`, `cognito`, `okta`. |
| `FLYDESK_OIDC_TENANT_ID` | str | -- | Tenant or realm identifier, required by some providers (e.g., Microsoft Entra ID). |

OIDC variables are only required when `FLYDESK_DEV_MODE=false`. The roles and permissions claims are configurable because different identity providers use different claim names. Keycloak uses `realm_access.roles`, Auth0 uses a custom namespace, and Entra ID uses `roles`. By making these configurable, Firefly Desk works with any standards-compliant provider without code changes.

**Example Keycloak configuration:**

```bash
FLYDESK_OIDC_ISSUER_URL=https://keycloak.example.com/realms/operations
FLYDESK_OIDC_CLIENT_ID=firefly-desk
FLYDESK_OIDC_CLIENT_SECRET=your-client-secret
FLYDESK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDESK_OIDC_ROLES_CLAIM=realm_access.roles
FLYDESK_OIDC_PERMISSIONS_CLAIM=resource_access.firefly-desk.roles
FLYDESK_OIDC_PROVIDER_TYPE=keycloak
```

See the [SSO and OIDC](sso-oidc.md) documentation for detailed configuration guides for each supported provider.

## CORS

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_CORS_ORIGINS` | list | `http://localhost:3000,http://localhost:5173` | Comma-separated list of allowed CORS origins. |

The default origins cover the two most common local development scenarios: the SvelteKit dev server on port 5173 and a production build served on port 3000. In production, restrict this to your actual frontend domain to prevent cross-origin attacks.

**Example production configuration:**

```bash
FLYDESK_CORS_ORIGINS=https://desk.example.com
```

## Agent

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_AGENT_NAME` | str | `Ember` | The display name of the conversational agent. |
| `FLYDESK_AGENT_INSTRUCTIONS` | str or None | `None` | Optional custom system instructions appended to the prompt. |
| `FLYDESK_MAX_TURNS_PER_CONVERSATION` | int | `200` | Maximum number of turns allowed in a single conversation. |
| `FLYDESK_MAX_TOOLS_PER_TURN` | int | `10` | Maximum number of tool invocations the agent can make in a single turn. |

The agent name defaults to "Ember," which includes a carefully designed personality and behavioral profile. If you override the agent name, the system uses a generic professional identity instead. The turn and tool limits exist as safety guardrails to prevent runaway conversations or excessive API calls against registered systems.

## Analysis

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_AUTO_ANALYZE` | bool | `false` | Enable automatic process discovery and KG recomputation when data changes. |

When auto-analyze is enabled, data change events (new knowledge documents, catalog system updates) automatically trigger background jobs for knowledge graph recomputation and process discovery. Rapid changes are debounced with a 5-second window to prevent redundant work.

This setting can also be toggled at runtime through the API (`PUT /api/settings/analysis`) or the setup wizard, in which case the database value takes precedence over the environment variable.

## Agent Customization

Agent customization settings (name, personality, tone, greeting, behavior rules, custom instructions, language) are stored in the database rather than environment variables. This allows changes to take effect immediately without restarting the application.

The following environment variables serve as initial defaults that are overridden once settings are saved to the database:

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_AGENT_NAME` | str | `Ember` | Initial agent name (overridden by DB settings). |
| `FLYDESK_AGENT_INSTRUCTIONS` | str or None | `None` | Initial custom instructions (overridden by DB settings). |

For full details on all customizable fields and how to configure them, see the [Agent Customization](agent-customization.md) documentation.

## User Memory

The User Memory system stores user-specific memories in the existing application database. No additional configuration is required. Memories are created through the agent's `save_memory` tool and managed through the `/api/memory` endpoints or the **Settings > Memories** page. See the [User Memory](user-memory.md) documentation for details.

## Background Jobs

The background job system runs automatically and requires no configuration. Jobs are submitted by internal services (process discovery, KG recomputation, knowledge indexing) and executed by the built-in `JobRunner`. Job status and history are available through the `GET /api/jobs` endpoint.

## Knowledge

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_EMBEDDING_MODEL` | str | `openai:text-embedding-3-small` | The embedding model used for knowledge document vectorization. |
| `FLYDESK_EMBEDDING_DIMENSIONS` | int | `1536` | The dimensionality of the embedding vectors. |
| `FLYDESK_RAG_TOP_K` | int | `3` | Number of document chunks to retrieve during RAG. |
| `FLYDESK_KG_MAX_ENTITIES_IN_CONTEXT` | int | `5` | Maximum number of knowledge graph entities included in context enrichment. |

The RAG top-k value controls the balance between context richness and prompt token usage. A higher value provides more context but increases token consumption and may dilute the relevance of retrieved passages. The default of 3 has been chosen as a practical balance for most operational documentation.

### Knowledge Quality

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_CHUNK_SIZE` | int | `500` | Maximum characters per document chunk. Smaller values increase precision; larger values preserve more context. |
| `FLYDESK_CHUNK_OVERLAP` | int | `50` | Character overlap between adjacent chunks to prevent sentence boundary loss. |
| `FLYDESK_CHUNKING_MODE` | str | `auto` | Chunking strategy: `fixed` (character-based), `structural` (heading/section-aware), or `auto` (selects based on content). |
| `FLYDESK_AUTO_KG_EXTRACT` | bool | `true` | Automatically extract knowledge graph entities and relationships when documents are indexed. |

The `auto` chunking mode inspects document structure: if headings or sections are detected, it uses structural chunking that respects document boundaries; otherwise it falls back to fixed-size chunking. Structural chunking produces more semantically coherent chunks, which improves retrieval quality for well-structured documents like runbooks and API references.

These settings can also be configured through the setup wizard or the admin console, in which case database values take precedence over environment variables.

## Security

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` | str | -- | AES encryption key for stored system credentials and provider secrets. |
| `FLYDESK_AUDIT_RETENTION_DAYS` | int | `365` | Number of days to retain audit log entries. |
| `FLYDESK_RATE_LIMIT_PER_USER` | int | `60` | Maximum API requests per user per minute. |

The credential encryption key is critical for production deployments. All credentials stored in the Credential Vault, including API keys, OAuth secrets, bearer tokens for external systems, and OIDC provider secrets, are encrypted at rest using this key. If the key is lost, all stored credentials become unrecoverable and must be re-entered. Generate a strong key and store it in your secrets manager.

**Generating an encryption key:**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## File Uploads

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_FILE_STORAGE_PATH` | str | `./uploads` | Directory path where uploaded files are stored. |
| `FLYDESK_FILE_MAX_SIZE_MB` | int | `50` | Maximum allowed file upload size in megabytes. |

The file storage path should be an absolute path in production deployments to avoid ambiguity. Ensure the application process has read and write permissions to this directory. For multi-instance deployments, use a shared filesystem or object storage.

**Example production configuration:**

```bash
FLYDESK_FILE_STORAGE_PATH=/data/flydesk/uploads
FLYDESK_FILE_MAX_SIZE_MB=100
```

## Branding

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `FLYDESK_APP_TITLE` | str | `Firefly Desk` | The application title displayed in the UI header and browser tab. |
| `FLYDESK_APP_LOGO_URL` | str or None | `None` | URL to a custom logo image. |
| `FLYDESK_ACCENT_COLOR` | str | `#2563EB` | Primary accent color used throughout the UI. |

Branding variables allow organizations to white-label Firefly Desk without modifying frontend code. The accent color propagates through the CSS custom properties system, affecting buttons, links, and interactive elements consistently across all views.

**Example white-label configuration:**

```bash
FLYDESK_APP_TITLE=ACME Operations Console
FLYDESK_APP_LOGO_URL=https://cdn.acme.com/logo.svg
FLYDESK_ACCENT_COLOR=#10B981
```

## Complete Production Example

The following `.env` file shows a complete production configuration:

```bash
# Mode
FLYDESK_DEV_MODE=false

# Database
FLYDESK_DATABASE_URL=postgresql+asyncpg://flydesk_user:strong_password@db-host:5432/flydesk
FLYDESK_REDIS_URL=redis://redis-host:6379/0

# OIDC Authentication
FLYDESK_OIDC_ISSUER_URL=https://keycloak.example.com/realms/operations
FLYDESK_OIDC_CLIENT_ID=firefly-desk
FLYDESK_OIDC_CLIENT_SECRET=your-client-secret
FLYDESK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDESK_OIDC_ROLES_CLAIM=realm_access.roles
FLYDESK_OIDC_PROVIDER_TYPE=keycloak

# CORS
FLYDESK_CORS_ORIGINS=https://desk.example.com

# Security
FLYDESK_CREDENTIAL_ENCRYPTION_KEY=your-generated-256-bit-key
FLYDESK_AUDIT_RETENTION_DAYS=365
FLYDESK_RATE_LIMIT_PER_USER=60

# Knowledge
FLYDESK_EMBEDDING_MODEL=openai:text-embedding-3-small
FLYDESK_RAG_TOP_K=5

# Analysis
FLYDESK_AUTO_ANALYZE=true

# File Uploads
FLYDESK_FILE_STORAGE_PATH=/data/flydesk/uploads
FLYDESK_FILE_MAX_SIZE_MB=100

# Branding
FLYDESK_APP_TITLE=Operations Desk
FLYDESK_ACCENT_COLOR=#2563EB
```
