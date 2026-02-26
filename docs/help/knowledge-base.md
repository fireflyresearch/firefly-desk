---
type: tutorial
---

# Knowledge Base

The Knowledge Base is the agent's primary source of information. It stores documents that are automatically chunked, embedded, and indexed for vector search. When users ask questions, the agent retrieves relevant document snippets to ground its responses in your organization's actual content.

## Adding Documents

There are several ways to add content to the knowledge base:

- **File upload** -- Upload Markdown, text, HTML, JSON, or YAML files directly. Multi-file upload is supported for batch imports. The system auto-detects the document type (tutorial, policy, FAQ, reference, API spec, manual).
- **URL import** -- Provide a URL and the system fetches the page, converts HTML to Markdown, and indexes it. Useful for importing existing documentation sites or wiki pages.
- **OpenAPI import** -- Import API specifications (OpenAPI/Swagger). The parser extracts endpoint descriptions, parameters, and schemas as searchable knowledge.
- **Git import** -- Connect a GitHub repository and import Markdown, JSON, and YAML files directly from your codebase. See the [Git Import guide](git-import.md) for details.

## How Indexing Works

When a document is added, the indexer performs these steps:

1. **Chunking** -- The document is split into overlapping chunks for optimal retrieval.
2. **Embedding** -- Each chunk is converted to a vector using the configured embedding model (default: OpenAI text-embedding-3-small, 1536 dimensions).
3. **Storage** -- Chunks and embeddings are stored in PostgreSQL with pgvector for efficient similarity search.
4. **Knowledge graph extraction** -- Entities and relationships are extracted and added to the knowledge graph for structured lookups.

## Document Types

The system recognizes these categories: API Spec, Tutorial, Policy, FAQ, Reference, Manual, and Other. Type detection is automatic but can be overridden during import.

## Managing Documents

Each document has a status (draft or published), tags for organization, and metadata for tracking its source. You can edit content, update tags, or delete documents from the admin list view.

## Tips

- Tag documents consistently to make filtering easier and to support role-based access scopes.
- Shorter, focused documents produce better retrieval results than large monolithic files.
- Re-index after significant edits to update the vector embeddings.
- Use URL import for living documentation that changes frequently -- you can re-import to refresh.
