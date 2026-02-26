---
type: reference
---

# File Uploads

## Overview

Firefly Desk supports file uploads that allow users to share documents, data files, and other content directly within conversations. Uploaded files are stored on the server, their content is extracted for text-based formats, and the extracted text is made available to Ember as additional context during conversations.

The file upload system exists because many operational workflows involve working with documents that are not already in the knowledge base. An operator might need to share a CSV of transactions for analysis, upload a configuration file for review, or attach a policy document for reference. Rather than requiring these to be added to the knowledge base first, the file upload system makes them immediately available in the conversation context.

## Supported Formats

### Text-Based Formats (with content extraction)

These formats have their content automatically extracted and made available to Ember:

| Format | Content Type | Extraction Method |
|--------|-------------|-------------------|
| Plain text | `text/plain` | Direct text reading |
| Markdown | `text/markdown` | Direct text reading |
| HTML | `text/html` | HTML-to-text conversion |
| JSON | `application/json` | Pretty-printed JSON text |
| YAML | `application/yaml`, `text/yaml` | Direct text reading |
| CSV | `text/csv` | Direct text reading |

### Binary Formats (storage only)

These formats are stored and available for download, but their content is not automatically extracted:

| Format | Content Type | Notes |
|--------|-------------|-------|
| PDF | `application/pdf` | Stored for download; text extraction is not currently supported |
| Word documents | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Stored for download |
| Images | `image/png`, `image/jpeg`, etc. | Stored for download |
| Archives | `application/zip`, etc. | Stored for download |

Binary files can still be referenced in conversations and downloaded, but Ember will not have access to their textual content unless the content is manually provided.

## Uploading Files

### Through the Chat Interface

The chat interface supports file uploads through two mechanisms:

- **Drag and drop:** Drag a file from your file manager onto the chat area. A drop overlay appears to confirm the upload target.
- **File picker:** Click the attachment button in the input bar to open a file picker dialog.

Files are uploaded immediately and a preview appears in the input area before the message is sent. When the message is sent, the file is associated with the conversation turn.

### Through the API

```
POST /api/files/upload
Content-Type: multipart/form-data

file: (binary file content)
```

The response includes the file record with metadata:

```json
{
  "id": "file-uuid",
  "filename": "transactions.csv",
  "content_type": "text/csv",
  "file_size": 15234,
  "extracted_text": "Date,Amount,Status\n2026-01-15,500,completed\n..."
}
```

## Content Extraction

For supported text-based formats, the `ContentExtractor` service processes the uploaded file and extracts its textual content. This extraction happens during the upload process, so the content is available immediately.

The extracted text is stored alongside the file record and is provided to Ember when the file is referenced in a conversation. This means Ember can read, analyze, and respond to questions about the file's content without the user needing to paste it into the chat.

### HTML Content

HTML files are converted to plain text, preserving the document structure and content while stripping HTML tags, styles, and scripts. Links are preserved in their text form.

### JSON Content

JSON files are pretty-printed for readability. The extracted text is the formatted JSON string, which Ember can parse and analyze.

### Large Files

For files that exceed a reasonable text length, the extracted content may be truncated. The original file is always stored in full and available for download.

## File Storage

Uploaded files are stored on the local filesystem at the path configured by `FLYDESK_FILE_STORAGE_PATH` (default: `./uploads`). Each file is stored with a unique identifier to prevent name collisions.

### Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLYDESK_FILE_STORAGE_PATH` | `./uploads` | Directory where uploaded files are stored |
| `FLYDESK_FILE_MAX_SIZE_MB` | `50` | Maximum allowed file size in megabytes |

### Production Considerations

In production deployments:

- Use an absolute path for `FLYDESK_FILE_STORAGE_PATH` to avoid ambiguity
- Ensure the application process has read and write permissions to the storage directory
- For multi-instance deployments, use a shared filesystem (NFS, EFS) or object storage so all instances can access uploaded files
- Back up the storage directory as part of your regular backup procedures
- Monitor disk usage and implement cleanup policies for old files

## Chat Integration

When files are uploaded in a conversation, they become part of the conversation context. Ember can:

- Read the extracted content of text-based files
- Answer questions about the file's contents
- Analyze data in CSV or JSON files
- Reference specific parts of uploaded documents
- Compare content across multiple uploaded files within the same conversation

The file's content is included in the agent's context enrichment alongside knowledge base results and conversation history.

## API Reference

### POST /api/files/upload

Uploads a file and returns the file record with metadata and extracted content.

**Content-Type:** `multipart/form-data`

**Response:** `201 Created` with the file record.

### GET /api/files/{file_id}

Returns a file record with its metadata and extracted content.

### GET /api/files/{file_id}/download

Downloads the original file with the correct content type header.

### DELETE /api/files/{file_id}

Deletes the file record and its stored content.

**Response:** `204 No Content`

## Troubleshooting

### Upload Rejected

If an upload fails with a size error, the file exceeds the `FLYDESK_FILE_MAX_SIZE_MB` limit. Increase the limit if larger files are expected.

If an upload fails with a permission error, the `FLYDESK_FILE_STORAGE_PATH` directory may not exist or may not be writable by the application process.

### Content Not Available to Agent

If Ember cannot access the content of an uploaded file, verify that the file's content type is one of the supported text-based formats. Binary files (PDF, Word, images) are stored but their content is not extracted.

### Files Missing After Restart

In development mode with the default storage path (`./uploads`), files are stored relative to the working directory. If the application is started from a different directory, previously uploaded files will not be found. Use an absolute path for `FLYDESK_FILE_STORAGE_PATH` to avoid this issue.
