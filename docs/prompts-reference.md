---
type: api_spec
---

# Prompt Templates Reference

## Overview

Firefly Desk uses Jinja2 templates to construct the system prompt sent to the LLM on every conversation turn. Rather than maintaining a single monolithic prompt string, the system composes the prompt from modular templates that are rendered conditionally based on the available context. This design allows sections to be added, removed, or modified independently without affecting other parts of the prompt.

The template system serves three purposes. First, it separates prompt engineering from application logic -- prompt improvements do not require code changes. Second, it supports conditional assembly so that sections with no data (such as knowledge context when the knowledge base is empty) are omitted entirely, saving tokens. Third, it enables customization through database-stored configuration values that are injected into templates at render time.

## Prompt Assembly Pipeline

The `SystemPromptBuilder` class in `src/flydesk/agent/prompt.py` orchestrates prompt assembly. On each conversation turn, it receives a `PromptContext` dataclass containing all the data needed to render templates, then builds the full system prompt in the following order:

| Order | Template | Condition |
|-------|----------|-----------|
| 1 | `identity_custom.j2` | Always rendered. |
| 2 | `user_context.j2` | Always rendered. |
| 3 | `available_tools.j2` | Always rendered (shows "no tools" message when list is empty). |
| 4 | `widget_instructions.j2` | Always rendered. |
| 5 | `behavioral_guidelines.j2` | Always rendered. |
| 6 | `knowledge_context.j2` | Only when `knowledge_context` is non-empty. |
| 7 | `file_context.j2` | Only when `file_context` is non-empty. |
| 8 | `relevant_processes.j2` | Only when `process_context` has items. |
| 9 | `conversation_history.j2` | Only when `conversation_summary` is non-empty. |

Each template is registered in the `PromptRegistry` (from the `fireflyframework-genai` package) and accessed by name. The rendered sections are joined with double newlines to form the complete system prompt.

The `reasoning_plan.j2` template is not part of the standard prompt assembly pipeline. It is rendered separately when the agent uses extended reasoning to plan multi-step operations.

## PromptContext

The `PromptContext` dataclass holds all the variables that templates can access:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `agent_name` | `str` | `"Ember"` | The agent's display name. |
| `company_name` | `str \| None` | `None` | Organization name shown in identity section. |
| `user_name` | `str` | `""` | Current user's display name. |
| `user_roles` | `list[str]` | `[]` | User's assigned roles. |
| `user_permissions` | `list[str]` | `[]` | User's resolved permissions. |
| `user_department` | `str` | `""` | User's department. |
| `user_title` | `str` | `""` | User's job title. |
| `tool_summaries` | `list[dict]` | `[]` | Tool name, description, and risk level for each available tool. |
| `knowledge_context` | `str` | `""` | Merged knowledge base snippets from RAG retrieval. |
| `conversation_summary` | `str` | `""` | Summary of earlier turns for multi-turn context. |
| `file_context` | `str` | `""` | Extracted content from uploaded files. |
| `personality` | `str` | `""` | Agent personality description (from DB configuration). |
| `behavior_rules` | `list[str]` | `[]` | Custom behavior rules (from DB configuration). |
| `greeting` | `str` | `""` | Custom greeting message. |
| `tone` | `str` | `""` | Communication tone (from DB configuration). |
| `process_context` | `list[Any]` | `[]` | Relevant business processes for the current turn. |
| `custom_instructions` | `str` | `""` | Freeform instructions (from DB configuration). |
| `language` | `str` | `"en"` | Response language code. |

---

## Core Agent Templates

These 10 templates live in `src/flydesk/prompts/templates/` and are used to build the agent's system prompt.

### identity_custom.j2

**Location:** `src/flydesk/prompts/templates/identity_custom.j2`

**Purpose:** Defines the agent's identity, personality, communication style, behavior rules, and custom instructions. This is the foundation of the agent's persona.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `agent_name` | Display name (default: "Ember"). |
| `company_name` | Organization name (optional, shown as "for {company}"). |
| `personality` | Personality description (e.g. "warm, professional, knowledgeable"). Falls back to a default if not set. |
| `tone` | Communication tone (e.g. "friendly yet precise"). |
| `behavior_rules` | List of custom behavior rules, each rendered as a bullet point. |
| `custom_instructions` | Freeform additional instructions block. |
| `language` | Language code. When set to non-English, instructs the agent to respond in that language. |

