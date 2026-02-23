# Process Discovery

## Overview

Process Discovery is Firefly Desk's ability to automatically identify and map business processes by analyzing the systems, endpoints, knowledge documents, and entity relationships already registered in the platform. Rather than requiring administrators to manually define every workflow, the discovery engine uses an LLM to infer how systems connect, what sequences of operations form coherent processes, and what dependencies exist between steps.

This capability exists because operational knowledge is often implicit. Teams know how things work, but that knowledge lives in people's heads, scattered documentation, and tribal understanding of "this system calls that system, then we check the result here." Process discovery makes this implicit knowledge explicit and visual.

## How It Works

The discovery engine operates in three stages:

### 1. Context Gathering

The engine collects all available context from the platform:

- **Service Catalog systems and endpoints:** What external systems are registered, what operations they support, and how they relate to each other through tags and descriptions.
- **Knowledge Graph entities and relationships:** The structured relationships between concepts, systems, and processes that have been extracted from documents.
- **Knowledge documents:** Operational runbooks, procedures, and reference material that describe workflows.

### 2. LLM Analysis

The gathered context is compiled into a structured prompt and sent to the configured LLM. The prompt uses Jinja2 templates (located in `src/flydesk/processes/prompts/`) that instruct the model to:

- Identify distinct business processes from the available context
- Break each process into ordered steps
- Map steps to specific catalog systems and endpoints where applicable
- Identify dependencies between steps (sequential, conditional, parallel)
- Assign confidence scores reflecting how certain the model is about each discovery
- Categorize processes (e.g., "customer-service", "operations", "payments")

The LLM returns structured JSON that is parsed into the process domain model.

### 3. Persistence

Discovered processes are stored in the database with their steps and dependencies. Each process is assigned a `discovered` status, a confidence score, and tagged with relevant categories. Processes can then be reviewed, verified, edited, or archived by administrators.

## Domain Model

### BusinessProcess

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier. |
| `name` | string | Process name (e.g., "ACH Transfer Processing"). |
| `description` | string | Summary of what the process does. |
| `category` | string | Category label (e.g., "payments", "customer-service"). |
| `steps` | array | Ordered list of `ProcessStep` objects. |
| `dependencies` | array | List of `ProcessDependency` edges between steps. |
| `source` | enum | How the process was created: `auto_discovered`, `manual`, or `imported`. |
| `confidence` | float | LLM confidence score (0.0 to 1.0). |
| `status` | enum | Lifecycle status: `discovered`, `verified`, `modified`, or `archived`. |
| `tags` | array | Categorization labels. |
| `created_at` | datetime | When the process was first discovered or created. |
| `updated_at` | datetime | When the process was last modified. |

### ProcessStep

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique step identifier. |
| `name` | string | Step name (e.g., "Validate Account"). |
| `description` | string | What this step does. |
| `step_type` | string | Step classification: "action", "decision", "wait", etc. |
| `system_id` | string or null | Reference to a catalog system (if the step uses one). |
| `endpoint_id` | string or null | Reference to a specific endpoint (if applicable). |
| `order` | int | Execution order within the process. |
| `inputs` | array | List of input data names. |
| `outputs` | array | List of output data names. |

### ProcessDependency

| Field | Type | Description |
|-------|------|-------------|
| `source_step_id` | string | The step that must complete first. |
| `target_step_id` | string | The step that depends on the source. |
| `condition` | string or null | Optional branching condition (e.g., "payment_valid == true"). |

## Auto-Triggers

When `FLYDESK_AUTO_ANALYZE` is enabled (or the `auto_analyze` setting is toggled on in the admin UI), data changes in the platform automatically trigger re-analysis:

| Event | Triggers |
|-------|----------|
| Knowledge document indexed | KG recomputation |
| Catalog system created or updated | KG recomputation + process discovery |

