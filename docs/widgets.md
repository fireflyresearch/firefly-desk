# Widget Reference

## Overview

Widgets are structured UI components that the agent embeds directly in chat responses. They transform what would otherwise be plain text into interactive, visually rich presentations of data. Widgets are rendered by the SvelteKit frontend from declarative JSON directives emitted by the agent.

The widget system exists because operational data is inherently structured. Displaying a table of transactions as formatted prose is both harder to scan and harder to act on than rendering it as an actual table with columns and rows. Widgets bridge the gap between the agent's text-based output and the user's need for visual clarity.

## Widget Directive Format

Widgets are embedded in the agent's markdown response using a fenced directive syntax:

```
:::widget{type="widget-type" inline=true}
{"prop": "value"}
:::
```

The directive consists of three parts:

1. **Opening fence** with attributes: `:::widget{type="..." ...}`
2. **JSON body** containing the widget's props
3. **Closing fence**: `:::`

### Attributes

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `type` | string | -- | The widget type identifier (required). |
| `inline` | bool | `true` | Render the widget inline within the chat message. |
| `panel` | bool | `false` | Open the widget in the side detail panel for more space. |
| `blocking` | bool | `false` | Block the conversation until the user responds (used with `confirmation`). |
| `action` | string | -- | Action name for blocking confirmations. |

## Widget Types

Firefly Desk includes 19 widget types organized into four categories:

### Display Widgets
- `status-badge` -- Colored status indicator
- `entity-card` -- Single-record detail card
- `data-table` -- Tabular data display
- `key-value` -- Key-value pair list
- `metric-card` -- Dashboard stat cards
- `image` -- Image with caption and lightbox

### Feedback Widgets
- `alert` -- Severity-based notification banner
- `progress-bar` -- Determinate or indeterminate progress
- `timeline` -- Chronological event list

### Interactive Widgets
- `action-buttons` -- Follow-up action chips
- `confirmation` -- Approval/rejection for high-risk operations
- `export` -- Export download card with status tracking

### Visualization Widgets
- `mermaid-diagram` -- Mermaid syntax diagrams
- `flow-diagram` -- Interactive SvelteFlow node-edge diagrams
- `chart` -- Chart.js charts (bar, line, pie, doughnut, radar, polarArea)
- `diff-viewer` -- Before/after comparison table
- `code-block` -- Syntax-highlighted code display
- `accordion` -- Collapsible content sections
- `citation-card` -- Knowledge base citation with relevance score

---

## status-badge

A small inline badge showing a status label with a colored indicator dot. Designed for displaying system health, job state, ticket status, or any categorical state.

Active-sounding labels such as "Active", "Running", "In Progress", or "Processing" automatically receive a pulsing animation to indicate ongoing activity.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `label` | string | yes | The text displayed next to the indicator dot (e.g. "Active", "Failed", "Pending"). |
| `status` | string | yes | Color variant: `"success"` (green), `"warning"` (yellow), `"error"` (red), `"info"` (blue), or `"neutral"` (gray). |

### Examples

**Healthy system:**
```
:::widget{type="status-badge" inline=true}
{"label": "Healthy", "status": "success"}
:::
```

**Failed job:**
```
:::widget{type="status-badge" inline=true}
{"label": "Failed", "status": "error"}
:::
```

**Pending task with pulse animation:**
```
:::widget{type="status-badge" inline=true}
{"label": "Processing", "status": "info"}
:::
```

---

## entity-card

A card that presents a single entity's details with a title, optional subtitle, a grid of labeled fields, and an optional status badge. Use this when displaying a single record such as a customer, a ticket, a system, or a user profile.

The status prop is automatically mapped to a color: strings like "Active", "Healthy", or "Running" render as green; "Warning", "Degraded", or "Pending" as yellow; "Error", "Failed", or "Offline" as red; "Info", "New", or "Scheduled" as blue; anything else as gray.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `title` | string | yes | Primary heading for the entity. |
| `subtitle` | string | no | Secondary descriptive text below the title. |
| `fields` | array | yes | Array of `{label: string, value: string}` objects displayed in a two-column grid. |
| `status` | string | no | Status text rendered as a `StatusBadge` with auto-mapped color. |

### Examples