**When rendered:** Always. This is the first section of every system prompt.

**Sections generated:**

1. **Identity** -- "You are {name} for {company}, the Firefly Desk operations agent."
2. **Personality** -- Describes the agent's demeanor.
3. **Communication Style** -- Tone, formatting preferences, language rules.
4. **Behavior Rules** -- Custom rules rendered as a bulleted list (conditional).
5. **Additional Instructions** -- Freeform block (conditional).
6. **Knowledge and Honesty** -- Standard instructions about honesty and scope.

---

### behavioral_guidelines.j2

**Location:** `src/flydesk/prompts/templates/behavioral_guidelines.j2`

**Purpose:** Core behavior rules that apply to every conversation regardless of agent customization. Covers language detection, tool invocation discipline, formatting standards, and widget usage guidelines.

**Key variables:** None (static template).

**When rendered:** Always.

**Sections generated:**

1. **Language** -- Critical instruction to detect and respond in the user's language. Widget labels should also match the user's language.
2. **Behavior** -- Concise professional style, mandatory tool invocation for data questions, confirmation flow for high-risk operations, error handling.
3. **Formatting** -- Markdown formatting standards (headers, bold, code, tables, numbered lists).
4. **Widget Usage** -- Maps data shapes to widget types (entity details to `entity-card`, collections to `data-table`, status to `status-badge`, timelines to `timeline`, diffs to `diff-viewer`, charts for numerical data).

---

### available_tools.j2

**Location:** `src/flydesk/prompts/templates/available_tools.j2`

**Purpose:** Lists all tools available to the agent for the current turn, with their names, risk levels, and descriptions. Includes usage guidelines for when to call (and when not to call) tools.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `tool_summaries` | List of dicts, each with `name`, `description`, and `risk_level` keys. |

**When rendered:** Always. When the tool list is empty, renders a fallback message instructing the agent to answer from knowledge context only.

**Template logic:** Iterates over `tool_summaries` and renders each as `- **{name}** ({risk_level}): {description}`. Followed by guidelines on when to use `search_knowledge` versus answering directly.

---

### knowledge_context.j2

**Location:** `src/flydesk/prompts/templates/knowledge_context.j2`

**Purpose:** Injects retrieved knowledge base snippets into the system prompt as authoritative reference material.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `knowledge_context` | Pre-formatted string containing merged RAG results and knowledge graph entities. |

**When rendered:** Only when the `ContextEnricher` produces non-empty knowledge context for the current turn. This happens when vector similarity search or knowledge graph traversal returns results relevant to the user's message.

**Template content:** Simply wraps the context under a `# Relevant Context` heading.

---

### relevant_processes.j2

**Location:** `src/flydesk/prompts/templates/relevant_processes.j2`

**Purpose:** Injects business process definitions into the system prompt as procedural guidance. Processes include ordered steps, and steps may reference specific tools by endpoint ID.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `processes` | List of process objects, each with `name`, `description`, and `steps`. Each step has a `description` and optional `endpoint_id`. |

**When rendered:** Only when `process_context` has items. The `ContextEnricher` searches for processes relevant to the user's message.

**Template logic:** Iterates over each process and its steps, numbering them. Steps that reference a specific endpoint include the tool reference inline.

**Important note:** The template explicitly states these are guidance, not strict instructions: "Use them as guidance, not strict instructions. Adapt steps based on the actual situation."

---

### user_context.j2

**Location:** `src/flydesk/prompts/templates/user_context.j2`

**Purpose:** Provides the agent with information about the current user so it can personalize responses and respect permission boundaries.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `user_name` | User's display name. |
| `user_roles` | List of role names, joined with commas. |
| `user_department` | User's department (optional, shown only when set). |
| `user_title` | User's job title (optional, shown only when set). |

**When rendered:** Always.

**Template content:** Renders a `# Current User` section with name, roles, and the constraint: "You may only use tools this user has permission to access."

---

### conversation_history.j2

**Location:** `src/flydesk/prompts/templates/conversation_history.j2`

**Purpose:** Provides summarized context from earlier turns in the conversation. This enables the agent to maintain continuity across a multi-turn conversation without sending the entire message history in the system prompt.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `conversation_summary` | Pre-built summary string of prior conversation turns. |

