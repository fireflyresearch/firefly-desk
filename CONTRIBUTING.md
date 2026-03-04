# Contributing to Firefly Desk

Thank you for your interest in contributing to Firefly Desk. This guide covers how to set up a development environment, run tests, create database migrations, and submit changes.

## Prerequisites

- **Python 3.13+** with [uv](https://github.com/astral-sh/uv) for dependency management
- **Node.js 22+** for the SvelteKit frontend
- **Git**

## Development Setup

```bash
# Clone the repository
git clone https://github.com/fireflyresearch/firefly-desk.git
cd firefly-desk

# Copy the example environment file
cp .env.example .env

# Install Python dependencies
uv sync

# Initialize the database
uv run flydesk db upgrade head

# Start backend + frontend in development mode
uv run flydesk dev
```

Development mode uses SQLite and a synthetic admin user -- no external services required.

### Frontend Only

```bash
cd frontend
npm install
npm run dev          # Dev server on :5173
npm run check        # Svelte type checking
npm run build        # Production build
```

## Project Structure

```
firefly-desk/
├── src/flydesk/           # Python backend
│   ├── agent/             # Agent pipeline (DeskAgent, context enricher, prompt builder)
│   ├── api/               # FastAPI routers (REST endpoints)
│   ├── audit/             # Append-only audit logger
│   ├── auth/              # OIDC authentication
│   ├── callbacks/         # Outbound webhook delivery
│   ├── catalog/           # Service catalog (systems, endpoints, tags)
│   ├── channels/          # Communication channels (email)
│   ├── config.py          # Environment variable configuration (DeskConfig)
│   ├── conversation/      # Conversation and message models
│   ├── db.py              # Database engine and session factory
│   ├── domain/            # Domain models and enums
│   ├── email/             # Email send/receive pipeline
│   ├── exports/           # CSV, JSON, PDF export system
│   ├── files/             # File upload and content extraction
│   ├── jobs/              # Background job runner
│   ├── knowledge/         # Knowledge base, KG extractor, RAG
│   ├── llm/               # LLM provider management, model routing
│   ├── memory/            # User-scoped memory system
│   ├── models/            # SQLAlchemy ORM models
│   ├── processes/         # Business process discovery
│   ├── prompts/           # Jinja2 prompt templates
│   ├── rbac/              # Role-based access control
│   ├── search/            # Web search integration
│   ├── security/          # Credential encryption (KMS)
│   ├── server.py          # FastAPI app factory and lifespan
│   ├── settings/          # DB-backed settings (agent, email, LLM runtime)
│   ├── tools/             # Tool execution (builtin, external, document)
│   ├── triggers/          # Auto-trigger service
│   ├── widgets/           # Chat widget parser
│   └── workflows/         # Workflow orchestration
├── frontend/              # SvelteKit frontend
│   ├── src/lib/
│   │   ├── components/    # Svelte components (admin, chat, widgets)
│   │   ├── services/      # API client functions
│   │   └── stores/        # Svelte stores (state management)
│   └── src/routes/        # SvelteKit file-based routing
├── tests/                 # Test suite (mirrors src/ structure)
├── migrations/            # Alembic database migrations
├── docs/                  # Documentation (Markdown)
└── seeds/                 # Demo data seed scripts
```

## Running Tests

### Backend

```bash
# Run the full test suite
PYTHONPATH=src python -m pytest tests/ -q

# Run a specific module
PYTHONPATH=src python -m pytest tests/agent/test_desk_agent.py -v

# Run tests matching a keyword
PYTHONPATH=src python -m pytest tests/ -k "test_knowledge" -v
```

All backend tests use an in-memory SQLite database and mock external services. No running server or network access is required.

### Frontend

```bash
cd frontend
npm run check    # TypeScript + Svelte type checking
npm run build    # Full production build (catches import errors)
```

## Database Migrations

Firefly Desk uses [Alembic](https://alembic.sqlalchemy.org/) for schema versioning. Migrations live in `migrations/versions/`.

### Creating a New Migration

After modifying SQLAlchemy models in `src/flydesk/models/`:

```bash
uv run flydesk db revision -m "add_new_column_to_table"
```

This auto-generates a migration script. Review the generated file to ensure the `upgrade()` and `downgrade()` functions are correct, then apply it:

```bash
uv run flydesk db upgrade head
```

### Migration Commands

| Command | Description |
|---------|-------------|
| `flydesk db upgrade head` | Apply all pending migrations |
| `flydesk db downgrade -1` | Revert the most recent migration |
| `flydesk db current` | Show the current schema revision |
| `flydesk db history` | List all migration revisions |
| `flydesk db revision -m "desc"` | Create a new migration |

## Code Style

### Python

- Type hints on all function signatures
- Async functions for all I/O operations
- Follow existing patterns in the module you are modifying
- No bare `except Exception: pass` -- always log with `logger.debug(..., exc_info=True)` at minimum
- Named constants for magic numbers

### Frontend (Svelte 5 + TypeScript)

- Svelte 5 runes: `$state`, `$derived`, `$bindable`, `$props`
- Tailwind CSS for styling
- `console.error` in catch blocks (never silent swallowing)
- TypeScript strict mode -- avoid `any` where possible

## Configuration Layers

Firefly Desk has two configuration layers:

1. **Environment variables** (`DeskConfig` in `config.py`) -- Set at startup via `.env` or environment. Immutable at runtime.
2. **Database settings** (`SettingsRepository`) -- Managed through the admin UI or API. Mutable at runtime. Takes precedence over env vars when both define the same concept.

When adding a new configurable value, decide which layer it belongs to based on whether it should be changeable at runtime without a restart.

## Submitting Changes

1. Create a branch from `main`
2. Make your changes with clear, focused commits
3. Ensure all tests pass (`pytest` + `npm run check`)
4. Push your branch and open a pull request against `main`
5. Describe what changed and why in the PR description

## CLI Reference

The `flydesk` CLI provides these commands:

| Command | Description |
|---------|-------------|
| `flydesk serve` | Start the backend server (`--host`, `--port`, `--reload`) |
| `flydesk dev` | Start backend + frontend for development (`--port`, `--frontend-port`, `--no-frontend`) |
| `flydesk db <cmd>` | Database migration commands (upgrade, downgrade, revision, current, history, stamp) |
| `flydesk status` | Show service status |
| `flydesk version` | Print version |
| `flydesk-seed banking` | Seed demo banking data |

## License

Firefly Desk is licensed under the Apache License, Version 2.0. By contributing, you agree that your contributions will be licensed under the same terms.
