# Agent Customization

## Overview

Firefly Desk's conversational agent can be customized to match your organization's brand, communication style, and operational requirements. Customization goes beyond changing a name -- you can define the agent's personality, tone, greeting, behavioral rules, and even provide free-form instructions that shape how the agent responds to every query.

Agent customization settings are stored in the database rather than environment variables. This means changes take effect immediately without restarting the application, and different deployment environments can have different agent configurations without modifying the `.env` file.

## What Can Be Customized

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `name` | string | `"Ember"` | The agent's internal name. Used in system prompts and greeting templates. |
| `display_name` | string | `"Ember"` | The name shown in the chat UI header and message bubbles. |
| `avatar_url` | string | `""` (default Ember avatar) | URL to a custom avatar image. Leave empty to use the built-in Ember avatar. |
| `personality` | string | `"warm, professional, knowledgeable"` | Comma-separated personality traits that shape the agent's communication style. |
| `tone` | string | `"friendly yet precise"` | Description of the conversational tone. |
| `greeting` | string | `"Hello! I'm {name}, your intelligent assistant."` | The initial message displayed when a user starts a new conversation. Supports `{name}` placeholder. |
| `behavior_rules` | array | `[]` | List of specific behavioral rules the agent must follow (e.g., "Always cite sources", "Never discuss competitor products"). |
| `custom_instructions` | string | `""` | Free-form additional instructions appended to the system prompt. Use this for domain-specific guidance. |
| `language` | string | `"en"` | Preferred response language. |

## Customizing via the Admin UI

The Agent Customization panel is accessible at `/admin/agent`. The interface is organized into sections:

### Identity

Configure the agent's name, display name, and avatar. The avatar preview updates in real-time as you enter a URL. The display name appears in the chat header, message bubbles, and the greeting message.

### Personality & Tone

Define how the agent communicates. The personality field accepts a comma-separated list of traits that the agent embodies in its responses. The tone field describes the overall conversational register.

**Example personalities:**
- `"warm, professional, knowledgeable"` -- The default Ember personality
- `"concise, technical, no-nonsense"` -- A direct, engineering-focused style
- `"friendly, patient, educational"` -- A teaching-oriented approach
- `"formal, authoritative, thorough"` -- An enterprise compliance style

### Greeting

The greeting is the first message the agent displays when a user starts a new conversation. The `{name}` placeholder is automatically replaced with the agent's display name.

**Example greetings:**
- `"Hello! I'm {name}, your intelligent operations assistant. How can I help you today?"`
- `"Welcome back. I'm {name}. What would you like to look into?"`
- `"Hi, I'm {name}. I have access to your systems and documentation -- what do you need?"`

### Behavior Rules

Behavior rules are specific instructions that the agent must follow in every conversation. Unlike personality traits (which are suggestive), behavior rules are prescriptive. Each rule is a separate text entry.

**Example rules:**
- `"Always include citations when referencing knowledge base documents"`
- `"Ask for confirmation before executing any destructive operations"`
- `"Respond in the same language the user uses"`
- `"Never share internal system credentials or API keys in responses"`

### Custom Instructions

The custom instructions field is a free-form text area for any additional instructions that should be included in the agent's system prompt. This is the most flexible customization option and is useful for domain-specific guidance that does not fit neatly into personality traits or behavior rules.

**Example custom instructions:**
```
When discussing financial transactions, always mention the relevant regulatory
framework (PCI-DSS for card data, SOX for financial reporting). If a user asks
about system access, direct them to the IT helpdesk at ext. 4200 for credential
requests.
```

### Language

Set the preferred response language. This instructs the agent to respond in the specified language by default, though it will follow the user's language if a behavior rule says to match the user's language.

## Customizing via the API

Agent settings can also be managed programmatically through the REST API. Both endpoints require the `admin:settings` permission.

### Get Current Settings

```
GET /api/settings/agent
```

Returns the current `AgentSettings` object:

```json
{
  "name": "Ember",
  "display_name": "Ember",
  "avatar_url": "",
  "personality": "warm, professional, knowledgeable",
  "tone": "friendly yet precise",
  "greeting": "Hello! I'm {name}, your intelligent assistant.",
  "behavior_rules": [],
  "custom_instructions": "",
  "language": "en"
}
```

### Update Settings

```
PUT /api/settings/agent
Content-Type: application/json

{
  "name": "Atlas",
  "display_name": "Atlas",
  "avatar_url": "https://cdn.example.com/atlas-avatar.png",
  "personality": "concise, technical, reliable",
  "tone": "direct and professional",
  "greeting": "Hello. I'm {name}, your operations assistant.",
  "behavior_rules": [
    "Always cite knowledge base sources",
    "Ask for confirmation before destructive operations"
  ],
  "custom_instructions": "Focus on banking operations and compliance.",
  "language": "en"
}
```

Changes take effect immediately. The in-memory agent profile cache is invalidated on every update, so the next conversation turn uses the new settings.

## Setup Wizard Integration

The first-run setup wizard includes an agent configuration step (Step 5: "Agent") where administrators can:

- Set the agent name and display name
- Upload or provide a URL for a custom avatar
- Choose a personality preset or enter a custom personality
- Configure the greeting message

This allows the agent to be personalized during initial setup before any conversations take place.

## Personality Presets

The admin UI and setup wizard offer several personality presets as starting points:

| Preset | Personality | Tone |
|--------|-------------|------|
| **Warm & Professional** | warm, professional, knowledgeable | friendly yet precise |
| **Technical & Concise** | concise, technical, no-nonsense | direct and efficient |
| **Friendly & Patient** | friendly, patient, educational | conversational and supportive |
| **Formal & Thorough** | formal, authoritative, thorough | professional and detailed |

Presets are convenience shortcuts. After selecting a preset, you can further customize any individual field.

## How Customization Works Internally

Agent settings are loaded by the `AgentCustomizationService` and compiled into an `AgentProfile` that includes the system prompt preamble, personality description, behavioral rules, and custom instructions. This profile is injected into the agent's system prompt at the beginning of every conversation turn.

The service maintains an in-memory cache of the compiled profile to avoid database lookups on every turn. The cache is invalidated whenever settings are updated through the API or admin UI, ensuring that changes propagate immediately without a server restart.

The `AgentProfile` influences the agent's behavior through the system prompt, not through model fine-tuning. This means customization is flexible and reversible -- changing the personality or instructions simply changes what the agent reads at the start of each turn.

## Environment Variables vs. Database Settings

Some agent-related settings exist as both environment variables and database settings:

| Environment Variable | Database Setting | Priority |
|---------------------|-----------------|----------|
| `FLYDESK_AGENT_NAME` | `AgentSettings.name` | Database wins (if set) |
| `FLYDESK_AGENT_INSTRUCTIONS` | `AgentSettings.custom_instructions` | Database wins (if set) |

The environment variables serve as initial defaults. Once agent settings are saved to the database (either through the admin UI, API, or setup wizard), the database values take precedence. This allows the same Docker image to be deployed with different agent configurations per environment without rebuilding.