**Customer record:**
```
:::widget{type="entity-card" inline=true}
{"title": "Customer #1042", "subtitle": "Premium Business Account", "fields": [{"label": "Company", "value": "Acme Corp"}, {"label": "Contact", "value": "Jane Smith"}, {"label": "Region", "value": "US-East"}, {"label": "Since", "value": "2024-03-15"}], "status": "Active"}
:::
```

**System overview (panel view):**
```
:::widget{type="entity-card" panel=true}
{"title": "Payment Gateway", "subtitle": "Core banking integration", "fields": [{"label": "Base URL", "value": "https://pay.internal:8443"}, {"label": "Auth", "value": "OAuth2"}, {"label": "Endpoints", "value": "12"}, {"label": "Last Health Check", "value": "2 min ago"}], "status": "Healthy"}
:::
```

---

## data-table

A table with column headers and alternating row stripes for displaying tabular data. Supports horizontal scrolling for wide tables. Best suited for multi-row result sets where each row has the same structure.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `columns` | array | yes | Array of `{key: string, label: string}` objects defining column order and header text. |
| `rows` | array | yes | Array of objects where each key corresponds to a column `key`. |
| `title` | string | no | Heading displayed above the table. |

### Examples

**Transaction list:**
```
:::widget{type="data-table" panel=true}
{
  "title": "Recent Transactions",
  "columns": [
    {"key": "id", "label": "Transaction ID"},
    {"key": "date", "label": "Date"},
    {"key": "amount", "label": "Amount"},
    {"key": "status", "label": "Status"}
  ],
  "rows": [
    {"id": "TXN-001", "date": "2026-02-23", "amount": "$1,200.00", "status": "Completed"},
    {"id": "TXN-002", "date": "2026-02-23", "amount": "$340.50", "status": "Pending"},
    {"id": "TXN-003", "date": "2026-02-22", "amount": "$8,900.00", "status": "Completed"}
  ]
}
:::
```

**Compact inline table:**
```
:::widget{type="data-table" inline=true}
{"columns": [{"key": "name", "label": "System"}, {"key": "status", "label": "Status"}], "rows": [{"name": "Payment API", "status": "Healthy"}, {"name": "Auth Service", "status": "Degraded"}]}
:::
```

---

## key-value

A vertical list of key-value pairs with the key on the left and value on the right. Ideal for configuration summaries, metadata displays, or connection details where each field has a distinct label.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `items` | array | yes | Array of `{key: string, value: string}` pairs. |
| `title` | string | no | Heading displayed above the list. |

### Examples

**Connection details:**
```
:::widget{type="key-value" inline=true}
{
  "title": "Database Connection",
  "items": [
    {"key": "Host", "value": "db-prod-01.internal"},
    {"key": "Port", "value": "5432"},
    {"key": "Database", "value": "flydesk_production"},
    {"key": "SSL", "value": "Required"},
    {"key": "Pool Size", "value": "20"}
  ]
}
:::
```

---

## alert

An alert banner with severity-based styling, icon, and optional title. Use for warnings, error notifications, success confirmations, or informational messages that need to stand out from regular text.

Each severity level renders with a distinct left border color and icon: info (blue, info icon), warning (amber, triangle icon), error (red, X icon), success (green, check icon).

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `message` | string | yes | The alert body text. |
| `severity` | string | yes | One of `"info"`, `"warning"`, `"error"`, or `"success"`. |
| `title` | string | no | Bold heading displayed above the message. |

### Examples

**Warning alert:**
```
:::widget{type="alert" inline=true}
{"severity": "warning", "title": "Rate Limit Approaching", "message": "API usage is at 85% of the hourly quota. Consider throttling non-critical requests."}
:::
```

**Error alert:**
```
:::widget{type="alert" inline=true}
{"severity": "error", "message": "Failed to connect to the payment gateway. The service returned HTTP 503."}
:::
```

**Success confirmation:**
```
:::widget{type="alert" inline=true}
{"severity": "success", "title": "Export Complete", "message": "Your transaction report has been generated successfully."}
:::
```

---

## progress-bar

An animated progress bar that can operate in either determinate mode (showing a specific percentage) or indeterminate mode (showing a shimmer animation). Use for tracking long-running operations like imports, exports, or batch jobs.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `value` | number or null | no | Current progress value. Omit or set to `null` for indeterminate shimmer mode. |
| `max` | number | no | Maximum value (default: 100). |
| `label` | string | no | Text label displayed above the bar. |
| `variant` | string | no | Color variant: `"default"`, `"success"`, `"warning"`, or `"danger"`. |

