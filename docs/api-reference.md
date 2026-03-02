---
type: api_spec
---

# API Reference

## Overview

The Firefly Desk backend exposes a REST API over HTTP. All endpoints return JSON unless otherwise noted. The API is organized around the platform's core domains: health and setup, authentication, chat, service catalog, credentials, knowledge base, knowledge graph, roles, exports, files, audit, LLM providers, OIDC providers, settings, users, and the admin dashboard. Authentication is enforced in production mode via OIDC bearer tokens; in development mode, all requests are attributed to a synthetic development user.

All endpoints are served under the `/api` prefix. The FastAPI application generates an OpenAPI specification automatically, accessible at `/docs` (Swagger UI) or `/openapi.json` when the server is running.

## Health and Setup

### GET /api/health

Returns the current health status of the application and its version. This endpoint is unauthenticated and suitable for use as a readiness probe in container orchestration systems.

**Response:** `{"status": "healthy", "version": "0.1.0"}`

### GET /api/setup/status

Returns the current setup status of the platform, including whether the database is initialized, whether seed data is present, and whether required configuration is complete. This endpoint helps frontend applications determine what onboarding steps to display.

**Response:** `SetupStatus` object with fields describing each setup dimension.

### POST /api/setup/seed

Triggers the data seeding process. Accepts a seed scenario name in the request body. The `banking` scenario populates the catalog with a sample banking system, endpoints, and knowledge documents.

**Response:** `SeedResult` with counts of created systems, endpoints, and documents.

### GET /api/setup/first-run

Returns whether this is the first time the application has been started, which the frontend uses to determine whether to show the onboarding wizard.

**Response:** `{"is_first_run": true}` or `{"is_first_run": false}`

## Authentication

### GET /api/auth/login

Initiates the OIDC authentication flow. Redirects the user to the configured identity provider's authorization endpoint. In development mode, this endpoint is not needed because authentication is bypassed.

### GET /api/auth/callback

Handles the OIDC callback after the identity provider authenticates the user. Exchanges the authorization code for tokens, extracts user information, roles, and permissions from the JWT, and establishes the user session.

### POST /api/auth/logout

Terminates the current user session and optionally triggers a logout at the identity provider.

### GET /api/auth/me

Returns the authenticated user's profile, including their ID, display name, email, roles, and permissions. In development mode, returns the synthetic development user with admin privileges.

**Response:**
```json
{
  "id": "user-id",
  "display_name": "User Name",
  "email": "user@example.com",
  "roles": ["admin"],
  "permissions": ["*"]
}
```

## Chat

### POST /api/chat/conversations/{conversation_id}/send

Sends a user message to the agent and returns the response as a Server-Sent Events (SSE) stream. The `conversation_id` path parameter identifies the conversation context. If the conversation does not exist, it is created automatically.

The response stream emits typed events:

- **token** -- A text chunk from the agent's response. Clients concatenate these to build the full response.
- **widget** -- A parsed widget directive with a `type` field and a `data` JSON payload.
- **tool_start** -- Emitted when the agent begins invoking a tool. Includes the tool name and parameters.
- **tool_end** -- Emitted when a tool invocation completes. Includes the result or error.
- **confirmation** -- Emitted when the agent requires user confirmation before executing a risky action. Includes the confirmation ID, tool name, risk level, and parameters.
- **error** -- Emitted when an error occurs during processing.
- **done** -- Signals the end of the response stream. Clients should close the connection after receiving this event.

**Content-Type:** `text/event-stream`

### POST /api/chat/conversations/{conversation_id}/confirm/{confirmation_id}

Approves a pending safety confirmation, allowing the agent to proceed with the gated tool execution. Returns the tool execution result.

### POST /api/chat/conversations/{conversation_id}/reject/{confirmation_id}

Rejects a pending safety confirmation. The gated tool call is cancelled and the agent is informed that the user declined the action.

### GET /api/chat/conversations

Returns all conversations for the authenticated user, ordered by last activity.

### GET /api/chat/conversations/{conversation_id}

Returns a single conversation including its message history.

### POST /api/chat/conversations

Creates a new conversation.

### DELETE /api/chat/conversations/{conversation_id}

Deletes a conversation and its message history.

## Service Catalog

### POST /api/catalog/systems

Registers a new external system in the catalog. The request body includes the system name, description, base URL, authentication configuration, and other metadata.

**Required permission:** `catalog:write`

**Response:** `201 Created` with the created system object.

### GET /api/catalog/systems

Returns all registered external systems. Supports filtering by tags and status via query parameters.

