---
type: tutorial
---

# Tools

Tools are the actions the AI agent can perform during a conversation. They range from searching your knowledge base to calling external APIs and running custom Python scripts. The agent selects which tool to use based on the user's request and each tool's description.

## Built-in Tools

Firefly Desk includes several built-in tools that operate on internal platform data without making external HTTP calls:

- **search_knowledge** -- Searches the knowledge base by natural-language query and returns relevant document snippets. Requires `knowledge:read` permission.
- **list_catalog_systems** -- Lists all registered external systems with their names, descriptions, and statuses. Requires `catalog:read` permission.
- **list_system_endpoints** -- Shows available API operations for a specific system. Requires `catalog:read` permission.
- **search_processes** -- Finds business processes matching a search term. Requires `processes:read` permission.
- **query_audit_log** -- Retrieves recent audit events. Requires `audit:read` permission (admin only).
- **get_platform_status** -- Returns a summary of the platform's current state. Available to all users.

Built-in tools are automatically available based on the user's role permissions.

## Catalog Endpoint Tools

Every active endpoint in the Catalog is also exposed as a tool. The agent uses each endpoint's "when to use" description to decide when to call it. Endpoint tools respect risk levels -- destructive or high-write operations require explicit user confirmation before execution.

## Custom Tools

Custom tools are user-defined Python scripts that the agent can execute. Each custom tool specifies:

- **Name and description** -- How the agent identifies and selects the tool.
- **Python code** -- The script to execute. It receives input parameters via stdin as JSON and must print a JSON result to stdout.
- **Parameters** -- JSON schema defining what inputs the tool accepts.
- **Output schema** -- Expected structure of the result.
- **Timeout** -- Maximum execution time (default: 30 seconds).
- **Memory limit** -- Maximum memory usage (default: 256 MB).

Custom tools run in an isolated subprocess sandbox. They cannot access the filesystem, network, or platform internals beyond what is passed through stdin. If a tool exceeds its timeout or memory limit, it is terminated automatically.

## Creating a Custom Tool

1. Navigate to **Tools** in the admin console and click **Create Tool**.
2. Provide a descriptive name and clear description of when the tool should be used.
3. Define the input parameters schema.
4. Write the Python code. Read input with `json.loads(input())` and print the result with `print(json.dumps(result))`.
5. Test the tool with sample inputs before activating it.

## Tips

- Write precise tool descriptions -- the agent relies on them heavily to pick the right tool.
- Keep custom tool code simple and focused on a single task.
- Test custom tools with edge cases before enabling them for production users.
- Use the `active` toggle to disable a tool without deleting it.
