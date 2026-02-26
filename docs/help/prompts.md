---
type: tutorial
---

# Prompts

Prompts are Jinja2 templates that control how the AI agent behaves, what context it receives, and how it structures its responses. The prompt system uses a template registry that loads `.j2` files from the templates directory and assembles them into the agent's system prompt at runtime.

## How Prompts Work

The agent's system prompt is composed from multiple template fragments, each responsible for a specific aspect of the agent's behavior:

- **identity_custom.j2** -- Defines the agent's persona, tone, and organizational identity.
- **behavioral_guidelines.j2** -- Rules the agent follows (e.g., always cite sources, ask for confirmation before writes).
- **available_tools.j2** -- Dynamically lists the tools the agent can use in the current session.
- **knowledge_context.j2** -- Injects relevant knowledge base snippets retrieved for the current query.
- **conversation_history.j2** -- Formats prior conversation turns for continuity.
- **user_context.j2** -- Includes user profile information (name, role, department) from the session.
- **widget_instructions.j2** -- Guides the agent on when and how to render UI widgets (tables, charts).
- **relevant_processes.j2** -- Provides matched business process steps as reference.
- **reasoning_plan.j2** -- Instructions for multi-step reasoning and planning.
- **file_context.j2** -- Context about uploaded files in the conversation.

## Jinja2 Syntax

Templates use standard Jinja2 syntax. Common patterns:

- `{{ variable }}` -- Insert a variable value.
- `{% for item in list %}...{% endfor %}` -- Loop over a collection.
- `{% if condition %}...{% endif %}` -- Conditional rendering.
- `{{ items | length }}` -- Use filters to transform values.

## Available Variables

Each template receives context variables relevant to its purpose. Common variables include:

- `tools` -- List of tool definitions (name, description, parameters).
- `knowledge_snippets` -- Retrieved document chunks with titles and scores.
- `user` -- Current user object (name, email, role, permissions).
- `processes` -- Matched business processes with steps.
- `conversation` -- Prior messages in the current session.
- `files` -- Uploaded file metadata.

## Editing Prompts

To customize agent behavior, edit the template files in the prompts/templates directory. Changes take effect on the next conversation since templates are loaded at startup and cached in the prompt registry.

## Tips

- Modify `identity_custom.j2` first -- it has the highest impact on how the agent presents itself.
- Keep templates focused on one concern; the system assembles them automatically.
- Test prompt changes in a development environment before deploying to production.
- Avoid removing required variables from templates -- the agent may produce errors if expected context is missing.