**Required permission:** `catalog:read`

### GET /api/catalog/systems/{system_id}

Returns a single external system by its unique identifier, including its full configuration and metadata.

**Required permission:** `catalog:read`

### PUT /api/catalog/systems/{system_id}

Updates an existing external system's configuration. All mutable fields can be updated.

**Required permission:** `catalog:write`

### DELETE /api/catalog/systems/{system_id}

Removes an external system and all of its associated endpoints from the catalog. This is a destructive operation; the system's endpoints will no longer be available to the agent.

**Required permission:** `catalog:delete`

**Response:** `204 No Content`

### POST /api/catalog/systems/{system_id}/endpoints

Registers a new service endpoint under the specified system. The request body includes the endpoint name, HTTP method, path, parameters, risk level, and other configuration.

**Required permission:** `catalog:write`

**Response:** `201 Created` with the created endpoint object.

### GET /api/catalog/systems/{system_id}/endpoints

Returns all endpoints registered under the specified system.

**Required permission:** `catalog:read`

### GET /api/catalog/endpoints/{endpoint_id}

Returns a single endpoint by its unique identifier, regardless of which system it belongs to. This endpoint is useful when you have an endpoint ID from an audit log or tool invocation record and need to look up its details.

**Required permission:** `catalog:read`

### DELETE /api/catalog/endpoints/{endpoint_id}

Removes a service endpoint from the catalog.

**Required permission:** `catalog:delete`

**Response:** `204 No Content`

## Credentials

### GET /api/credentials

Returns all stored credentials. Sensitive values such as secrets and tokens are redacted in the response; only metadata and identifiers are returned.

**Required permission:** `credentials:read`

### POST /api/credentials

Creates a new credential entry. The request body includes the credential name, authentication type, and the secret values. Secrets are encrypted at rest immediately upon receipt.

**Required permission:** `credentials:write`

**Response:** `201 Created`

### PUT /api/credentials/{credential_id}

Updates an existing credential. Used for credential rotation. The new secret values replace the previous ones, and all systems referencing this credential automatically use the updated values.

**Required permission:** `credentials:write`

### DELETE /api/credentials/{credential_id}

Deletes a credential. Systems that reference this credential will fail to authenticate until a replacement is configured.

**Required permission:** `credentials:write`

**Response:** `204 No Content`

## Knowledge Base

### GET /api/knowledge/documents

Returns all knowledge documents with their metadata, including title, source, document type, tags, and chunk count. Document content may be truncated in list responses for performance.

**Required permission:** `knowledge:read`

### GET /api/knowledge/documents/{document_id}

Returns a single knowledge document with its full content and metadata.

**Required permission:** `knowledge:read`

### POST /api/knowledge/documents

Adds a new knowledge document. The document is immediately chunked, embedded, and indexed for retrieval. The request body includes the title, full content, document type, source identifier, and tags.

**Required permission:** `knowledge:write`

**Response:** `201 Created` with an `IndexResult` containing the document ID and the number of chunks generated.

### PUT /api/knowledge/documents/{document_id}

Updates metadata for an existing knowledge document (title, document type, tags). Content updates require deleting and re-creating the document to trigger re-indexing.

**Required permission:** `knowledge:write`

### DELETE /api/knowledge/documents/{document_id}

Removes a knowledge document and all of its associated chunks and embeddings from the index.

**Required permission:** `knowledge:delete`

**Response:** `204 No Content`

### POST /api/knowledge/import/url

Imports a document from a URL. The importer fetches the content, converts HTML to markdown if needed, auto-detects the document type, and indexes the result.

**Required permission:** `knowledge:write`

**Request body:**
```json
{
  "url": "https://wiki.internal.com/procedures/ach-failures",
  "title": "ACH Failure Procedures",
  "document_type": "manual",
  "tags": ["payments", "procedures"]
}
```

### POST /api/knowledge/import/file

Imports a document from an uploaded file. Supports text, markdown, HTML, JSON, and YAML files. The content is extracted, converted as needed, and indexed.

**Required permission:** `knowledge:write`

## Knowledge Graph

### GET /api/knowledge/graph/entities

Returns all entities in the knowledge graph.

**Required permission:** `knowledge:read`

### GET /api/knowledge/graph/entities/{entity_id}

Returns a single entity with its properties.

**Required permission:** `knowledge:read`

### GET /api/knowledge/graph/entities/{entity_id}/neighbors

Returns entities connected to the specified entity, including the relationship types and directions.

**Required permission:** `knowledge:read`

### POST /api/knowledge/graph/entities

