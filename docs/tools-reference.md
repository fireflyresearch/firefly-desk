---
type: api_spec
---

# Built-in Tools Reference

## Overview

Firefly Desk ships with a set of built-in tools that the agent can invoke during conversations. These tools let the agent interact with the platform's own subsystems -- knowledge base, service catalog, audit log, document storage, and external APIs -- without requiring an external HTTP round-trip for internal operations.

Built-in tools are distinct from catalog endpoint tools. Catalog endpoints represent operations on external systems registered through the Service Catalog. Built-in tools are internal to the platform and always available (subject to permissions). Both types appear in the agent's tool list during a conversation turn, and the user does not need to distinguish between them.

The full tool set is organized into eight categories, totaling 24 built-in tools.

## Permission Model

Tools are filtered based on the current user's permissions before each conversation turn. The `BuiltinToolRegistry.get_tool_definitions()` method accepts the user's permission list and returns only the tools that user is authorized to invoke. This filtering happens at the platform level, not within the LLM, so the agent never sees tools the user cannot use.

Key rules:

| Rule | Effect |
|------|--------|
| Permission `*` (wildcard) | Grants access to all tools. Assigned to the built-in Administrator role. |
| No matching permission | The tool is excluded from the agent's tool list for that turn. |
| User-scoped tools | Memory and data transformation tools require no permission. They are always available to every authenticated user. |
| Document read tools | Gated by `knowledge:read`. |
| Document write tools | Gated by `knowledge:write`. |

Risk levels are assigned per tool and control the confirmation flow:

| Risk Level | Confirmation |
|------------|--------------|
| `read` | Never. Tool executes immediately. |
| `low_write` | Never. Tool executes immediately. |
| `high_write` | Required, unless user holds `*` permission. |
| `destructive` | Always required, regardless of permissions. |

---

## Knowledge and Documentation

Three tools for searching internal knowledge and working with document files.

### search_knowledge

Search the organization's knowledge base by natural-language query. Returns the most relevant document snippets using vector similarity search.

| Property | Value |
|----------|-------|
| **Permission** | `knowledge:read` |
| **Risk Level** | `read` |
| **Source** | `builtin.py` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Natural-language search query. |
| `top_k` | integer | no | Number of results to return (default: 5). |

**When to use:** The user asks a question that might be answered by internal documentation, policies, guides, or manuals.

**Example:** The user asks "what is the procedure for handling a failed ACH transfer." The agent calls `search_knowledge` with query `"failed ACH transfer procedure"` and receives matching document chunks from the knowledge base.

---

### document_read

Extract text, tables, and metadata from a document file stored in the platform's file storage.

| Property | Value |
|----------|-------|
| **Permission** | `knowledge:read` |
| **Risk Level** | `read` |
| **Supported formats** | PDF, DOCX, XLSX, PPTX |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | yes | Storage path of the document to read. |

**When to use:** The user asks to read, view, or extract information from an uploaded document.

**Example:** The user uploads a PDF and asks "what does this report say about Q4 revenue." The agent calls `document_read` with the file's storage path, receives the extracted text, and answers the question.

---

### document_convert

Convert a document between formats.

| Property | Value |
|----------|-------|
| **Permission** | `knowledge:read` |
| **Risk Level** | `read` |
| **Supported conversions** | XLSX to CSV, DOCX to plain text |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | yes | Storage path of the source document. |
| `target_format` | string | yes | Target format: `csv` or `text`. |

**When to use:** The user needs a document in a different format, such as converting a spreadsheet to CSV for import into another tool.

**Example:** The user says "convert this spreadsheet to CSV." The agent calls `document_convert` with `target_format: "csv"` and returns the path to the generated CSV file.

---

## Service Catalog -- Read

Two tools for browsing the service catalog.

### list_catalog_systems

List all external systems registered in the service catalog.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `read` |

**Parameters:** None.

**Returns:** System names, descriptions, base URLs, and statuses.

