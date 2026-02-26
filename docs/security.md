---
type: policy
---

# Security

## Overview

Firefly Desk enforces security at multiple layers to ensure that operations teams can trust the platform with access to their backend systems. The security model is built around four pillars: role-based access control (RBAC) to govern who can do what, safety safeguards to prevent accidental or unauthorized destructive actions, credential encryption to protect stored secrets, and audit logging to maintain a complete record of every action taken through the platform.

This defense-in-depth approach means that security does not rely on any single mechanism. Even if one layer is bypassed, such as the LLM ignoring a behavioral guideline, the platform-level enforcement layers still prevent unauthorized actions.

## Role-Based Access Control

### RBAC Model

Firefly Desk uses a permission-based RBAC model where users are assigned roles, and roles contain sets of permissions. Permissions are enforced at two levels: the API middleware layer rejects unauthorized requests before they reach the route handler, and the agent's tool resolution layer filters available tools based on the current user's permissions. This dual enforcement means that a user cannot invoke a tool they lack permission for, regardless of whether the LLM attempts to call it.

### Permission Reference

The system defines 20 discrete permissions organized across seven domains:

| Permission | Description |
|-----------|-------------|
| `knowledge:read` | View knowledge documents, chunks, and graph entities |
| `knowledge:write` | Create and update knowledge documents, import from URLs, create graph entities and relationships |
| `knowledge:delete` | Delete knowledge documents and graph entities |
| `catalog:read` | View registered systems and endpoints |
| `catalog:write` | Create and update systems and endpoints |
| `catalog:delete` | Delete systems and endpoints |
| `chat:send` | Send messages to the agent and participate in conversations |
| `exports:create` | Create export jobs |
| `exports:download` | Download generated export files |
| `exports:delete` | Delete export records and files |
| `exports:templates` | Manage export templates (create, update, delete) |
| `audit:read` | View audit trail events |
| `credentials:read` | View credential metadata (secrets are always redacted) |
| `credentials:write` | Create, update, and delete credentials |
| `admin:users` | View and manage user accounts and role assignments |
| `admin:settings` | View and modify application settings |
| `admin:roles` | View and manage roles and permissions |
| `admin:sso` | Configure OIDC identity providers |
| `admin:llm` | Configure LLM providers and API keys |
| `admin:dashboard` | Access the admin dashboard with platform statistics |

### Built-in Roles

Three built-in roles are provided and cannot be modified or deleted:

**Administrator**
- Permissions: `*` (wildcard -- full access to all features)
- Intended for: Platform administrators responsible for system configuration, user management, and security
- Special behavior: The wildcard permission grants access to every feature and bypasses the confirmation requirement for `high_write` risk level operations (but not `destructive` operations, which always require confirmation)

**Operator**
- Permissions: `knowledge:read`, `catalog:read`, `catalog:write`, `exports:create`, `exports:download`, `chat:send`, `audit:read`
- Intended for: Operations team members who use the platform daily to interact with backend systems
- Design rationale: Operators can read knowledge and catalog data, execute tools through the chat interface (within catalog:write scope), create and download exports, and review audit logs, but they cannot modify the knowledge base, manage credentials, or access admin features

**Viewer**
- Permissions: `knowledge:read`, `catalog:read`, `chat:send`
- Intended for: Team members who need to observe the system and ask questions but should not execute write operations
- Design rationale: Viewers can browse knowledge documents, view registered systems, and have conversations with Ember, but Ember will only have access to read-only tools for these users

### Custom Roles

Custom roles can be created through the Role Manager in the admin console or via the `POST /api/admin/roles` API endpoint. Each custom role specifies an arbitrary combination of the 20 permissions listed above. This allows organizations to create role definitions that match their specific access control requirements.

For example, an organization might create a "Knowledge Curator" role with `knowledge:read`, `knowledge:write`, and `knowledge:delete` permissions, allowing specific team members to maintain the knowledge base without granting them access to the service catalog or admin features.

### Permission Enforcement

Permissions are enforced at two layers:

1. **API middleware**: Every API route declares its required permission. The RBAC middleware extracts the user's permissions from their session (populated from the OIDC token) and rejects requests that lack the required permission with a 403 Forbidden response. This enforcement is absolute and cannot be bypassed by the agent.

2. **Agent tool filtering**: During each conversation turn, the `ToolFactory` queries the service catalog for available endpoints and filters them based on the user's permissions. Only endpoints the user is authorized to invoke are presented to the LLM as available tools. This means the agent never even sees tools the user cannot use, which prevents the LLM from attempting unauthorized actions.

### Document Tool Permissions

Built-in document tools are gated by the appropriate knowledge permissions:

