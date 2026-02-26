---
type: reference
---

# Exports

## Overview

The export system allows users to extract structured data from Firefly Desk into standard file formats for reporting, compliance, integration with other tools, or offline analysis. Exports are generated from conversation data, query results, or any structured data the agent produces, and are stored as downloadable files.

The export system exists because operational teams frequently need to move data out of the conversational interface and into spreadsheets, reports, or other systems. Rather than requiring users to copy-paste from the chat interface, the export system produces clean, formatted files that can be shared or imported directly into other tools.

## Supported Formats

### CSV

Comma-separated values format. Best suited for tabular data that will be opened in spreadsheet applications or imported into other data tools.

- **Content type:** `text/csv`
- **Encoding:** UTF-8
- **Structure:** Header row followed by data rows
- **Use when:** You need to open the data in Excel, Google Sheets, or import it into a database

### JSON

Pretty-printed JSON format. Best suited for data that will be processed programmatically or integrated with APIs.

- **Content type:** `application/json`
- **Encoding:** UTF-8
- **Structure:** Array of objects, where each object represents a row with column names as keys
- **Use when:** You need to process the data with code or feed it into another system's API

### PDF

Formatted document with a styled HTML table. Best suited for reports that need to be shared, printed, or archived.

- **Content type:** `application/pdf` (or `text/html` if weasyprint is not installed)
- **Structure:** HTML document with a header, styled table, and optional footer
- **Note:** PDF generation requires the `weasyprint` library and its system-level dependencies (Cairo, Pango). If these are not available, the system generates an HTML file instead, which can still be opened in any browser and printed to PDF.
- **Use when:** You need a formatted report for distribution, compliance records, or archival

## Creating Exports

### Through the API

```
POST /api/exports
Content-Type: application/json

{
  "format": "csv",
  "title": "Monthly Transaction Summary",
  "source_data": {
    "columns": ["Date", "Customer", "Amount", "Status"],
    "rows": [
      ["2026-01-15", "Alice Corp", "$12,500", "completed"],
      ["2026-01-16", "Bob LLC", "$8,200", "pending"],
      ["2026-01-17", "Charlie Inc", "$3,100", "completed"]
    ]
  }
}
```

The `source_data` field accepts two formats:

**Table format** (recommended):
```json
{
  "columns": ["Column A", "Column B"],
  "rows": [["value1", "value2"], ["value3", "value4"]]
}
```

**List-of-dicts format:**
```json
{
  "items": [
    {"Column A": "value1", "Column B": "value2"},
    {"Column A": "value3", "Column B": "value4"}
  ]
}
```

### Through the Agent

Users can ask Ember to export data directly within a conversation. When the agent determines that an export is appropriate, it creates an export job and presents an `ExportCard` widget in the chat interface with a download link.

Example prompts:
- "Export these transactions to CSV"
- "Generate a PDF report of the account balances"
- "Save this data as JSON"

### Through the Admin Console

The Export Manager at `/admin/exports` allows administrators to view all exports, download files, and manage export templates.

## Export Lifecycle

Each export progresses through a defined lifecycle:

1. **Pending** -- The export request has been received and recorded.
2. **Generating** -- The export file is being created. For CSV and JSON, this is near-instantaneous. For PDF, it depends on the complexity of the data and whether weasyprint is available.
3. **Completed** -- The file has been generated and stored. It is ready for download.
4. **Failed** -- An error occurred during generation. The error message is stored in the export record.

## Export Templates

Export templates allow administrators to define reusable formatting configurations that control how exported data is structured. Templates are particularly useful when the same type of data is exported regularly and needs to follow a consistent format.

### Template Fields

| Field | Description |
|-------|-------------|
| `name` | A descriptive name for the template (e.g., "Standard Transaction Report") |
| `format` | The export format this template applies to (csv, json, or pdf) |
| `column_mapping` | A mapping from source column names to output column names |
| `header_text` | Text displayed at the top of PDF exports |
| `footer_text` | Text displayed at the bottom of PDF exports |

### Column Mapping

Column mapping allows templates to rename and filter columns. Only columns present in the mapping are included in the output, and they are renamed according to the mapping values.

Example template:
```json
{
  "name": "Customer Report",
  "format": "csv",
  "column_mapping": {
    "cust_name": "Customer Name",
    "acct_balance": "Current Balance",
    "last_activity": "Last Active"
  }
}
```

When this template is applied to an export, only the `cust_name`, `acct_balance`, and `last_activity` columns are included, and they appear in the output as "Customer Name", "Current Balance", and "Last Active" respectively.

### Creating Templates

Templates are created through the API or the Export Manager:

```
POST /api/exports/templates
Content-Type: application/json

{
  "name": "Standard Transaction Report",
  "format": "pdf",
  "column_mapping": {
    "date": "Transaction Date",
    "amount": "Amount (USD)",
    "status": "Status"
  },
  "header_text": "Transaction Report - ACME Corp",
  "footer_text": "Confidential - Internal Use Only"
}
```

### System Templates

Some templates are marked as system templates and cannot be deleted. These provide baseline formatting options that are always available.

## Permissions

The export system uses four permissions to control access:

| Permission | Grants |
|-----------|--------|
| `exports:create` | Create new export jobs and view export history |
| `exports:download` | Download generated export files |
| `exports:delete` | Delete export records and their associated files |
| `exports:templates` | Create, edit, and delete export templates |

The built-in Administrator role has all export permissions. The Operator role has `exports:create` and `exports:download`. The Viewer role has no export permissions.

## Storage

Export files are stored using the same file storage system as file uploads, configured by `FLYDESK_FILE_STORAGE_PATH`. Each export file is named with the export ID and the appropriate file extension. Files remain available for download until the export record is deleted.

In multi-instance deployments, ensure that all application instances have access to the same file storage location so that exports created by one instance can be downloaded through another.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLYDESK_FILE_STORAGE_PATH` | `./uploads` | Directory where export files are stored |

No additional configuration is required for the export system. PDF generation quality depends on whether the `weasyprint` library and its system dependencies are installed.