**When to use:** The user asks what systems are available, wants to see integrations, or needs to browse connected services.

**Example:** The user asks "what systems do we have connected?" The agent calls `list_catalog_systems` and presents the results in a `data-table` widget.

---

### list_system_endpoints

List all endpoints (operations) for a specific external system.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the system to list endpoints for. |

**Returns:** Endpoint names, HTTP methods, paths, risk levels, and descriptions.

**When to use:** The user asks what operations are available for a system or wants to know what they can do with a specific integration.

**Example:** The user asks "what can I do with the Payment Gateway?" The agent first calls `list_catalog_systems` to find the system ID, then calls `list_system_endpoints` with that ID.

---

## Service Catalog -- Write

Three tools for modifying the service catalog. These tools require `catalog:write` permission.

### create_catalog_system

Register a new external system in the service catalog.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:write` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | yes | System name. |
| `description` | string | no | System description. |
| `base_url` | string | no | Base URL for the system API. |
| `tags` | string | no | Comma-separated tags (e.g. `"crm,sales,api"`). |
| `auth_type` | string | no | Authentication type: `none`, `oauth2`, `api_key`, `basic`, `bearer`, `mutual_tls` (default: `none`). |

**Behavior:** The system is created in `DRAFT` status and must be activated manually through the admin console or API before the agent can make calls to it.

**When to use:** You discover or are told about a new backend system that should be registered for the agent to interact with.

---

### update_catalog_system

Update an existing external system in the service catalog.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:write` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the system to update. |
| `name` | string | no | New system name. |
| `description` | string | no | New system description. |
| `base_url` | string | no | New base URL. |
| `tags` | string | no | Comma-separated tags (replaces existing tags). |

**Behavior:** Only the fields you provide are changed; others remain unchanged.

**When to use:** You need to correct or enrich a system's name, description, URL, or tags.

---

### create_system_endpoint