**When rendered:** Only when `conversation_summary` is non-empty. This is populated by the conversation management system for turns beyond the first.

---

### file_context.j2

**Location:** `src/flydesk/prompts/templates/file_context.j2`

**Purpose:** Provides the agent with content extracted from files the user has uploaded or attached to the conversation.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `file_context` | Pre-formatted string containing extracted file content. |

**When rendered:** Only when `file_context` is non-empty. This is populated when the user uploads files through the chat interface.

---

### reasoning_plan.j2

**Location:** `src/flydesk/prompts/templates/reasoning_plan.j2`

**Purpose:** Renders a numbered plan of reasoning steps with status indicators. Used for extended reasoning and multi-step planning.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `steps` | List of step objects, each with `description` and `status` fields. |

**When rendered:** Not part of the standard system prompt pipeline. Rendered separately when the agent engages in explicit planning for complex multi-step tasks.

**Template logic:** Numbers each step sequentially and appends the status in brackets: `1. Validate payment details [pending]`.

---

### widget_instructions.j2

**Location:** `src/flydesk/prompts/templates/widget_instructions.j2`

**Purpose:** Comprehensive reference for all widget types the agent can embed in chat responses. Includes syntax, props, examples, and usage guidelines for all 24 widget types.

**Key variables:** None (static template).

**When rendered:** Always.

**Coverage:** Documents every widget type including display widgets (status-badge, entity-card, data-table, key-value, metric-card, image, code-block, accordion), feedback widgets (alert, progress-bar, timeline), interactive widgets (action-buttons, confirmation, export), visualization widgets (chart, mermaid-diagram, flow-diagram, diff-viewer, citation-card), and observability widgets (traces-timeline, metrics-chart, service-map, log-viewer, span-detail).

---

## Knowledge Graph Extraction Templates

Four templates in `src/flydesk/knowledge/prompts/` used by the `KGExtractor` component to extract entities and relationships from unstructured content.

### kg_extraction_document_system.j2

**Location:** `src/flydesk/knowledge/prompts/kg_extraction_document_system.j2`

**Purpose:** System prompt for the LLM when extracting knowledge graph entities and relationships from a knowledge base document.

**Key variables:** None (static system prompt).

**When rendered:** When a knowledge document is indexed or during KG recomputation.

**Instructions to the LLM:**
- Identify key business entities (systems, processes, roles, departments, concepts, data objects, APIs, services).
- Identify relationships between entities (uses, produces, depends_on, managed_by, part_of, integrates_with).
- Assign confidence scores between 0.0 and 1.0.
- Use `lowercase_snake_case` for entity and relation types.
- Return only a valid JSON object with `entities` and `relations` arrays.

**Output schema:**

```json
{
  "entities": [
    {"name": "...", "entity_type": "...", "properties": {}, "confidence": 0.9}
  ],
  "relations": [
    {"source": "entity_name", "target": "entity_name", "relation_type": "...", "properties": {}, "confidence": 0.8}
  ]
}
```

---

### kg_extraction_document_user.j2

**Location:** `src/flydesk/knowledge/prompts/kg_extraction_document_user.j2`

**Purpose:** User message template that provides the document content for entity extraction.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `title` | Document title. |
| `content` | Document content (first 8,000 characters). |

**When rendered:** Paired with `kg_extraction_document_system.j2` during document indexing.

---

### kg_extraction_catalog_system.j2

**Location:** `src/flydesk/knowledge/prompts/kg_extraction_catalog_system.j2`

**Purpose:** System prompt for extracting knowledge graph entities from service catalog metadata. Similar rules to document extraction, but with specific guidance for catalog content.

**Key variables:** None (static system prompt).

**When rendered:** When a catalog system is registered or updated, or during KG recomputation.

**Additional rules beyond document extraction:**
- The system itself should be an entity of type `system`.
- Each endpoint should be an entity of type `api_endpoint`.
- Identify relationships such as `has_endpoint`, `integrates_with`, `depends_on`, `produces`, `consumes`.

---

### kg_extraction_catalog_user.j2

**Location:** `src/flydesk/knowledge/prompts/kg_extraction_catalog_user.j2`

**Purpose:** User message template that provides the catalog system definition for entity extraction.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `name` | System name. |
| `description` | System description. |
| `base_url` | System base URL. |
| `status` | System status. |
| `tags` | System tags. |
| `endpoints` | Pre-formatted endpoint listing. |

