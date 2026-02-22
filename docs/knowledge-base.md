# Knowledge Base

## Purpose

The Knowledge Base gives Ember access to operational documentation, runbooks, policies, and domain-specific information that is not available through the Service Catalog's structured API metadata. While the Service Catalog tells Ember what actions it can perform, the Knowledge Base tells Ember how things work, why they work that way, and what procedures to follow in specific situations.

This distinction matters because operational work frequently requires contextual understanding that goes beyond API calls. When an operator asks "what is the procedure for handling a failed ACH transfer," the answer comes from organizational knowledge, not from an API endpoint. The Knowledge Base bridges this gap by making documents searchable and retrievable during every conversation turn.

## Document Types

Every knowledge document is classified with a document type that helps organize the knowledge base and allows Ember to understand the nature of the information it is referencing. The following types are supported:

| Type | Description | When to Use |
|------|-------------|-------------|
| `manual` | Operational manuals and runbooks | Step-by-step procedures, standard operating procedures |
| `tutorial` | Instructional guides | How-to guides, onboarding documentation, training material |
| `api_spec` | API specifications | OpenAPI specs, service contracts, integration documentation |
| `faq` | Frequently asked questions | Common questions and answers, troubleshooting checklists |
| `policy` | Organizational policies | Compliance rules, security policies, governance documents |
| `reference` | Reference documentation | Architecture diagrams, data dictionaries, configuration guides |
| `other` | Uncategorized documents | Anything that does not fit the above categories |

Document types are assigned automatically when content is imported through the importer service, or manually when documents are created through the API or admin interface.

## Knowledge Documents

A knowledge document is the fundamental unit of the Knowledge Base. Each document contains:

| Field | Description |
|-------|-------------|
| `id` | Unique identifier, generated automatically. |
| `title` | A descriptive title for the document (e.g., "ACH Failure Resolution Procedure"). |
| `content` | The full text content of the document. |
| `document_type` | Classification of the document (manual, tutorial, api_spec, faq, policy, reference, other). |
| `source` | Where the document originated (e.g., "Confluence", "internal wiki", "manual upload", a URL). |
| `tags` | Categorization labels for filtering and organization. |
| `metadata` | Arbitrary key-value pairs for additional document attributes. |

Documents are added through the REST API via `POST /api/knowledge/documents`, through the Admin Console's Knowledge Base Manager, by importing from a URL, or by uploading a file.

## Adding Documents

### Manual Creation

Documents can be created through the REST API or the Admin Console by providing a title, content, and optional metadata:

```
POST /api/knowledge/documents
Content-Type: application/json

{
  "title": "ACH Failure Resolution",
  "content": "When an ACH transfer fails...",
  "document_type": "manual",
  "source": "operations-wiki",
  "tags": ["payments", "ach", "procedures"]
}
```

The response includes an `IndexResult` with the document ID and the number of chunks created. Documents can also be managed through the Admin Console's Knowledge Base Manager.

### URL Import

The Knowledge Importer can fetch documents from URLs, automatically converting HTML content to clean markdown text:

```
POST /api/knowledge/import/url
Content-Type: application/json

{
  "url": "https://wiki.internal.com/procedures/ach-failures",
  "title": "ACH Failure Procedures",
  "document_type": "manual",
  "tags": ["payments", "procedures"]
}
```

When the URL returns HTML content, the importer converts it to markdown using `html2text`, preserving links while stripping images and unnecessary formatting. Non-HTML content is stored as-is. The document type is auto-detected from the URL structure when not explicitly provided.

### OpenAPI Specification Parsing

The importer includes a dedicated OpenAPI parser that converts OpenAPI 3.x specifications into structured knowledge documents:

```
POST /api/knowledge/import/url
Content-Type: application/json

{
  "url": "https://api.example.com/openapi.json",
  "title": "Example API Reference",
  "tags": ["api", "integration"]
}
```

The parser detects JSON/YAML content that contains `openapi` and `paths` keys, then extracts each endpoint as a structured description with its HTTP method, path, summary, parameters, and request/response schemas. This creates a comprehensive API reference document that Ember can use to answer questions about external system capabilities.

### File Upload

Files can be uploaded and their content extracted for indexing. See the [File Uploads](file-uploads.md) documentation for supported formats and the extraction process.

## Chunking

Raw documents are rarely the right unit for retrieval. A 10-page runbook contains many distinct topics, and retrieving the entire document when only one paragraph is relevant wastes context window tokens and dilutes the quality of the agent's response.