Creates a new entity in the knowledge graph.

**Required permission:** `knowledge:write`

### DELETE /api/knowledge/graph/entities/{entity_id}

Removes an entity and all of its relationships from the knowledge graph.

**Required permission:** `knowledge:delete`

### POST /api/knowledge/graph/relationships

Creates a new relationship between two entities.

**Required permission:** `knowledge:write`

## Roles

### GET /api/admin/roles

Returns all roles including built-in and custom roles.

**Required permission:** `admin:roles`

### GET /api/admin/roles/{role_id}

Returns a single role with its full permission list.

**Required permission:** `admin:roles`

### POST /api/admin/roles

Creates a new custom role with the specified permissions.

**Required permission:** `admin:roles`

**Response:** `201 Created`

### PUT /api/admin/roles/{role_id}

Updates a custom role's display name, description, or permissions. Built-in roles cannot be modified.

**Required permission:** `admin:roles`

### DELETE /api/admin/roles/{role_id}

Deletes a custom role. Built-in roles cannot be deleted.

**Required permission:** `admin:roles`

**Response:** `204 No Content`

## Exports

### POST /api/exports

Creates a new export job. Accepts the export format (csv, json, pdf), source data, title, and optional template ID. The export is generated asynchronously and the response includes the export record with its status.

**Required permission:** `exports:create`

**Request body:**
```json
{
  "format": "csv",
  "title": "Transaction Report",
  "source_data": {
    "columns": ["Date", "Amount", "Status"],
    "rows": [["2026-01-15", "$500", "completed"]]
  },
  "template_id": null
}
```

### GET /api/exports

Returns all exports for the authenticated user, ordered by creation date.

**Required permission:** `exports:create`

### GET /api/exports/{export_id}

Returns a single export record with its status, file information, and metadata.

**Required permission:** `exports:create`

### GET /api/exports/{export_id}/download

Downloads the generated export file. Returns the file content with the appropriate content type header.

**Required permission:** `exports:download`

### DELETE /api/exports/{export_id}

Deletes an export record and its associated file.

**Required permission:** `exports:delete`

### GET /api/exports/templates

Returns all available export templates.

**Required permission:** `exports:templates`

### POST /api/exports/templates

Creates a new export template with column mappings, header text, and footer text.

**Required permission:** `exports:templates`

### DELETE /api/exports/templates/{template_id}

Deletes an export template. System templates cannot be deleted.

**Required permission:** `exports:templates`

## Files

### POST /api/files/upload

Uploads a file. The file is stored on the configured storage backend and its content is extracted for text-based formats. Returns the file record with metadata.

**Response:** `201 Created` with the file record including ID, filename, content type, file size, and extracted text preview.

### GET /api/files/{file_id}

Returns a file record with its metadata, including extracted content.

### GET /api/files/{file_id}/download

Downloads the original file. Returns the file content with the original content type.

### DELETE /api/files/{file_id}

Deletes a file and its stored content.

**Response:** `204 No Content`

## Audit

### GET /api/audit/events

Queries the audit trail. Supports the following query parameters:

| Parameter | Type | Description |
|-----------|------|-------------|
| `user_id` | str | Filter events by user identifier. |
| `event_type` | str | Filter by event type (e.g., `chat_turn`, `tool_invocation`, `admin_action`). |
| `limit` | int | Maximum number of events to return. Default: 50. |

**Required permission:** `audit:read`

Events are returned in reverse chronological order. Each event includes the timestamp, user identity, event type, and a detail payload whose schema varies by event type. Chat turn events include the full message, enriched context, and response. Tool invocation events include the tool name, parameters, and result. Administrative events include the action taken and the affected resource.

## LLM Providers

### GET /api/admin/llm-providers

Returns all configured LLM provider entries.

**Required permission:** `admin:llm`

### POST /api/admin/llm-providers

Registers a new LLM provider configuration. API keys are encrypted at rest.

**Required permission:** `admin:llm`

### PUT /api/admin/llm-providers/{provider_id}

Updates an LLM provider configuration.

**Required permission:** `admin:llm`

### DELETE /api/admin/llm-providers/{provider_id}

Removes an LLM provider configuration.

**Required permission:** `admin:llm`

## Model Routing

### GET /api/admin/model-routing

Returns the current model routing configuration. If no configuration has been saved, returns the default configuration (routing disabled).

**Required permission:** `admin:llm`

**Response:**
```json
{
  "enabled": false,
  "classifier_model": null,
  "default_tier": "balanced",
  "tier_mappings": {},
  "updated_at": null
}
```

### PUT /api/admin/model-routing