- `document_read` and `document_convert` require `knowledge:read`
- `document_create` and `document_modify` require `knowledge:write`

This ensures that users with read-only access to the knowledge base cannot create or modify documents through the agent, even if they can browse existing content.

## Safety Safeguards

### Risk Levels

Every endpoint in the service catalog is classified with a risk level that reflects the severity of its potential impact:

| Risk Level | Description | Confirmation Required |
|------------|-------------|----------------------|
| `read` | No side effects. Information retrieval only. | Never |
| `low_write` | Creates or modifies data with limited, easily reversible impact. | Never |
| `high_write` | Significant data modification. May be difficult to reverse. | Yes, unless user holds wildcard permission |
| `destructive` | Irreversible operations such as deletions, account closures, or data purges. | Always, regardless of permissions |

### Confirmation Flow

When the agent resolves a tool call for an endpoint classified as `high_write` or `destructive`, the platform intercepts the call before execution and generates a confirmation request. This confirmation request is sent to the frontend as a `confirmation` SSE event, which renders a `ConfirmationCard` widget in the chat interface.

The confirmation card displays:
- The name of the tool being invoked
- The parameters that will be sent
- The risk level classification
- A clear explanation of what the action will do

The user can then approve or reject the action. Only after explicit approval does the platform execute the tool call. This flow is enforced at the platform level by the `ConfirmationService`, independent of the LLM's behavior. Even if the LLM attempts to bypass confirmation, the execution layer blocks the call.

### Confirmation Rules

- `read` and `low_write` operations execute immediately without confirmation
- `high_write` operations require confirmation unless the user holds the wildcard `*` permission (admin bypass)
- `destructive` operations always require confirmation, regardless of the user's permissions
- Pending confirmations expire after 5 minutes (300 seconds) if not acted upon
- A maximum of 10 confirmations can be pending simultaneously per conversation

### Safety Plan Cards

For complex operations that involve multiple steps or affect multiple resources, the agent can present a `SafetyPlanCard` widget that outlines the complete plan before execution begins. This gives the user visibility into the full scope of the operation and the opportunity to cancel before any action is taken.

## Credential Encryption

All credentials stored in the Credential Vault are encrypted at rest using the `FLYDESK_CREDENTIAL_ENCRYPTION_KEY`. This includes API keys, OAuth client secrets, bearer tokens, and any other sensitive values associated with external system integrations. LLM provider API keys and OIDC provider client secrets are also encrypted using this key.

Credentials are decrypted only at the moment they are needed for an API call and are never logged, cached in plaintext, or exposed through the API. The credential list endpoint returns only metadata and identifiers; the actual secret values are always redacted.

If the encryption key is lost, all stored credentials become unrecoverable and must be re-entered. For this reason, the encryption key should be stored in your organization's secrets management system, not in a `.env` file committed to version control.

## Audit System

### What is Audited

Every significant action in the platform is recorded in the audit trail:

- **Chat turns:** The user's message, the enriched context provided to the agent, and the agent's response
- **Tool invocations:** The tool name, parameters sent, the response received, and the risk level of the operation
- **Confirmation decisions:** Whether the user approved or rejected a safety confirmation, and which tool call was involved
- **Administrative actions:** Changes to systems, endpoints, credentials, roles, users, knowledge documents, settings, and SSO configuration
- **Authentication events:** User login, logout, and session creation

### Audit Record Structure

Each audit event includes:
- **Timestamp:** When the event occurred (UTC)
- **User ID:** Who performed the action
- **Event type:** The category of the event (chat_turn, tool_invocation, admin_action, etc.)
- **Detail payload:** Event-specific data whose schema varies by event type

### Retention

Audit records are retained for the number of days specified by `FLYDESK_AUDIT_RETENTION_DAYS` (default: 365 days). The retention period should be set according to your organization's compliance requirements. Records beyond the retention period are eligible for cleanup.

### Why This Matters

In operational environments, accountability is essential. When the agent executes an action against a production system, the audit trail must capture exactly what was requested, what context informed the decision, and what action was taken. This enables incident investigation, compliance reporting, and continuous improvement of the agent's behavior.

The audit trail is append-only, meaning records cannot be modified or deleted through the application. This immutability ensures that the audit trail is a trustworthy record of what occurred.

## Rate Limiting

The `FLYDESK_RATE_LIMIT_PER_USER` configuration controls the maximum number of API requests a single user can make per minute. The default is 60 requests per minute. Rate limiting is enforced in production mode and disabled in development mode.

Rate limiting exists as a safety measure against both accidental abuse (such as a script making rapid API calls) and malicious activity. When a user exceeds the rate limit, subsequent requests receive a 429 Too Many Requests response until the rate limit window resets.