### Examples

**Determinate progress:**
```
:::widget{type="progress-bar" inline=true}
{"value": 75, "max": 100, "label": "Upload Progress", "variant": "success"}
:::
```

**Indeterminate loading:**
```
:::widget{type="progress-bar" inline=true}
{"label": "Processing documents..."}
:::
```

---

## accordion

Collapsible sections for organizing related content. Multiple sections can be open simultaneously. Use when presenting multiple distinct topics in a compact format.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `sections` | array | yes | Array of `{title: string, content: string}` objects. |
| `defaultOpen` | number or array | no | Index or array of indices of sections to open by default. |

### Examples

```
:::widget{type="accordion" inline=true}
{
  "sections": [
    {"title": "What is the refund policy?", "content": "Refunds are processed within 5 business days of the request."},
    {"title": "How do I reset my password?", "content": "Navigate to Settings > Security > Change Password."},
    {"title": "What file formats are supported?", "content": "PDF, DOCX, TXT, CSV, JSON, and Markdown files are supported."}
  ],
  "defaultOpen": 0
}
:::
```

---

## metric-card

Dashboard-style stat cards displayed in a grid. Each card shows a label, value, and optional trend indicator. Use for presenting KPIs, dashboard summaries, or at-a-glance metrics.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `metrics` | array | yes | Array of metric objects (see below). |

**Metric object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | yes | Short label for the metric. |
| `value` | string | yes | Display value (formatted as a string, e.g. "1,234"). |
| `delta` | string | no | Change indicator text (e.g. "+12%", "-5"). |
| `trend` | string | no | `"up"` (green arrow) or `"down"` (red arrow). |
| `icon` | string | no | Icon name hint. |

### Examples

```
:::widget{type="metric-card" inline=true}
{
  "metrics": [
    {"label": "Active Users", "value": "1,234", "delta": "+12%", "trend": "up"},
    {"label": "Error Rate", "value": "0.3%", "delta": "-0.1%", "trend": "down"},
    {"label": "Avg Response", "value": "1.2s"},
    {"label": "Open Tickets", "value": "47", "delta": "+5", "trend": "up"}
  ]
}
:::
```

---

## code-block

Enhanced code display with syntax highlighting, line numbers, and a copy-to-clipboard button. Use for showing code snippets, configuration files, API responses, or any structured text.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `code` | string | yes | The source code to display. |
| `language` | string | no | Language for syntax highlighting (e.g. "python", "javascript", "sql", "json"). Auto-detected if omitted. |
| `title` | string | no | Title displayed in the header bar. |
| `showLineNumbers` | bool | no | Whether to show line numbers (default: `true`). |

### Examples

```
:::widget{type="code-block" inline=true}
{"code": "SELECT u.name, COUNT(t.id) AS ticket_count\nFROM users u\nJOIN tickets t ON t.user_id = u.id\nGROUP BY u.name\nORDER BY ticket_count DESC\nLIMIT 10;", "language": "sql", "title": "Top Users by Ticket Count"}
:::
```

---

## action-buttons

Follow-up action chips that send a message to the conversation when clicked. Use to suggest next steps, offer related queries, or provide quick actions after presenting information.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `actions` | array | yes | Array of action objects (see below). |

**Action object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | yes | Button text. |
| `message` | string | yes | Message sent to the conversation when clicked. |
| `variant` | string | no | `"default"`, `"primary"`, or `"outline"`. Defaults to `"default"`. |

### Examples

```
:::widget{type="action-buttons" inline=true}
{
  "actions": [
    {"label": "Show full details", "message": "Show me the complete transaction details"},
    {"label": "Export as CSV", "message": "Export these transactions as CSV", "variant": "primary"},
    {"label": "Check system health", "message": "What is the current system health?", "variant": "outline"}
  ]
}
:::
```

---

## citation-card

Displays a knowledge base citation with the source title, relevant excerpt, and an optional relevance score. Use when referencing knowledge documents in the agent's response to provide transparency about information sources.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `source_title` | string | yes | Name of the source document. |
| `snippet` | string | yes | Relevant excerpt from the source. |
| `score` | number | no | Relevance score between 0 and 1 (displayed as a percentage). |
| `document_id` | string | no | Internal document identifier. |
| `source_url` | string | no | URL to the source document (rendered as a clickable link). |

