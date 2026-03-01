---
type: tutorial
---

# Agent

The Agent page lets you customize the conversational AI agent's identity, personality, and behavior without modifying code. Changes take effect immediately for new conversation turns.

## Identity

Configure the agent's display name and avatar. The display name appears in the chat header, message bubbles, and greeting messages throughout the UI.

## Personality & Tone

Define how the agent communicates using personality traits and a tone description. Several presets are available as starting points:

- **Warm & Professional** -- Friendly yet authoritative.
- **Technical & Concise** -- Direct, minimal, focused on accuracy.
- **Friendly & Patient** -- Approachable and thorough.
- **Formal & Thorough** -- Structured and comprehensive.

## Greeting

Set the initial message displayed when a user starts a new conversation. Use `{name}` as a placeholder for the agent's display name.

## Behavior Rules

Add specific rules the agent must follow in every conversation, such as:

- "Always cite sources when referencing knowledge base documents."
- "Ask for confirmation before executing destructive operations."
- "Respond in the user's preferred language when known."

## Custom Instructions

Free-form text appended to the agent's system prompt. Use this for domain-specific guidance that doesn't fit into the structured fields above.

## Tips

- Start with a preset personality and fine-tune from there.
- Write clear, actionable behavior rules -- vague instructions produce inconsistent results.
- Test changes by starting a new conversation after saving.
