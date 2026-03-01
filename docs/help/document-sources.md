---
type: tutorial
---

# Document Sources

Document Sources connect Firefly Desk to cloud storage and drive services for automated document import and synchronization into the knowledge base.

## Supported Providers

- **Amazon S3** -- Connect to S3 buckets for document sync.
- **Azure Blob Storage** -- Import from Azure storage containers.
- **Google Cloud Storage** -- Sync from GCS buckets.
- **OneDrive** -- Connect to Microsoft OneDrive personal or business accounts.
- **SharePoint** -- Import from SharePoint document libraries.
- **Google Drive** -- Sync from Google Drive folders.

## Setting Up a Source

1. Click the provider card or **+ Add Source** button.
2. Follow the inline setup tutorial for your chosen provider -- it explains how to create credentials, which permissions to grant, and security best practices.
3. Enter the connection details (bucket name, folder path, credentials).
4. Test connectivity to verify the configuration.
5. Save and optionally enable automatic sync.

## Sync Options

Each source supports:

- **Automatic sync** -- Run on a schedule: every 6 hours, 12 hours, or daily.
- **Manual sync** -- Trigger an immediate sync from the source detail view.
- **Active/Inactive toggle** -- Pause syncing without deleting the source configuration.

## Tips

- Start with a small folder to verify the import pipeline before syncing large repositories.
- Documents are automatically chunked, embedded, and indexed when synced.
- Use the connectivity test before saving to catch credential issues early.