The Knowledge Indexer splits documents into chunks of 500 characters by default, with a 50-character overlap between adjacent chunks. The overlap ensures that sentences spanning a chunk boundary are not lost. Each chunk inherits the parent document's metadata and is stored as an independent retrieval unit.

The chunk size of 500 characters reflects a deliberate tradeoff. Smaller chunks are more precise but may lose surrounding context. Larger chunks provide more context but may include irrelevant information that confuses the model. The 500-character default works well for the kind of procedural and reference documentation common in operations work.

## Embedding and Indexing

Each chunk is converted into a vector embedding using the configured `EmbeddingProvider`. The `EmbeddingProvider` protocol defines a single method for generating embeddings, which allows different embedding model implementations to be swapped without changing the indexing or retrieval logic.

The default embedding model is `openai:text-embedding-3-small` with 1536 dimensions. These embeddings are stored alongside the chunk text in the database. When using PostgreSQL with pgvector, the embeddings are stored in a vector column with an appropriate index for efficient similarity search. In SQLite development mode, embeddings are stored as serialized arrays and similarity search is performed in application code.

The `KnowledgeIndexer` orchestrates the full indexing pipeline: it receives a document, chunks it, generates embeddings for each chunk, and persists the results. Indexing happens synchronously when a document is submitted, so the document is searchable immediately after the API call returns.

## Retrieval

The `KnowledgeRetriever` performs vector similarity search to find chunks that are semantically related to a query. When the agent processes a user message, the message text is embedded using the same model that indexed the documents, and the resulting vector is compared against all stored chunk vectors. The top-k most similar chunks (default: 3, configurable via `FLYDEK_RAG_TOP_K`) are returned as candidate context.

Similarity search is the right approach here because operational queries are often phrased differently from the documentation they relate to. A user asking "how do I fix a stuck payment" should match documentation titled "Payment Processing Error Recovery," even though the words are different. Vector similarity captures this semantic relationship in a way that keyword search cannot.

## Knowledge Graph

The Knowledge Graph is a complementary retrieval system that captures structured relationships between entities. While vector search finds documents that sound similar to a query, the knowledge graph answers "what is related to X" through explicit entity-to-entity connections.

### Entity Types

Entities in the knowledge graph represent concepts, systems, processes, or any other named item that appears in your operational documentation. Each entity has a type, a name, and optional properties.

### Relationships

Relationships connect entities with named, directional edges. For example, "Payment Service" might have a "depends_on" relationship with "Account Service," or "ACH Processor" might have a "handles" relationship with "Wire Transfers."

### Graph Exploration

The Admin Console includes a Knowledge Graph Explorer that visualizes entities and their relationships as an interactive force-directed graph powered by D3. Administrators can:

- Browse all entities and their connections visually
- Click on entities to view their properties and related documents
- Understand how concepts in the knowledge base relate to each other
- Identify gaps in the knowledge graph where relationships are missing

The graph explorer is available at `/admin/knowledge` under the Graph Explorer tab.

### API Endpoints

```
GET /api/knowledge/graph/entities
GET /api/knowledge/graph/entities/{entity_id}
GET /api/knowledge/graph/entities/{entity_id}/neighbors
POST /api/knowledge/graph/entities
DELETE /api/knowledge/graph/entities/{entity_id}
POST /api/knowledge/graph/relationships
```

## Context Enrichment

During each conversation turn, the `ContextEnricher` runs two retrieval processes in parallel: Knowledge Graph retrieval and RAG retrieval. The Knowledge Graph traverses entity relationships to find structurally related concepts. The RAG pipeline retrieves semantically similar document chunks using the process described above.

These two approaches are complementary. The knowledge graph answers "what is related to X" through explicit relationships. The vector search answers "what sounds like X" through semantic similarity. Running them in parallel rather than sequentially halves the retrieval latency, which is important because this enrichment happens on every conversation turn and directly affects the user's perceived response time.

The merged results are formatted and injected into the agent's system prompt as a dedicated context section. The agent sees this context as authoritative reference material and uses it to ground its responses in organizational knowledge rather than relying solely on its training data.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FLYDEK_EMBEDDING_MODEL` | `openai:text-embedding-3-small` | The embedding model for document vectorization. |
| `FLYDEK_EMBEDDING_DIMENSIONS` | `1536` | Dimensionality of embedding vectors. |
| `FLYDEK_RAG_TOP_K` | `3` | Number of document chunks retrieved during RAG. |
| `FLYDEK_KG_MAX_ENTITIES_IN_CONTEXT` | `5` | Maximum knowledge graph entities in context enrichment. |