**When rendered:** Paired with `kg_extraction_catalog_system.j2` during catalog system registration or update.

---

## Process Discovery Templates

Two templates in `src/flydesk/processes/prompts/` used by the process discovery system to identify business workflows from organizational data.

### discovery_system.j2

**Location:** `src/flydesk/processes/prompts/discovery_system.j2`

**Purpose:** System prompt that instructs the LLM to act as an enterprise process discovery analyst. Analyzes catalogs, knowledge graphs, and documents to identify workflows with steps, dependencies, and confidence scores.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `trigger` | Optional discovery trigger text. Focuses the analysis on processes related to a specific event or topic. |

**When rendered:** When process discovery is triggered manually, automatically (via `FLYDESK_AUTO_ANALYZE`), or during setup.

**Output schema:** Returns a JSON object with a `processes` array, where each process contains:
- `name`, `description`, `category`, `confidence`, `tags`
- `steps` array: Each step has `id`, `name`, `description`, `step_type` (action, decision, wait, notification, validation, transformation), optional `system_id`/`endpoint_id`, `order`, `inputs`, `outputs`.
- `dependencies` array: Each with `source_step_id`, `target_step_id`, and optional `condition`.

**Guidelines encoded in the template:**
- Focus on real business processes, not individual API calls.
- A process should have at least 2 steps.
- Higher confidence for processes with evidence across multiple sources.

---

### discovery_context.j2

**Location:** `src/flydesk/processes/prompts/discovery_context.j2`

**Purpose:** User message template that provides the organizational context for process discovery. Assembles data from three sources into a single structured prompt.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `systems` | List of catalog systems with their endpoints. Each system includes `id`, `name`, `description`, `base_url`, `status`, `tags`, and `endpoints`. |
| `entities` | Knowledge graph entities with `name`, `entity_type`, `confidence`, and `properties`. |
| `relations` | Knowledge graph relations with `source_id`, `relation_type`, `target_id`, and `properties`. |
| `documents` | Knowledge base documents with `title`, `document_type`, `tags`, and truncated `content` (first 500 characters). |

**When rendered:** Paired with `discovery_system.j2` during process discovery.

**Template structure:**
1. **Available Systems and Endpoints** -- Lists each catalog system with its endpoints, methods, risk levels, and usage guidance.
2. **Knowledge Graph Entities and Relations** -- Lists entities and their directional relationships.
3. **Knowledge Base Documents** -- Lists documents with titles and content previews.

---

## Catalog Discovery Templates

Two templates in `src/flydesk/catalog/discovery_prompts/` used by the system discovery feature to identify external systems that should be registered in the service catalog.

### system_discovery_system.j2

**Location:** `src/flydesk/catalog/discovery_prompts/system_discovery_system.j2`

**Purpose:** System prompt instructing the LLM to act as an enterprise system and application discovery analyst. Identifies external systems, platforms, and applications referenced in organizational data that are not yet in the service catalog.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `trigger` | Optional discovery trigger text for focused analysis. |

**When rendered:** When system discovery is triggered through the admin console, the API, or automatically.

**Output schema:** Returns a JSON object with a `systems` array, where each system contains:
- `name`, `description`, `base_url`, `category`, `auth_type`, `confidence`, `tags`
- `evidence`: Exact snippets from KG entities, relations, or documents supporting the discovery.
- `endpoints`: Identified API endpoints with `name`, `method`, `path`, `description`, `parameters`.
- `config_parameters`: Configuration parameters with `name`, `value`, `description`.

**Categories:** `crm`, `devops`, `communication`, `hr`, `finance`, `analytics`, `security`, `infrastructure`, `collaboration`, `project-management`, `ticketing`, `monitoring`, `storage`, `identity`, `other`.

**Guidelines encoded in the template:**
- Focus on software products, SaaS platforms, APIs, and infrastructure services.
- Do not report generic concepts or abstract entities.
- Do not report systems already in the catalog.
- Extract API endpoints and configuration parameters from evidence.

---

### system_discovery_context.j2

**Location:** `src/flydesk/catalog/discovery_prompts/system_discovery_context.j2`

**Purpose:** User message template providing organizational context for system discovery.

**Key variables:**