Updates the model routing configuration. Changes take effect within 60 seconds (the config cache TTL).

**Required permission:** `admin:llm`

**Request body:**
```json
{
  "enabled": true,
  "classifier_model": "gpt-4o-mini",
  "default_tier": "balanced",
  "tier_mappings": {
    "fast": "gpt-4o-mini",
    "balanced": "gpt-4o",
    "powerful": "claude-sonnet-4-20250514"
  }
}
```

### POST /api/admin/model-routing/test

Tests the classifier with a sample message. Requires routing to be enabled.

**Required permission:** `admin:llm`

**Request body:**
```json
{
  "message": "Hello, how are you?",
  "tool_count": 5,
  "tool_names": ["search", "lookup"]
}
```

## OIDC Providers

### GET /api/admin/oidc-providers

Returns all configured OIDC provider entries.

**Required permission:** `admin:sso`

### POST /api/admin/oidc-providers

Registers a new OIDC provider configuration. Client secrets are encrypted at rest.

**Required permission:** `admin:sso`

### PUT /api/admin/oidc-providers/{provider_id}

Updates an OIDC provider configuration.

**Required permission:** `admin:sso`

### DELETE /api/admin/oidc-providers/{provider_id}

Removes an OIDC provider configuration.

**Required permission:** `admin:sso`

## Settings

### GET /api/admin/settings

Returns the current application settings.

**Required permission:** `admin:settings`

### PUT /api/admin/settings

Updates application settings.

**Required permission:** `admin:settings`

## Users

### GET /api/admin/users

Returns all user accounts with their roles and status.

**Required permission:** `admin:users`

### GET /api/admin/users/{user_id}

Returns a single user account with full details.

**Required permission:** `admin:users`

### PUT /api/admin/users/{user_id}

Updates a user account, including role assignments.

**Required permission:** `admin:users`

## Memory

### GET /api/memory

Returns all saved memories for the authenticated user. Memories are user-scoped; each user can only access their own memories.

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `category` | string | No | Filter by category: `general`, `preference`, `fact`, `workflow` |

**Response:** Array of memory objects, each containing `id`, `user_id`, `content`, `category`, `source`, `created_at`, and `updated_at`.

### DELETE /api/memory/{memory_id}

Deletes a specific memory. Only the owning user can delete their memories.

**Response:** `204 No Content`

### PATCH /api/memory/{memory_id}

Updates a memory's content or category. Only the owning user can update their memories.

**Request body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | No | New content (1--5000 characters) |
| `category` | string | No | New category: `general`, `preference`, `fact`, `workflow` |

**Response:** The updated memory object.

## Agent Tools

### Built-in Tools

The agent has access to built-in tools that operate on internal platform data. The following tools are always available:

| Tool | Risk Level | Permission | Description |
|------|-----------|------------|-------------|
| `search_knowledge` | READ | `knowledge:read` | Search the knowledge base by natural language query |
| `list_catalog_systems` | READ | `catalog:read` | List all registered external systems |
| `list_system_endpoints` | READ | `catalog:read` | List available endpoints for a specific system |
| `search_processes` | READ | `knowledge:read` | Search discovered business processes |
| `query_audit_log` | READ | `audit:read` | Retrieve recent audit trail events |
| `get_platform_status` | READ | None | Return platform health and status summary |
| `document_read` | READ | `knowledge:read` | Read a knowledge document by ID |
| `document_convert` | READ | `knowledge:read` | Convert document content between formats |
| `document_create` | LOW_WRITE | `knowledge:write` | Create a new knowledge document |
| `document_modify` | LOW_WRITE | `knowledge:write` | Modify an existing knowledge document |
| `save_memory` | LOW_WRITE | None (user-scoped) | Save important information about the user for future reference |
| `recall_memories` | READ | None (user-scoped) | Search the user's saved memories for relevant information |

### Memory Tools

The `save_memory` and `recall_memories` tools enable the agent to remember information about users across conversations. These tools are always available because memories are scoped to the authenticated user and do not require special permissions.

**save_memory** accepts a `content` string (required) and an optional `category` (defaults to `general`). The agent uses this tool when a user shares preferences, facts about themselves, or workflow details worth remembering.

**recall_memories** accepts a `query` string and returns up to 10 matching memories sorted by recency. The agent uses this tool during context enrichment and when the user asks about previously shared information.

## Dashboard

### GET /api/admin/dashboard/stats

Returns aggregated platform statistics including total conversations, tool invocations, active users, system health, and recent activity metrics.

**Required permission:** `admin:dashboard`