### Examples

```
:::widget{type="citation-card" inline=true}
{"source_title": "ACH Failure Resolution Procedure", "snippet": "When an ACH transfer fails with code R01, the originating bank must initiate a return within 2 business days...", "score": 0.94, "document_id": "doc-ach-001"}
:::
```

---

## timeline

A vertical timeline of events with connecting lines, timestamps, and optional status badges. Use for audit trails, incident chronologies, process execution histories, or any sequence of dated events.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `events` | array | yes | Array of event objects (see below). |

**Event object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | yes | Display timestamp (any string format). |
| `title` | string | yes | Event headline. |
| `description` | string | no | Additional detail text below the title. |
| `status` | string | no | Badge text displayed beside the title. |

### Examples

```
:::widget{type="timeline" panel=true}
{
  "events": [
    {"timestamp": "2026-02-23 14:30:00", "title": "Incident Reported", "description": "Payment gateway returning 503 errors", "status": "Critical"},
    {"timestamp": "2026-02-23 14:35:00", "title": "Alert Triggered", "description": "PagerDuty notified on-call engineer"},
    {"timestamp": "2026-02-23 14:42:00", "title": "Root Cause Identified", "description": "Database connection pool exhausted due to connection leak"},
    {"timestamp": "2026-02-23 14:58:00", "title": "Fix Deployed", "description": "Hotfix deployed to restart connection pool", "status": "Resolved"},
    {"timestamp": "2026-02-23 15:05:00", "title": "Service Restored", "description": "All health checks passing"}
  ]
}
:::
```

---

## diff-viewer

A before/after comparison table that highlights changed fields. Unchanged values appear in neutral text; changed values show the old value in red and the new value in green. Use when displaying what changed in an update, configuration change, or data correction.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `before` | object | yes | Key-value object representing the original state. |
| `after` | object | yes | Key-value object representing the new state. |
| `title` | string | no | Heading displayed above the diff table. |

### Examples

```
:::widget{type="diff-viewer" panel=true}
{
  "title": "Configuration Update",
  "before": {
    "timeout_seconds": "30",
    "max_retries": "3",
    "log_level": "INFO",
    "rate_limit": "100/min"
  },
  "after": {
    "timeout_seconds": "60",
    "max_retries": "5",
    "log_level": "INFO",
    "rate_limit": "200/min"
  }
}
:::
```

---

## confirmation

A safety confirmation card for high-risk tool operations. Displays a risk-level badge, tool name, description, parameter summary, and Approve/Reject buttons with an optional countdown timer. This widget should always use `blocking=true` to pause the conversation until the user responds.

When the user clicks Approve, the widget sends `__confirm__:<confirmation_id>` to the conversation. When they click Reject, it sends `__reject__:<confirmation_id>`.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `confirmation_id` | string | yes | Unique identifier for tracking this confirmation. |
| `tool_name` | string | yes | Name of the tool requesting confirmation. |
| `risk_level` | string | yes | `"high_write"` (yellow/amber) or `"destructive"` (red). |
| `description` | string | no | Explanation of the action being confirmed. |
| `message` | string | no | Alternative to `description`. |
| `parameters` | object | no | Key-value object of parameters being passed to the tool. |
| `tool_call_id` | string | no | Internal tool call identifier. |
| `expires_at` | number | no | Unix timestamp (seconds) for the expiration countdown. |

### Examples

```
:::widget{type="confirmation" blocking=true action="delete-records"}
{
  "confirmation_id": "conf-abc-123",
  "tool_name": "bulk_delete_records",
  "risk_level": "destructive",
  "description": "This will permanently delete 1,247 archived transaction records older than 2 years.",
  "parameters": {
    "table": "transactions",
    "filter": "archived = true AND created_at < '2024-02-23'",
    "count": 1247
  },
  "expires_at": 1740350000
}
:::
```

---

## export

