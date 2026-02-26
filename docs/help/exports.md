---
type: tutorial
---

# Exports

Exports let you generate downloadable documents from data produced by the AI agent. You can export conversation results, data tables, and analysis outputs in CSV, JSON, or PDF format.

## Supported Formats

| Format | Description | Content Type |
|--------|-------------|-------------|
| **CSV** | Comma-separated values, suitable for spreadsheets | `text/csv` |
| **JSON** | Pretty-printed JSON, suitable for programmatic use | `application/json` |
| **PDF** | Formatted document with headers and tables (requires weasyprint) | `application/pdf` |

If the PDF library (weasyprint) is not installed, PDF exports fall back to styled HTML documents.

## How Exports Work

When you request an export, the system follows this lifecycle:

1. **Pending** -- The export record is created with the source data.
2. **Generating** -- The system normalizes the data, applies any template mappings, and generates the file.
3. **Completed** -- The file is stored and available for download. The record includes the file size and row count.
4. **Failed** -- If generation encounters an error, the record is marked as failed with an error message.

Exports are tied to the user who created them and tracked in the export history.

## Export Templates

Templates customize how data is formatted in the output. Each template defines:

- **Name** -- Descriptive label for the template.
- **Format** -- Which output format this template applies to (CSV, JSON, or PDF).
- **Column mapping** -- A dictionary that renames or filters source columns. Only mapped columns appear in the output, with the new names as headers.
- **Header text** -- Title shown at the top of PDF exports.
- **Footer text** -- Optional text at the bottom of PDF exports.

System templates ship with the platform and cannot be deleted. You can create additional custom templates.

## Data Input Formats

The export system accepts two input shapes:

- **Table format** -- `{"columns": ["Name", "Value"], "rows": [["Item A", "100"], ...]}` -- typically produced by the agent's data-table widget.
- **List of dicts** -- `{"items": [{"name": "Item A", "value": "100"}, ...]}` -- common in API responses.

Both formats are normalized internally before applying template mappings.

## Permissions

Export operations are controlled by RBAC permissions:

- `exports:create` -- Create new exports.
- `exports:download` -- Download generated files.
- `exports:delete` -- Remove export records and files.
- `exports:templates` -- Manage export templates.

## Tips

- Use templates to standardize export formats across your organization.
- Column mappings let you rename technical field names to business-friendly labels.
- Export records persist in the system -- clean up old exports periodically to save storage.
- The audit log tracks who created and downloaded each export.
