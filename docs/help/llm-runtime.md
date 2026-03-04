---
type: tutorial
---

# LLM Runtime Settings

The LLM Runtime Settings page lets you tune how the AI agent interacts with LLM providers -- retry behavior, timeouts, context budgets, and token limits. Changes are saved to the database and take effect immediately.

## Getting Started

If this is your first time on this page, click **Configure Wizard** to walk through a guided 4-step setup. The wizard explains what each group of settings does and why it matters before presenting the form fields.

Alternatively, pick a **preset profile** from the quick-apply bar to load a pre-configured set of values:

| Profile | When to Use |
|---------|-------------|
| **Conservative** | Rate-limited APIs, production environments where reliability is paramount |
| **Balanced** | Most deployments (this is the default) |
| **Performance** | High-throughput APIs with generous rate limits, when you want faster responses |

## Settings Overview

### Resilience & Retries

Controls how the agent handles transient LLM errors (rate limits, 503, 529):

- **Max retries** -- Number of retry attempts for the primary model (default: 3)
- **Retry base/max delay** -- Exponential backoff bounds (default: 3s–15s)
- **Fallback retries** -- Retry attempts for lighter fallback models (default: 2)
- **Follow-up retries** -- Retry attempts specifically for follow-up calls (default: 3)
- **Follow-up retry delays** -- Backoff bounds for follow-up retries (default: 15s–60s)

### Timeouts

Maximum wait times before the agent gives up on an LLM response:

- **Stream timeout** -- For the main streaming response (default: 300s / 5 min)
- **Follow-up timeout** -- For follow-up summarization calls (default: 240s / 4 min)

Increase these if you see timeout errors with complex queries or slow providers.

### Context Truncation

Controls how much content is included in LLM prompts to prevent oversized requests:

- **Per-part content limit** -- Max characters per tool result (default: 8,000)
- **Total content budget** -- Max characters across all tool results (default: 60,000)
- **Per-file limit** -- Max characters per uploaded file (default: 12,000)
- **Total file budget** -- Max characters across all files (default: 40,000)
- **Multimodal limit** -- Max characters for image descriptions (default: 12,000)

### LLM Output

- **Default max tokens** -- Maximum tokens per LLM response (default: 4,096)

### Knowledge Processing

- **Analyzer max chars** -- Content limit for document analysis (default: 8,000)
- **Document read max chars** -- Default limit for the document_read tool (default: 30,000)
- **Max knowledge tokens** -- Token budget for RAG snippets in the system prompt (default: 4,000)

### Context Enrichment

- **Entity limit** -- Max knowledge graph entities per turn (default: 5)
- **Retrieval top-k** -- Number of knowledge snippets retrieved per message (default: 5)
- **Enrichment timeout** -- Seconds to wait for knowledge retrieval (default: 10)

## Configuration Wizard

The wizard walks you through 4 steps:

1. **Choose a Profile** -- Pick Conservative, Balanced, or Performance to pre-fill all values
2. **Resilience & Timeouts** -- Configure retry and timeout behavior with visual flow diagram
3. **Context & Token Budgets** -- Set truncation limits with pipeline diagram
4. **Review & Apply** -- See a summary of changes vs. defaults and apply

## Tips

- Start with a preset profile and adjust individual fields only if needed.
- If the agent frequently hits rate limits, try the **Conservative** profile or increase retry counts.
- If responses feel slow, reduce timeouts or try the **Performance** profile.
- Monitor the audit log for timeout and retry errors to guide your tuning decisions.
- The profile indicator shows "Custom" when any field differs from all three presets.

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings/llm-runtime` | Retrieve current LLM runtime settings |
| `PUT` | `/api/settings/llm-runtime` | Update settings (partial updates supported) |

Both endpoints require the `admin:settings` permission.
