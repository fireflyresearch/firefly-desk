# Service Catalog

## Purpose

The Service Catalog is the registry of external systems and API endpoints that Ember can interact with on behalf of users. It answers the question: "What can the agent do?" Every system the agent calls, every endpoint it invokes, and every credential it uses to authenticate is defined in the catalog.

This registry-driven approach exists because an AI agent should never have implicit access to systems that operators have not explicitly registered and configured. The catalog makes the agent's capabilities visible, auditable, and controllable. An administrator can see exactly which systems are connected, what operations are available, what risk level each operation carries, and which users have permission to trigger them.

## External Systems

An external system represents a single backend service -- your CRM, ERP, payment gateway, internal API, or any other system the agent should be able to reach. Each system entry contains the information needed to connect, authenticate, and manage the integration.

### System Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, generated automatically. |
| `name` | string | Human-readable name displayed in the admin UI and referenced by the agent (e.g., "Payment Gateway"). |
| `description` | string | What this system does. The agent uses this description to understand the system's purpose. |
| `base_url` | string | Root URL for all endpoints (e.g., `https://api.payments.example.com/v2`). |
| `auth_config` | object | Authentication configuration. See [Authentication](#authentication-configuration) below. |
| `health_check_path` | string or null | Optional endpoint the platform pings to monitor availability (e.g., `/health`). |
| `tags` | array | Categorization labels for filtering and organization (e.g., `["payments", "banking"]`). |
| `status` | enum | Lifecycle state. See [System Status Lifecycle](#system-status-lifecycle) below. |
| `agent_enabled` | boolean | Whether the agent is allowed to use this system. Defaults to `false` for new systems. |
| `workspace_id` | string or null | Optional workspace scope for multi-workspace deployments. |
| `metadata` | object | Arbitrary key-value pairs for additional system attributes. |

### Registering a System

```
POST /api/catalog/systems
Content-Type: application/json

{
  "name": "Payment Gateway",
  "description": "Processes credit card and ACH payments. Supports refunds, chargebacks, and transaction lookups.",
  "base_url": "https://api.payments.example.com/v2",
  "auth_config": {
    "auth_type": "bearer",
    "credential_id": "cred-payment-api-key"
  },
  "health_check_path": "/health",
  "tags": ["payments", "banking"],
  "agent_enabled": true
}
```

The `description` field matters more than it might seem. The agent reads this description when deciding which system is relevant to a user's request. A vague description like "payment stuff" will produce worse tool selection than "Processes credit card and ACH payments. Supports refunds, chargebacks, and transaction lookups."

### System Status Lifecycle

Every system has a status that controls whether the agent can use it and what transitions are allowed. The lifecycle prevents accidental exposure of partially configured systems and provides a clear deprecation path.

| Status | Description | Agent Can Use? |
|--------|-------------|---------------|
| `draft` | System is being configured. Not yet ready for agent use. | No |
| `active` | System is fully configured and operational. | Yes (if `agent_enabled` is true) |
| `disabled` | System is temporarily taken offline. | No |
| `deprecated` | System is end-of-life. Terminal state. | No |
| `degraded` | System is experiencing issues but still partially functional. | Yes (with caution) |

**Valid transitions:**

```
draft ──────> active
active ─────> disabled | deprecated | degraded
disabled ───> active | deprecated
degraded ───> active | disabled
deprecated ─> (terminal, no transitions)
```

The `deprecated` status is intentionally a terminal state. Once a system is deprecated, it should be replaced rather than reactivated. This prevents the common pattern of temporarily "un-deprecating" something that was supposed to be retired.

## Service Endpoints

Each system contains one or more endpoints representing individual API operations. Endpoints are the atomic units that the agent resolves and invokes. While the system defines how to connect, the endpoint defines what to do.

### Endpoint Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier, generated automatically. |
| `system_id` | string | Reference to the parent system. |
| `name` | string | Human-readable name (e.g., "Look Up Transaction"). |
| `description` | string | What this endpoint does. Used by the agent for understanding. |
| `method` | enum | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. |
| `path` | string | Relative path appended to the system's base URL (e.g., `/transactions/{id}`). |
| `path_params` | object | Path parameter schemas (name, type, description, required). |
| `query_params` | object | Query parameter schemas. |
| `request_body` | object | Request body JSON schema. |
| `response_schema` | object | Expected response structure for the agent to interpret results. |
| `when_to_use` | string | Natural-language description of when to call this endpoint. **This is the primary signal the agent uses for tool selection.** |
| `examples` | array | Example user queries that should trigger this endpoint. |
| `risk_level` | enum | See [Risk Levels](#risk-levels) below. |
| `required_permissions` | array | RBAC permissions a user must hold to invoke this endpoint. |
| `protocol_type` | enum | Communication protocol. See [Multi-Protocol Support](#multi-protocol-support). |
| `rate_limit` | object | Optional rate limit (max requests per time window). |
| `timeout_seconds` | float | Request timeout. Default: 30 seconds. |
| `retry_policy` | object | Optional retry configuration (max retries, backoff factor). |
| `tags` | array | Categorization labels. |

### Registering an Endpoint

```
POST /api/catalog/systems/{system_id}/endpoints
Content-Type: application/json

{
  "name": "Look Up Transaction",
  "description": "Retrieves transaction details by transaction ID, including status, amount, and timestamps.",
  "method": "GET",
  "path": "/transactions/{transaction_id}",
  "path_params": {
    "transaction_id": {
      "type": "string",
      "description": "The unique transaction identifier",
      "required": true
    }
  },
  "when_to_use": "Use when the user asks about a specific transaction, wants to check a payment status, or needs transaction details like amount, date, or status.",
  "risk_level": "read",
  "required_permissions": ["catalog:read"],
  "protocol_type": "rest",
  "timeout_seconds": 15.0
}
```

### The "When to Use" Field

The `when_to_use` field deserves special attention because it is the primary mechanism the agent uses to decide which endpoint to call. When a user asks a question, the agent evaluates all available endpoints' `when_to_use` descriptions against the user's intent. A well-written description dramatically improves tool selection accuracy.

**Good example:**
> "Use when the user asks about a specific transaction, wants to check a payment status, or needs transaction details like amount, date, or status. Do NOT use for listing multiple transactions -- use the List Transactions endpoint instead."

**Poor example:**
> "Gets a transaction."

The difference is that the good example tells the agent both when to use the endpoint and when not to, reducing ambiguity between similar endpoints.

## Risk Levels

Every endpoint is classified with a risk level that reflects the severity of its potential impact on external systems. Risk levels drive the confirmation flow and determine whether the agent can execute an operation automatically or must pause for user approval.

| Risk Level | Description | Confirmation Required |
|------------|-------------|----------------------|
| `read` | No side effects. Information retrieval only. | Never |
| `low_write` | Creates or modifies data with limited, easily reversible impact. | Never |
| `high_write` | Significant data modification. May be difficult to reverse. | Yes, unless user holds wildcard (`*`) permission |
| `destructive` | Irreversible operations such as deletions, account closures, or data purges. | Always, regardless of permissions |

### Confirmation Flow

When the agent resolves a tool call classified as `high_write` or `destructive`, the platform intercepts the call before execution and generates a confirmation request. This request is delivered to the frontend as an SSE `confirmation` event, which renders a `ConfirmationCard` widget displaying the tool name, parameters, risk level, and a description of what will happen.

The user can approve or reject the action. Only after explicit approval does the platform execute the call. This enforcement is at the platform level, independent of the LLM's behavior. Even if the LLM attempts to bypass confirmation, the execution layer blocks the call.

**Confirmation rules:**
- `read` and `low_write` execute immediately
- `high_write` requires confirmation unless the user holds the wildcard `*` permission (admin bypass)
- `destructive` always requires confirmation, regardless of permissions
- Pending confirmations expire after 5 minutes if not acted upon
- A maximum of 10 confirmations can be pending simultaneously per conversation

## Multi-Protocol Support

The catalog supports five communication protocols, allowing the agent to work with both modern and legacy integration patterns. The `protocol_type` field on each endpoint determines how the `ToolExecutor` constructs and sends the request.

### REST (default)

Standard HTTP request/response. The endpoint's `method` and `path` are used directly. Path parameters, query parameters, and request body are populated from the LLM's tool call arguments.

### GraphQL

For GraphQL endpoints, the request is always a `POST` to the system's base URL (or the endpoint's path). The endpoint definition includes additional fields:

| Field | Description |
|-------|-------------|
| `graphql_query` | The GraphQL query or mutation string. |
| `graphql_operation_name` | Optional operation name for multi-operation documents. |

The tool executor constructs a standard GraphQL request body with `query`, `operationName`, and `variables` fields.

### SOAP

For SOAP endpoints, the request includes SOAP-specific envelope construction:

| Field | Description |
|-------|-------------|
| `soap_action` | The SOAPAction header value. |
| `soap_body_template` | A Jinja2 template for the SOAP body XML. Parameters from the tool call are injected into the template. |

SOAP support exists because many enterprise systems (ERP, legacy banking, government APIs) still expose SOAP interfaces. Rather than requiring a separate integration layer, the catalog handles SOAP natively.

### gRPC

For gRPC endpoints, the tool executor uses the gRPC-specific fields to construct the call:

| Field | Description |
|-------|-------------|
| `grpc_service` | The fully qualified gRPC service name. |
| `grpc_method_name` | The method to invoke on the service. |

### WebSocket

WebSocket endpoints establish a persistent connection for bidirectional communication. This is useful for systems that provide real-time data feeds or require interactive session-based protocols.

## Tool Resolution

When the agent processes a user message, the `ToolFactory` generates a set of available tools by querying the catalog. The resolution process works as follows:

1. **Filter active systems.** Only systems with `status=active` and `agent_enabled=true` are considered.
2. **Filter by permissions.** Each endpoint's `required_permissions` are checked against the current user's permissions. Endpoints the user cannot invoke are excluded entirely -- the LLM never sees them.
3. **Generate tool definitions.** Each eligible endpoint is converted into a tool definition that includes the endpoint name, description, `when_to_use` text, parameter schemas, and risk level.
4. **Present to the LLM.** The tool definitions are included in the system prompt. The LLM uses the descriptions and `when_to_use` fields to select the appropriate tool for the user's request.

This approach means the agent's capabilities are always a precise reflection of what the current user is allowed to do. An Operator who lacks `credentials:write` will never see tools that modify credentials, even if such endpoints exist in the catalog.

## Authentication Configuration

Each system can be configured with its own authentication method. Credentials are stored in the encrypted Credential Vault and referenced by ID -- the catalog never stores raw secrets.

| Auth Type | Description | Configuration |
|-----------|-------------|---------------|
| `none` | No authentication required. | No additional fields. |
| `api_key` | API key sent in a header or query parameter. | `credential_id`, optional `auth_headers` or `auth_params` to specify where the key is sent. |
| `bearer` | Bearer token in the Authorization header. | `credential_id` referencing the stored token. |
| `basic` | HTTP Basic Authentication (username:password). | `credential_id` referencing the stored credentials. |
| `oauth2` | OAuth 2.0 client credentials or authorization code flow. | `credential_id`, `token_url`, optional `scopes`. |
| `mutual_tls` | Mutual TLS with client certificates. | `credential_id` referencing the stored certificate/key pair. |

**Example OAuth2 configuration:**

```json
{
  "auth_type": "oauth2",
  "credential_id": "cred-payment-oauth",
  "token_url": "https://auth.payments.example.com/oauth/token",
  "scopes": ["transactions:read", "transactions:write"]
}
```

When the agent invokes an endpoint, the `ToolExecutor` retrieves the credential from the vault, decrypts it using the KMS provider, and injects it into the outbound request. For OAuth2, the executor handles token acquisition and caching automatically. Credentials are never logged, cached in plaintext, or exposed through the API.

## OpenAPI Import

Instead of manually creating systems and endpoints, you can import an OpenAPI 3.x specification to auto-register everything at once. The parser extracts all paths, methods, parameters, request/response schemas, and descriptions automatically.

```
POST /api/catalog/import/openapi
Content-Type: application/json

{
  "name": "Payment Gateway",
  "base_url": "https://api.payments.example.com/v2",
  "openapi_url": "https://api.payments.example.com/v2/openapi.json",
  "tags": ["payments"],
  "default_risk_level": "read"
}
```

The import process:

1. Fetches the OpenAPI specification from the provided URL.
2. Validates that it is a valid OpenAPI 3.x document.
3. Creates the external system with the provided name and base URL.
4. Iterates through all paths and methods, creating an endpoint for each operation.
5. Maps OpenAPI parameter definitions to the endpoint's `path_params`, `query_params`, and `request_body` fields.
6. Generates `when_to_use` descriptions from the OpenAPI operation summaries and descriptions.
7. Assigns the `default_risk_level` to all endpoints (can be adjusted individually after import).

After import, review the generated endpoints to adjust risk levels, refine `when_to_use` descriptions, and configure authentication. The import gives you a baseline; manual refinement ensures the agent uses each endpoint appropriately.

## API Reference

### Systems

| Method | Endpoint | Permission | Description |
|--------|----------|-----------|-------------|
| `GET` | `/api/catalog/systems` | `catalog:read` | List all registered systems. Supports filtering by tags and status. |
| `POST` | `/api/catalog/systems` | `catalog:write` | Register a new external system. |
| `GET` | `/api/catalog/systems/{system_id}` | `catalog:read` | Get a single system with full configuration. |
| `PUT` | `/api/catalog/systems/{system_id}` | `catalog:write` | Update an existing system. |
| `DELETE` | `/api/catalog/systems/{system_id}` | `catalog:delete` | Remove a system and all its endpoints. |

### Endpoints

| Method | Endpoint | Permission | Description |
|--------|----------|-----------|-------------|
| `GET` | `/api/catalog/systems/{system_id}/endpoints` | `catalog:read` | List all endpoints for a system. |
| `POST` | `/api/catalog/systems/{system_id}/endpoints` | `catalog:write` | Register a new endpoint under a system. |
| `GET` | `/api/catalog/endpoints/{endpoint_id}` | `catalog:read` | Get a single endpoint by ID. |
| `DELETE` | `/api/catalog/endpoints/{endpoint_id}` | `catalog:delete` | Remove an endpoint. |

### Import

| Method | Endpoint | Permission | Description |
|--------|----------|-----------|-------------|
| `POST` | `/api/catalog/import/openapi` | `catalog:write` | Auto-register systems and endpoints from an OpenAPI spec. |

## Tips

- **Write clear "when to use" descriptions.** This is the single most impactful thing you can do for tool selection accuracy.
- **Start with read-only endpoints.** Register `read` risk-level endpoints first. Once you trust the workflow, add write operations incrementally.
- **Use tags consistently.** Tags help organize large catalogs and enable filtering in both the admin UI and the API.
- **Set realistic timeouts.** The default 30-second timeout works for most APIs, but adjust it for slow endpoints (report generation, batch operations) to avoid premature failures.
- **Test with the agent.** After registering a system, ask Ember about it. If the agent struggles to select the right endpoint, the `when_to_use` description likely needs refinement.
- **Review imported endpoints.** OpenAPI import is a starting point. Always review generated endpoints to adjust risk levels and descriptions for your specific use case.
