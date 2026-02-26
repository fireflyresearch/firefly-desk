---
type: tutorial
---

# Users & Roles

Users & Roles manages who can access Firefly Desk and what they are allowed to do. The platform uses role-based access control (RBAC) where each user is assigned one or more roles, and each role defines a set of permissions.

## Built-in Roles

Three roles ship with the platform and cannot be deleted:

| Role | Description | Key Permissions |
|------|------------|-----------------|
| **Administrator** | Full system access | All permissions (`*` wildcard) |
| **Operator** | Operational access for day-to-day use | Knowledge read, catalog read/write, exports, chat, audit read, jobs, processes |
| **Viewer** | Read-only access | Knowledge read, catalog read, chat, jobs read, processes read |

## Permissions

Permissions follow a `resource:action` pattern. The full set includes:

- `knowledge:read`, `knowledge:write`, `knowledge:delete` -- Knowledge base access.
- `catalog:read`, `catalog:write`, `catalog:delete` -- Catalog systems and endpoints.
- `chat:send` -- Ability to use the agent chat interface.
- `exports:create`, `exports:download`, `exports:delete`, `exports:templates` -- Export operations.
- `audit:read` -- View the audit log.
- `credentials:read`, `credentials:write` -- Credential vault access.
- `jobs:read`, `jobs:cancel` -- Background job monitoring.
- `processes:read`, `processes:write` -- Business process management.
- `admin:users`, `admin:roles`, `admin:settings`, `admin:sso`, `admin:llm`, `admin:dashboard`, `admin:git_providers` -- Administrative functions.

The administrator role uses the `*` wildcard, which grants all current and future permissions.

## Access Scopes

Beyond permissions, roles can define **access scopes** that limit visibility to specific resources:

- **Systems** -- Restrict which catalog systems a role can see.
- **Knowledge tags** -- Limit knowledge base access to documents with specific tags.
- **Skill tags** -- Filter which tool categories are available.

An empty scope means unrestricted access for that dimension. When a user has multiple roles, scopes are merged using a most-permissive strategy.

## Custom Roles

Create custom roles to match your organization's structure. Navigate to **Roles** in the admin settings, click **Create Role**, define a name, description, permission set, and optional access scopes.

## Managing Users

From the **Users** section you can invite new users (by email or SSO linkage), assign or change roles, deactivate accounts, and view login history. Users who authenticate via SSO have their accounts created automatically on first login.

## Tips

- Follow the principle of least privilege -- assign the most restrictive role that still allows users to do their job.
- Use access scopes to implement data segregation across teams or departments.
- Custom roles let you create specialized access patterns (e.g., "Knowledge Editor" with only knowledge write permissions).
- The audit log records all user management actions.