A download card for export results. Displays the export title, format badge (color-coded: green for CSV, blue for JSON, red for PDF), status indicator, row count, file size, and a download button that becomes active when the export completes.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `export_id` | string | yes | Export identifier used to construct the download URL (`/api/exports/{export_id}/download`). |
| `title` | string | yes | Export name displayed in the card header. |
| `format` | string | yes | `"csv"`, `"json"`, or `"pdf"`. |
| `status` | string | yes | `"pending"`, `"generating"`, `"completed"`, or `"failed"`. |
| `row_count` | number | no | Number of rows in the export. |
| `file_size` | number | no | File size in bytes (auto-formatted to KB/MB/GB). |
| `error` | string | no | Error message displayed when status is `"failed"`. |

### Examples

```
:::widget{type="export" inline=true}
{"export_id": "exp-20260223-001", "title": "February Transaction Report", "format": "csv", "status": "completed", "row_count": 3420, "file_size": 156000}
:::
```

---

## image

Displays an image with an optional caption. Clicking the image opens a full-screen lightbox overlay. Use for screenshots, generated charts, visual evidence, or any image content.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `src` | string | yes | Image URL or file path. |
| `alt` | string | no | Alt text for accessibility (defaults to empty string). |
| `caption` | string | no | Caption text displayed below the image. If omitted, `alt` is used as fallback. |

### Examples

```
:::widget{type="image" inline=true}
{"src": "/uploads/dashboard-screenshot.png", "alt": "Admin dashboard showing system health metrics", "caption": "Dashboard captured at 2026-02-23 14:30 UTC"}
:::
```

---

## chart

Renders an interactive chart using Chart.js. Supports multiple chart types and automatically applies a theme-aware color palette. Use for data visualization, trend analysis, and metric breakdowns.

The widget automatically assigns colors from a warm industrial palette if none are provided. For pie, doughnut, and polarArea charts, each data segment receives its own color. For bar, line, and radar charts, each dataset receives a single color.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `chartType` | string | no | Chart type (default: `"bar"`). Options: `"bar"`, `"line"`, `"pie"`, `"doughnut"`, `"radar"`, `"polarArea"`. |
| `title` | string | no | Heading displayed above the chart. |
| `labels` | array | no | Array of category labels for the x-axis or chart segments. |
| `datasets` | array | no | Array of dataset objects (see below). |
| `options` | object | no | Chart.js options object for advanced customization (merged with theme defaults). |

**Dataset object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | yes | Dataset legend label. |
| `data` | array | yes | Array of numeric values. |
| `backgroundColor` | string or array | no | Fill color(s). Auto-assigned from palette if omitted. |
| `borderColor` | string or array | no | Border color(s). Auto-assigned from palette if omitted. |
| `borderWidth` | number | no | Border width in pixels (default: 2). |

### Examples

**Bar chart:**
```
:::widget{type="chart" panel=true}
{
  "chartType": "bar",
  "title": "Monthly API Calls by Service",
  "labels": ["Jan", "Feb", "Mar", "Apr", "May"],
  "datasets": [
    {"label": "Payment API", "data": [4200, 5100, 4800, 5500, 6200]},
    {"label": "Auth Service", "data": [8900, 9200, 8700, 9800, 10100]}
  ]
}
:::
```

**Pie chart:**
```
:::widget{type="chart" inline=true}
{
  "chartType": "pie",
  "title": "Ticket Distribution",
  "labels": ["Open", "In Progress", "Resolved", "Closed"],
  "datasets": [{"label": "Tickets", "data": [23, 15, 42, 120]}]
}
:::
```

**Line chart with trend:**
```
:::widget{type="chart" panel=true}
{
  "chartType": "line",
  "title": "Response Time Trend",
  "labels": ["Mon", "Tue", "Wed", "Thu", "Fri"],
  "datasets": [
    {"label": "P50 (ms)", "data": [120, 115, 130, 125, 118]},
    {"label": "P99 (ms)", "data": [450, 480, 520, 490, 460]}
  ]
}
:::
```

---

## flow-diagram

An interactive flow diagram rendered with SvelteFlow. Use for process flows, entity relationships, decision trees, and dependency graphs. Nodes can be dragged, and the diagram supports zoom and pan when in interactive mode.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `nodes` | array | yes | Array of node objects (see below). |
| `edges` | array | yes | Array of edge objects (see below). |
| `title` | string | no | Heading displayed above the diagram. |
| `interactive` | bool | no | Enable drag/zoom. Defaults to `false` for inline, `true` for panel. |
| `height` | string | no | Diagram height as a CSS value (default: `"300px"`). |

