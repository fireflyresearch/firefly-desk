---
type: tutorial
---

# System Catalog

The System Catalog is the registry of external systems and API endpoints that the AI agent can call on behalf of users. It defines what integrations are available, how to authenticate, and what operations are permitted.

## External Systems

A system represents a single external service (e.g., your CRM, ERP, or internal API). Each system entry includes:

- **Name and description** -- Human-readable identifier shown to the agent and in the admin UI.
- **Base URL** -- The root URL for all endpoints (e.g., `https://api.example.com/v2`).
- **Authentication config** -- How to authenticate: none, API key, bearer token, OAuth2, basic auth, or mutual TLS.
- **Health check path** -- Optional endpoint the platform pings to monitor availability.
- **Agent enabled** -- Toggle whether the agent is allowed to use this system.
- **Status** -- Lifecycle state: draft, active, disabled, deprecated, or degraded.

Status transitions follow a defined workflow: draft can become active; active can be disabled, deprecated, or marked degraded; deprecated is a terminal state.

## Service Endpoints

Each system contains one or more endpoints representing individual API operations. Endpoint configuration includes:

- **Method and path** -- HTTP method (GET, POST, PUT, PATCH, DELETE) and the relative path.
- **Parameters** -- Path parameters, query parameters, and request body schema.
- **Response schema** -- Expected response structure for the agent to interpret results.
- **When to use** -- Natural-language description that helps the agent decide when to call this endpoint.
- **Risk level** -- Categorized as read, low_write, high_write, or destructive. Higher risk operations require explicit user confirmation.
- **Protocol** -- REST (default), GraphQL, SOAP, or gRPC.
- **Rate limits and timeouts** -- Protect external systems from excessive calls.
- **Required permissions** -- RBAC permissions a user must hold to trigger this endpoint.

## Adding Systems

The catalog provides a unified wizard with multiple ways to add systems:

- **Curl import** -- Paste a curl command to auto-generate a system and endpoint. The parser extracts the method, URL, headers, query parameters, and body.
- **Upload docs** -- Upload API documentation files to populate system definitions.
- **Detect from KB** -- Select knowledge base documents and let the discovery engine identify systems and endpoints.
- **Manual** -- Fill out the system and endpoint forms directly.
- **OpenAPI import** -- Import an OpenAPI specification to auto-register all paths, methods, parameters, and schemas.

## Credential Mapping

Credential mappings control how authentication values are injected into API requests. Each mapping specifies a source credential field, a target location (header, query parameter, path parameter, or body parameter), the field name, and an optional transform (base64, prefix). This supports APIs that require authentication in places other than HTTP headers.

## System Tags

Tags are managed from the **Tags** tab in the catalog. Tags are shared across all systems and provide a consistent vocabulary for categorization and filtering. To associate tags with a system, use the system detail view.

## System Documents

You can link knowledge base documents to a system from the system detail view. Linked documents give the agent additional context about the system when it interacts with that integration -- for example, runbooks, API guides, or operational procedures.

## Tabbed Layout

The catalog interface is organized into four tabs:

- **Systems** -- Browse, create, and edit systems and endpoints.
- **Discovery** -- Run the system discovery engine, optionally providing knowledge documents as input.
- **Tags** -- Manage the tag vocabulary.
- **Import** -- Add systems using the unified wizard (curl, upload, KB detect, manual).

## Tips

- Write clear "when to use" descriptions -- this is the primary signal the agent uses to select the right endpoint.
- Start with read-only endpoints at the `read` risk level, then add write operations once you trust the workflow.
- Use tags to group related systems and endpoints for easier management.
- Set realistic timeouts; the default is 30 seconds per endpoint call.
