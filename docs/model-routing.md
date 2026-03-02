---
type: guide
---

# Smart Model Routing

## Overview

Smart Model Routing automatically classifies incoming messages by complexity and routes them to cost-appropriate LLM models. Simple messages (greetings, status checks) are handled by cheaper, faster models, while complex reasoning tasks are routed to more capable models. This reduces LLM costs without sacrificing quality where it matters.

Routing is disabled by default and must be enabled by an administrator through the admin console or the API.

## How It Works

When a user sends a message, the router performs the following steps before the main LLM call:

1. **Classification** — A cheap classifier model analyzes the message text, tool count, and tool names to determine complexity.
2. **Tier assignment** — The classifier assigns one of three complexity tiers: fast, balanced, or powerful.
3. **Confidence check** — If the classifier's confidence is below 0.5, the router falls back to the default tier (configurable, defaults to balanced).
4. **Model mapping** — The assigned tier is mapped to a specific model string using the administrator's tier mappings.
5. **Override** — The mapped model is passed as `model_override` to the agent factory, overriding the provider's default model for this turn.

If routing is disabled, not configured, or fails for any reason, the system falls back silently to the provider's default model. Routing never blocks a conversation.

## Complexity Tiers

| Tier | Use Case | Examples |
|------|----------|----------|
| **Fast** | Simple interactions with no reasoning required | Greetings, status checks, simple lookups, yes/no questions |
| **Balanced** | Standard conversations with moderate tool use | 1-3 tool calls, standard Q&A, summarization, explanations |
| **Powerful** | Complex reasoning with heavy tool orchestration | 4+ tool calls, multi-step analysis, cross-system correlation, debugging |

## Architecture

The router is implemented as four components in the `flydesk.agent.router` package:

| Component | Module | Responsibility |
|-----------|--------|---------------|
| `ComplexityTier` | `models.py` | Enum defining the three tiers (fast, balanced, powerful) |
| `RoutingConfig` | `models.py` | Pydantic model for runtime configuration |
| `RoutingConfigRepository` | `config.py` | Database persistence with in-memory cache (60-second TTL) |
| `ComplexityClassifier` | `classifier.py` | Calls the classifier LLM to analyze message complexity |
| `ModelRouter` | `router.py` | Orchestrates classification, confidence thresholding, and tier-to-model mapping |

### Integration Point

The router integrates with `DeskAgent` at a single seam: before each LLM call. In `DeskAgent.stream()`, after tools are adapted but before the LLM is invoked, the `_route_model()` method calls the router. If a routing decision is made, it is:

- Emitted as an SSE `ROUTING` event to the frontend (so the UI can show which model was selected).
- Passed as `model_override` to `DeskAgentFactory.create_agent()`.
- Logged in the usage metadata for audit.

### Classifier Prompt

The classifier receives a structured prompt containing:

- The first 500 characters of the user's message
- The number of available tools
- The names of available tools
- The conversation turn count

It responds with a JSON object containing `tier`, `confidence` (0.0–1.0), and `reasoning`. The classifier prompt is designed to be fast and deterministic — it does not require chain-of-thought reasoning.

### Graceful Degradation

The router is designed to never break the conversation flow:

- If the classifier model call fails, the router returns `None` and the default model is used.
- If the classifier returns invalid JSON, the fallback tier (balanced, confidence 0.0) is used.
- If the confidence is clamped outside [0.0, 1.0], it is clamped to valid bounds.
- If the routing config has no tier mappings, the router returns `None`.
- If the database is unreachable, the cached config is used (stale cache is preferred over no config).

## Configuration

### Admin Console

Navigate to **Admin → LLM Configuration → Model Routing** to configure routing through the UI:

1. **Enable Smart Routing** — Toggle to activate the router.
2. **Classifier Model** — Select the cheap/fast model used for classification. The UI suggests small models (GPT-4o Mini, Claude Haiku, Gemini Flash) but any configured model can be used.
3. **Default Tier** — The fallback tier when classification confidence is low or classification fails. Defaults to balanced.
4. **Tier Model Mappings** — Assign a specific model to each tier. Unmapped tiers use the provider's default model.

Changes take effect within 60 seconds (the config cache TTL) without requiring a server restart.

### API

The routing configuration can also be managed through the REST API. See the [API Reference](api-reference.md) for endpoint details.

### Example Configuration

A typical cost-optimized setup:

| Setting | Value |
|---------|-------|
| Enabled | Yes |
| Classifier Model | `gpt-4o-mini` |
| Default Tier | Balanced |
| Fast → | `gpt-4o-mini` |
| Balanced → | `gpt-4o` |
| Powerful → | `claude-sonnet-4-20250514` |

This routes simple messages to GPT-4o Mini (low cost), standard conversations to GPT-4o (good balance), and complex multi-tool tasks to Claude Sonnet (highest capability).

## SSE Events

When routing is active, the server emits a `ROUTING` SSE event before the first `TOKEN` event in a streamed response:

```json
{
  "type": "routing",
  "data": {
    "model_string": "gpt-4o-mini",
    "tier": "fast",
    "confidence": 0.92,
    "reasoning": "Simple greeting with no tool requirements"
  }
}
```

## Title Generation

Conversation title generation automatically uses the FAST tier model when routing is configured, since title generation is a simple summarization task that does not require powerful models.

## Monitoring

Routing decisions are included in the usage metadata for each conversation turn. The `routing` field in the usage object contains the full `RoutingDecision` including the selected model, tier, confidence, reasoning, classifier latency, and token usage.
