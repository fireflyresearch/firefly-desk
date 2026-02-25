# User Memory

Firefly Desk's User Memory system allows the agent to remember important information about users across conversations. When a user shares preferences, facts, or workflow details, the agent can save these as memories and recall them in future interactions to provide personalized, context-aware responses.

## How It Works

Memories are:

- **User-scoped** -- Each user's memories are private and isolated. Other users and administrators cannot access them.
- **Searchable** -- The agent searches memories during context enrichment, automatically including relevant memories in every conversation turn.
- **Persistent** -- Stored in the database, surviving server restarts and conversation boundaries.

The memory system uses the existing database and requires no additional configuration or infrastructure.

## Categories

| Category | Description | Example |
|----------|-------------|---------|
| `general` | Default catch-all category | "User mentioned they are on the sales team" |
| `preference` | User preferences and settings | "Prefers dark mode and compact tables" |
| `fact` | Important facts about the user | "User's timezone is America/New_York" |
| `workflow` | Workflow and process details | "Always needs manager approval for orders over $500" |

## Agent Tools

### save_memory

- **Risk Level:** LOW_WRITE
- **Parameters:** `content` (required), `category` (optional, defaults to `general`)
- **Permissions:** None required (user-scoped)

The agent uses this tool when users share information worth remembering. Memories are saved with the authenticated user's identity and are only accessible to that user.

### recall_memories

- **Risk Level:** READ
- **Parameters:** `query` (required)
- **Permissions:** None required (user-scoped)
- **Returns:** Up to 10 matching memories sorted by recency

The agent uses this tool to search for relevant memories when context would improve the response. Memories are also searched automatically during context enrichment.

## Context Enrichment

User memories are automatically searched during the context enrichment phase of each conversation turn. When a user sends a message, the `ContextEnricher` searches for memories relevant to the message content and includes matching memories in the agent's context alongside knowledge base results and knowledge graph entities. This enables the agent to personalize responses without requiring the user to repeat previously shared information.

## REST API

The memory system exposes three endpoints under `/api/memory`:

- `GET /api/memory` -- List all memories for the authenticated user, with optional category filtering
- `DELETE /api/memory/{memory_id}` -- Delete a specific memory
- `PATCH /api/memory/{memory_id}` -- Update a memory's content or category

See the [API Reference](api-reference.md#memory) for full endpoint documentation.

## Settings Page

Users can view and manage their memories at **Settings > Memories** (`/settings/memories`). The page provides:

- A list of all saved memories with content, category badges, and timestamps
- Search filtering by content
- Category filtering via dropdown
- Delete buttons for removing individual memories

## Slash Command

The `/context` command includes memory information in its output:

- When given a query (`/context <query>`), it shows matching user memories alongside knowledge base results
- Memory usage statistics are displayed, including token count, usage percentage, turns in conversation, compaction status, and total saved memory count