| Variable | Description |
|----------|-------------|
| `systems` | Existing catalog systems (listed as exclusions -- "DO NOT report these"). |
| `entities` | Knowledge graph entities. |
| `relations` | Knowledge graph relations. |
| `documents` | Knowledge base documents (content truncated to 500 characters). |

**When rendered:** Paired with `system_discovery_system.j2` during system discovery.

---

## Customization

### How Agent Personality is Customized

Agent personality, tone, behavior rules, and custom instructions are stored in the database as application settings, not hardcoded in template files. When the `SystemPromptBuilder` assembles the prompt, it reads these values from the `PromptContext` (which was populated from the database) and passes them to the `identity_custom.j2` template as variables.

This means administrators can customize the agent's behavior through two paths:

1. **Admin Console** -- The Agent Customization page (`/admin/customization`) provides form fields for agent name, personality, tone, greeting, behavior rules, custom instructions, and response language. Changes take effect on the next conversation turn.

2. **Setup Wizard** -- During initial setup, the wizard collects agent personality configuration and stores it in the database.

Neither path requires editing template files. The templates contain conditional logic (`{% if personality %}`, `{% if behavior_rules %}`, etc.) that includes or omits sections based on what is configured.

### What Can Be Customized Without Touching Templates

| Setting | Effect |
|---------|--------|
| Agent name | Changes the name in the identity section (default: "Ember"). |
| Company name | Adds "for {company}" to the identity line. |
| Personality | Defines the agent's demeanor (e.g. "warm and professional" vs. "direct and technical"). |
| Tone | Controls communication style (e.g. "friendly yet precise" vs. "formal and concise"). |
| Behavior rules | Custom bullet-point rules added to the identity section. |
| Custom instructions | Freeform text block for organization-specific instructions. |
| Language | Forces responses in a specific language (default: auto-detect from user's message). |
| Greeting | Custom greeting message for new conversations. |

### Template Architecture

All templates use Jinja2 syntax with conditional blocks. The rendering chain is:

```
PromptContext (dataclass)
    -> SystemPromptBuilder.build()
        -> PromptRegistry.get(template_name)
            -> Template.render(**variables)
                -> Rendered string section
    -> "\n\n".join(sections)
        -> Complete system prompt
```

The `PromptRegistry` is provided by the `fireflyframework-genai` package and handles template loading and caching. Templates are loaded from the filesystem paths listed above and registered by name during application startup.

## Template Quick Reference

| Template | Location | Conditional | Key Variables |
|----------|----------|-------------|---------------|
| `identity_custom.j2` | `prompts/templates/` | No | `agent_name`, `personality`, `tone`, `behavior_rules`, `custom_instructions`, `language` |
| `behavioral_guidelines.j2` | `prompts/templates/` | No | None (static) |
| `available_tools.j2` | `prompts/templates/` | No | `tool_summaries` |
| `knowledge_context.j2` | `prompts/templates/` | Yes | `knowledge_context` |
| `relevant_processes.j2` | `prompts/templates/` | Yes | `processes` |
| `user_context.j2` | `prompts/templates/` | No | `user_name`, `user_roles`, `user_department`, `user_title` |
| `conversation_history.j2` | `prompts/templates/` | Yes | `conversation_summary` |
| `file_context.j2` | `prompts/templates/` | Yes | `file_context` |
| `reasoning_plan.j2` | `prompts/templates/` | Separate | `steps` |
| `widget_instructions.j2` | `prompts/templates/` | No | None (static) |
| `kg_extraction_document_system.j2` | `knowledge/prompts/` | N/A | None (static) |
| `kg_extraction_document_user.j2` | `knowledge/prompts/` | N/A | `title`, `content` |
| `kg_extraction_catalog_system.j2` | `knowledge/prompts/` | N/A | None (static) |
| `kg_extraction_catalog_user.j2` | `knowledge/prompts/` | N/A | `name`, `description`, `base_url`, `status`, `tags`, `endpoints` |
| `discovery_system.j2` | `processes/prompts/` | N/A | `trigger` |
| `discovery_context.j2` | `processes/prompts/` | N/A | `systems`, `entities`, `relations`, `documents` |
| `system_discovery_system.j2` | `catalog/discovery_prompts/` | N/A | `trigger` |
| `system_discovery_context.j2` | `catalog/discovery_prompts/` | N/A | `systems`, `entities`, `relations`, `documents` |