**Node object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | Unique node identifier. |
| `label` | string | yes | Display text for the node. |
| `type` | string | no | Visual style: `"entity"`, `"process-step"`, `"system"`, `"document"`, `"decision"`. |
| `x` | number | no | Explicit x position. Auto-laid out if omitted. |
| `y` | number | no | Explicit y position. Auto-laid out if omitted. |

**Edge object fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | yes | Source node ID. |
| `target` | string | yes | Target node ID. |
| `label` | string | no | Relationship label displayed on the edge. |

### Examples

**Process flow:**
```
:::widget{type="flow-diagram" panel=true}
{
  "title": "Order Processing Flow",
  "nodes": [
    {"id": "1", "label": "Order Received", "type": "entity"},
    {"id": "2", "label": "Validate Payment", "type": "process-step"},
    {"id": "3", "label": "Payment Valid?", "type": "decision"},
    {"id": "4", "label": "Fulfill Order", "type": "process-step"},
    {"id": "5", "label": "Reject Order", "type": "process-step"}
  ],
  "edges": [
    {"source": "1", "target": "2", "label": "submit"},
    {"source": "2", "target": "3"},
    {"source": "3", "target": "4", "label": "yes"},
    {"source": "3", "target": "5", "label": "no"}
  ],
  "interactive": true,
  "height": "400px"
}
:::
```

---

## mermaid-diagram

Renders a diagram from Mermaid syntax. Supports flowcharts, sequence diagrams, ER diagrams, Gantt charts, and all other Mermaid diagram types. Use when the diagram structure maps naturally to Mermaid's text-based syntax.

### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `code` | string | yes | Mermaid diagram source code. |
| `title` | string | no | Heading displayed above the diagram. |

### Examples

**Sequence diagram:**
```
:::widget{type="mermaid-diagram" panel=true}
{
  "title": "Authentication Flow",
  "code": "sequenceDiagram\n  User->>+Frontend: Click Login\n  Frontend->>+OIDC Provider: Authorization Request\n  OIDC Provider-->>-Frontend: Authorization Code\n  Frontend->>+Backend: Exchange Code\n  Backend->>+OIDC Provider: Token Request\n  OIDC Provider-->>-Backend: ID Token + Access Token\n  Backend-->>-Frontend: Session Cookie\n  Frontend-->>-User: Logged In"
}
:::
```

---

## Usage Guidelines

### When to Use Inline vs. Panel

**Inline** (`inline=true`, the default) is appropriate for:
- Status badges, alerts, and progress bars
- Small key-value lists (3-5 items)
- Compact entity cards
- Action buttons
- Short data tables (2-3 rows)

**Panel** (`panel=true`) is appropriate for:
- Large data tables (many rows or columns)
- Timelines with multiple events
- Charts and diagrams
- Diff viewers
- Detailed entity cards with many fields

### When to Use Blocking

Blocking widgets (`blocking=true`) should only be used with the `confirmation` widget type. A blocking widget pauses the conversation until the user responds, which is appropriate only when user approval is required before a high-risk action can proceed. Never use blocking for informational widgets.

### Best Practices

1. **Prefer text for simple answers.** If the answer is a single sentence or a brief explanation, plain text is better than a widget. Widgets add value when data is structured, comparative, or actionable.

2. **Do not overuse widgets.** One or two widgets per response is usually sufficient. A response filled with many widgets is harder to scan than well-organized prose with a single focused widget.

3. **Match the widget to the data shape.** A single record is best shown with `entity-card`. A list of similar records fits `data-table`. A status indicator is best as `status-badge`. A comparison of two states should use `diff-viewer`.

4. **Combine related data.** Use one `data-table` with multiple rows rather than multiple separate `key-value` widgets when presenting a collection of similar items.

5. **Choose the right diagram type.** For standard flowcharts, sequence diagrams, and ER diagrams where Mermaid syntax is well-established, prefer `mermaid-diagram`. For custom node-edge layouts, process flows with typed nodes, or interactive diagrams, use `flow-diagram`.

6. **Use panel for detail views.** When the user asks to "show me the details" or "give me the full breakdown," render the response in a panel widget so it has room to breathe.
