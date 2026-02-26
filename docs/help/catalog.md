---
type: tutorial
---

# Catalog

The Catalog is the registry of external systems and API endpoints that the AI agent can call on behalf of users. It defines what integrations are available, how to authenticate, and what operations are permitted.

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

## OpenAPI Import

Instead of manually creating endpoints, you can import an OpenAPI specification. The parser extracts all paths, methods, parameters, and schemas automatically. You can review and adjust the imported endpoints before activating them.

## Tips

- Write clear "when to use" descriptions -- this is the primary signal the agent uses to select the right endpoint.
- Start with read-only endpoints at the `read` risk level, then add write operations once you trust the workflow.
- Use tags to group related systems and endpoints for easier management.
- Set realistic timeouts; the default is 30 seconds per endpoint call.