Add a new endpoint (operation) to an existing system in the catalog.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:write` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the parent system. |
| `name` | string | yes | Endpoint name. |
| `method` | string | yes | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. |
| `path` | string | yes | URL path (e.g. `/users/{id}`). |
| `description` | string | no | What this endpoint does. |
| `when_to_use` | string | no | When the agent should use this endpoint. |
| `risk_level` | string | no | Risk level: `read`, `low_write`, `high_write`, `destructive` (default: `read`). |

**When to use:** You discover or are told about an API endpoint that the agent should be able to call on a registered system.

---

## API and Protocol Callers

Five tools for making calls to external systems registered in the service catalog. These tools bridge the gap between the agent's conversation and real backend APIs by handling authentication, URL construction, and response parsing automatically.

All five require `catalog:read` permission and are classified as `low_write` risk because they send requests to external systems. The actual risk of any specific call depends on the endpoint being invoked, which is why the confirmation system evaluates the registered endpoint's risk level rather than the caller tool's risk level.

### call_rest_endpoint

Make an HTTP REST call to a registered system endpoint.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `low_write` |
| **Protocols** | HTTP/HTTPS (GET, POST, PUT, PATCH, DELETE) |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the target system from the catalog. |
| `method` | string | yes | HTTP method: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`. |
| `path` | string | yes | URL path (appended to the system's `base_url`). |
| `query_params` | object | no | Query string parameters. |
| `body` | object | no | Request body (JSON). |
| `headers` | object | no | Additional HTTP headers (sensitive headers like `Authorization` are stripped from logs). |

**When to use:** You need to call a REST API on a system from the catalog but no pre-registered endpoint exists for the specific operation.

**Example:** The agent needs to fetch a customer record from the CRM: `call_rest_endpoint(system_id="crm-01", method="GET", path="/api/v2/customers/1042")`.

---

### call_graphql_endpoint

Execute a GraphQL query or mutation against a registered system.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the target system from the catalog. |
| `query` | string | yes | GraphQL query or mutation string. |
| `variables` | object | no | GraphQL variables object. |
| `operation_name` | string | no | GraphQL operation name (if query contains multiple operations). |

**When to use:** You need to run an ad-hoc GraphQL operation on a system from the catalog.

**Example:** `call_graphql_endpoint(system_id="product-api", query="query { products(limit: 10) { id name price } }")`.

---

### call_soap_endpoint

Send a SOAP XML request to a registered system.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the target system from the catalog. |
| `soap_action` | string | yes | SOAPAction header value. |
| `body_xml` | string | yes | SOAP XML request body. |
| `path` | string | no | URL path (defaults to system `base_url` root). |

**When to use:** You need to call a SOAP/XML web service on a system from the catalog. Common for legacy enterprise integrations.

---

### call_grpc_endpoint

Call a gRPC service method via JSON transcoding (gRPC-Web).

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the target system from the catalog. |
| `service` | string | yes | Fully qualified gRPC service name (e.g. `mypackage.MyService`). |
| `method` | string | yes | gRPC method name (e.g. `GetUser`). |
| `body` | object | no | JSON object for the request message. |

**When to use:** You need to invoke a gRPC method on a system from the catalog using JSON request/response encoding.

---

### call_websocket

Open a WebSocket connection, send a message, and return the response.

| Property | Value |
|----------|-------|
| **Permission** | `catalog:read` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `system_id` | string | yes | ID of the target system. |
| `path` | string | yes | WebSocket path (appended to system `base_url`, using `ws://` or `wss://`). |
| `message` | string | yes | Message to send (JSON string or plain text). |
| `timeout` | number | no | Timeout in seconds for response (default: 30). |
| `headers` | object | no | Additional connection headers. |

**When to use:** You need to interact with a WebSocket endpoint on a registered system.

---

## Document Operations

Four tools for creating, reading, modifying, and converting office documents. These tools work with the platform's file storage backend and lazily import document libraries only when invoked.

### document_create

Generate a new document file.

| Property | Value |
|----------|-------|
| **Permission** | `knowledge:write` |
| **Risk Level** | `low_write` |
| **Supported formats** | DOCX, XLSX, PDF |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `format` | string | yes | Output format: `docx`, `xlsx`, or `pdf`. |
| `title` | string | yes | Document title. |
| `content` | object | yes | Document content structure (see below). |

**Content structure by format:**

| Format | Structure |
|--------|-----------|
| `docx` | `{"paragraphs": ["paragraph text", ...]}` |
| `xlsx` | `{"sheets": [{"name": "Sheet1", "rows": [["A1", "B1"], ["A2", "B2"]]}]}` |
| `pdf` | `{"paragraphs": ["paragraph text", ...]}` |

**When to use:** The user asks to create a new report, spreadsheet, or document from scratch.

---

### document_modify

Edit an existing document.

| Property | Value |
|----------|-------|
| **Permission** | `knowledge:write` |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `file_path` | string | yes | Storage path of the document to modify. |
| `operation` | string | yes | Operation: `append`, `replace`, `update_cells`, or `merge`. |
| `data` | object | yes | Operation-specific data (see below). |

**Operation data by type:**

| Operation | Format | Data Structure |
|-----------|--------|---------------|
| `append` | DOCX | `{"paragraphs": ["new paragraph", ...]}` |
| `replace` | DOCX | `{"old_text": "find this", "new_text": "replace with this"}` |
| `update_cells` | XLSX | `{"updates": [{"sheet": "Sheet1", "cell": "A1", "value": "new value"}]}` |
| `merge` | PDF | `{"file_paths": ["path/to/second.pdf", ...]}` |

**When to use:** The user asks to edit, update, or merge documents.

---

## Data Transformation

Four tools for manipulating API results in memory. These tools require no permissions and are always available to every authenticated user. All operations are pure in-memory transformations using only Python standard library modules.

The data transformation tools exist because API responses are frequently larger or more complex than what the user needs. Rather than asking the user to sift through raw JSON, the agent can grep, filter, sort, and reshape data before presenting it.

### grep_result

Filter lines or objects from a text or JSON result that match a regular expression pattern.

| Property | Value |
|----------|-------|
| **Permission** | None (always available) |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | yes | The text or JSON array string to search through. |
| `pattern` | string | yes | Regular expression pattern to match. |

**Behavior:** If `data` is a valid JSON array, each element is tested against the pattern. If `data` is plain text, it is searched line-by-line. Returns matching items and a count.

**When to use:** You need to narrow down a large result set to lines or objects matching a keyword or pattern.

**Example:** After receiving a long list of transactions, the agent uses `grep_result` with pattern `"FAILED"` to find only the failed ones.

---

### parse_json

Parse a JSON string and optionally extract a value by dot-path, list top-level keys, or validate the structure.

| Property | Value |
|----------|-------|
| **Permission** | None (always available) |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | yes | JSON string to parse. |
| `action` | string | no | Action: `extract` (default), `keys`, or `validate`. |
| `path` | string | no | Dot-separated path for extraction (e.g. `results.0.name`). |

**Actions:**

| Action | Behavior |
|--------|----------|
| `extract` | Parse and return the full object, or extract a nested value if `path` is provided. |
| `keys` | Return the top-level keys of a JSON object. |
| `validate` | Check if the string is valid JSON and return the type. |

**When to use:** You need to drill into a JSON response, check its structure, or pull out a nested value.

**Example:** `parse_json(data='{"user": {"name": "Alice"}}', path="user.name")` returns `{"result": "Alice"}`.

---

### filter_rows

Filter an array of objects by field conditions.

| Property | Value |
|----------|-------|
| **Permission** | None (always available) |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | yes | JSON array string of objects to filter. |
| `field` | string | yes | Field name to filter on. |
| `operator` | string | yes | Comparison operator (see below). |
| `value` | string | yes | Value to compare against. |

**Supported operators:**

| Operator | Meaning |
|----------|---------|
| `eq` | Equal (string comparison). |
| `neq` | Not equal. |
| `gt` | Greater than (numeric). |
| `lt` | Less than (numeric). |
| `gte` | Greater than or equal (numeric). |
| `lte` | Less than or equal (numeric). |
| `contains` | Field value contains the given substring. |

**When to use:** You need to narrow down a list of records by a specific field value or range.

**Example:** From a list of orders, find those over $1,000: `filter_rows(data='[...]', field="amount", operator="gt", value="1000")`.

---

### transform_data

Transform an array of objects via sort, group, count, or pick operations.

| Property | Value |
|----------|-------|
| **Permission** | None (always available) |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `data` | string | yes | JSON array string of objects to transform. |
| `action` | string | yes | Action: `sort`, `group`, `count`, or `pick`. |
| `field` | string | conditional | Field name for `sort` and `group` actions. |
| `order` | string | no | Sort order: `asc` (default) or `desc`. Only for `sort`. |
| `fields` | string | conditional | Comma-separated field names for `pick` action. |

**Actions:**

| Action | Behavior |
|--------|----------|
| `sort` | Sort the array by `field` in `order` direction. |
| `group` | Group items by `field` value into a dictionary. |
| `count` | Return the number of items in the array. |
| `pick` | Return only the specified `fields` from each object. |

**When to use:** You need to reorder, aggregate, or slim down a dataset before presenting it to the user.

**Example:** Sort transactions by date descending: `transform_data(data='[...]', action="sort", field="date", order="desc")`.

---

## Audit and Monitoring

Two tools for platform observability. Both require `audit:read` permission.

### query_audit_log

Query the audit log for recent events.

| Property | Value |
|----------|-------|
| **Permission** | `audit:read` |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `limit` | integer | no | Maximum events to return (default: 20). |
| `event_type` | string | no | Filter by event type (e.g. `tool_invocation`, `chat_turn`, `admin_action`). |

**Returns:** Timestamped records of tool calls, agent responses, authentication events, and administrative actions.

**When to use:** An admin asks about recent activity, wants to review actions taken through the platform, or needs to investigate an issue.

---

### get_platform_status

Get an overview of the Firefly Desk platform status.

| Property | Value |
|----------|-------|
| **Permission** | `audit:read` |
| **Risk Level** | `read` |

**Parameters:** None.

**Returns:** Number of registered systems, endpoints, knowledge documents, and recent events.

**When to use:** The user asks about the platform, wants a summary, or is getting started and wants to know what is available. This tool is also always available regardless of permissions as a baseline status check.

---

## Business Processes

One tool for searching discovered business processes.

### search_processes

Search business processes by name or description.

| Property | Value |
|----------|-------|
| **Permission** | `processes:read` |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search term to find matching processes. |

**Returns:** Matching processes with their steps, dependencies, and categories as reference material.

**When to use:** The user asks about business processes, workflows, or how a procedure works.

**Example:** The user asks "how does the customer onboarding process work?" The agent calls `search_processes` with query `"customer onboarding"` and presents the discovered process steps.

---

## User Memory

Two tools for persisting and recalling user-specific information across conversations. Memory tools require no permissions because memories are scoped to the authenticated user and are not accessible to other users or administrators.

### save_memory

Save an important piece of information about the user for future reference.

| Property | Value |
|----------|-------|
| **Permission** | None (user-scoped, always available) |
| **Risk Level** | `low_write` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `content` | string | yes | The information to remember. |
| `category` | string | no | Category: `general` (default), `preference`, `fact`, or `workflow`. |

**When to use:** The user shares a preference, important fact, or workflow detail that should be remembered across conversations.

**Example:** The user says "I always want reports in CSV format." The agent calls `save_memory(content="User prefers reports in CSV format", category="preference")`.

---

### recall_memories

Search the user's saved memories for relevant information.

| Property | Value |
|----------|-------|
| **Permission** | None (user-scoped, always available) |
| **Risk Level** | `read` |

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `query` | string | yes | Search query to find relevant memories. |

**Returns:** Up to 10 matching memories sorted by recency.

**When to use:** You need to recall user preferences, past instructions, or facts the user has shared before. Memories are also searched automatically during the context enrichment phase of each conversation turn.

---

## Quick Reference Table

| Tool | Category | Permission | Risk Level |
|------|----------|------------|------------|
| `search_knowledge` | Knowledge | `knowledge:read` | `read` |
| `document_read` | Knowledge | `knowledge:read` | `read` |
| `document_convert` | Knowledge | `knowledge:read` | `read` |
| `list_catalog_systems` | Catalog Read | `catalog:read` | `read` |
| `list_system_endpoints` | Catalog Read | `catalog:read` | `read` |
| `create_catalog_system` | Catalog Write | `catalog:write` | `low_write` |
| `update_catalog_system` | Catalog Write | `catalog:write` | `low_write` |
| `create_system_endpoint` | Catalog Write | `catalog:write` | `low_write` |
| `call_rest_endpoint` | API Caller | `catalog:read` | `low_write` |
| `call_graphql_endpoint` | API Caller | `catalog:read` | `low_write` |
| `call_soap_endpoint` | API Caller | `catalog:read` | `low_write` |
| `call_grpc_endpoint` | API Caller | `catalog:read` | `low_write` |
| `call_websocket` | API Caller | `catalog:read` | `low_write` |
| `document_create` | Document Ops | `knowledge:write` | `low_write` |
| `document_modify` | Document Ops | `knowledge:write` | `low_write` |
| `grep_result` | Transform | None | `read` |
| `parse_json` | Transform | None | `read` |
| `filter_rows` | Transform | None | `read` |
| `transform_data` | Transform | None | `read` |
| `query_audit_log` | Audit | `audit:read` | `read` |
| `get_platform_status` | Audit | `audit:read` | `read` |
| `search_processes` | Processes | `processes:read` | `read` |
| `save_memory` | Memory | None | `low_write` |
| `recall_memories` | Memory | None | `read` |