The `AutoTriggerService` debounces rapid changes with a 5-second window. If multiple documents are imported in quick succession, only one KG recomputation job is submitted after the burst completes. This prevents redundant work while ensuring that changes are eventually processed.

Auto-trigger jobs run through the background job system, so they do not block API responses. The jobs can be monitored through the jobs API at `/api/jobs`.

### Enabling Auto-Triggers

**Via environment variable:**
```bash
FLYDESK_AUTO_ANALYZE=true
```

**Via API:**
```
PUT /api/settings/analysis
Content-Type: application/json

{"auto_analyze": true}
```

**Via setup wizard:** The auto-analyze toggle is available during the initial setup wizard data configuration step.

## User Corrections

Discovered processes are starting points, not final truths. The LLM may infer incorrect relationships, miss steps, or misidentify which system handles a particular operation. The process management interface supports several correction workflows:

### Verify a Process

When a discovered process accurately represents reality, an administrator can mark it as verified:

```
POST /api/processes/{process_id}/verify
```

This changes the process status from `discovered` to `verified`, indicating that a human has reviewed and approved the discovery.

### Edit Steps

Individual steps within a process can be updated to correct names, descriptions, system mappings, or ordering:

```
PUT /api/processes/{process_id}/steps/{step_id}
Content-Type: application/json

{
  "name": "Validate Payment Method",
  "description": "Check that the payment method is active and has sufficient funds",
  "step_type": "action",
  "system_id": "sys-payment-gateway",
  "order": 2
}
```

### Update a Process

The entire process can be updated, including its steps and dependencies:

```
PUT /api/processes/{process_id}
Content-Type: application/json

{
  "id": "proc-001",
  "name": "Updated Process Name",
  "description": "Corrected description",
  "category": "payments",
  "steps": [...],
  "dependencies": [...]
}
```

When a process is edited, its status automatically changes to `modified`.

### Delete a Process

Processes that are incorrect or no longer relevant can be deleted:

```
DELETE /api/processes/{process_id}
```

## Process Explorer

The Process Explorer at `/admin/processes` provides a visual interface for viewing and managing discovered processes. It uses SvelteFlow to render each process as an interactive flow diagram where:

- **Steps** are rendered as draggable nodes with color-coded types (action, decision, wait)
- **Dependencies** are rendered as directed edges between nodes, with optional condition labels
- **Selection** clicking a node or edge reveals its details in a side panel
- **Layout** is computed automatically using a hierarchical algorithm

See [Admin Console](admin-console.md) for more details on the Process Explorer interface.

## API Reference

All process endpoints require the `processes:read` or `processes:write` permission.

### List Processes

```
GET /api/processes?category=payments&status=verified&tag=banking&limit=50&offset=0
```

Returns summary objects (without steps and dependencies) for efficient listing.

**Query parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `category` | string | Filter by category. |
| `status` | string | Filter by status: `discovered`, `verified`, `modified`, `archived`. |
| `tag` | string | Filter by tag. |
| `limit` | int | Maximum results (default: 50, max: 200). |
| `offset` | int | Pagination offset (default: 0). |

### Get Process

```
GET /api/processes/{process_id}
```

Returns the full process including steps and dependencies.

### Update Process

```
PUT /api/processes/{process_id}
```

Update a process (user corrections). Accepts a full `BusinessProcess` JSON body.

### Delete Process

```
DELETE /api/processes/{process_id}
```

Returns 204 No Content on success.

### Trigger Discovery

```
POST /api/processes/discover
Content-Type: application/json

{"trigger": "optional context hint"}
```

Submits a process discovery job. Returns `{"job_id": "...", "status": "pending"}`. Track the job through `GET /api/jobs/{job_id}`.

### Update Step

```
PUT /api/processes/{process_id}/steps/{step_id}
```

Update an individual step within a process.

### Verify Process

```
POST /api/processes/{process_id}/verify
```

Mark a process as verified by a human reviewer.
