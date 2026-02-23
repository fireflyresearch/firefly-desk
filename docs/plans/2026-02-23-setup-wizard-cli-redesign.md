# Setup Wizard, CLI Installer & First-Run Redesign

## Problem

The current setup wizard is fundamentally broken:

1. **Chicken-and-egg**: The setup wizard is chat-driven via `SetupConversationHandler`, but the LLM provider is not configured during first run. The agent cannot respond.
2. **Missing widgets**: The handler emits `dev-user-profile`, `llm-provider-setup`, and `sso-provider-setup` widget types that do not exist in the frontend registry.
3. **No CLI installer**: Users must manually clone, configure `.env`, install dependencies, and start services. No `curl | bash` install path exists.
4. **Missing `flydesk` CLI**: The `flydesk-serve` entry point is defined in `pyproject.toml` but `src/flydesk/cli.py` does not exist.

## Design Decisions

- **Setup wizard**: Dedicated `/setup` SvelteKit route with traditional form-based step wizard. No LLM dependency.
- **CLI installer**: Rich interactive `install.sh` with colored output, spinners, and progress indicators. No emojis. Falls back to plain output when piped.
- **Dead widgets**: Remove broken widget emissions from setup handler. Use only existing registered widgets.
- **Post-setup greeting**: Simple Ember welcome using existing `key-value` and `status-badge` widgets.

---

## Section 1: Setup Wizard -- Dedicated `/setup` Route

### Route Structure

```
/setup
  +page.svelte          -- Container page
  +page.server.ts       -- Server load: check setup status, redirect if done

Components:
  SetupWizard.svelte    -- Step manager, progress rail, transitions
  WelcomeStep.svelte    -- Environment detection, mode display
  LLMProviderStep.svelte -- Provider picker, API key input, test button
  UserProfileStep.svelte -- Dev mode: display name, role selection
  SSOStep.svelte        -- Prod mode: OIDC issuer, client_id, client_secret, test
  SampleDataStep.svelte -- Toggle to load banking demo data
  ReadyStep.svelte      -- Summary of configured items, launch button
```

### Step Flow

1. **Welcome**: Detect environment (dev/prod mode, database type). Display system info.
2. **LLM Provider**: Card-based provider picker (OpenAI, Anthropic, Google, Azure OpenAI, Ollama). API key input. "Test Connection" button that creates the provider via `POST /api/admin/llm-providers` and tests via `POST /api/admin/llm-providers/{id}/health`.
3. **User Profile** (dev mode only): Display name, role selector (admin/operator/viewer). Creates dev user.
4. **SSO/OIDC** (prod mode only): Issuer URL, Client ID, Client Secret inputs. "Test Discovery" button. Creates OIDC provider via existing API.
5. **Sample Data**: Toggle switch. If enabled, calls `POST /api/setup/seed` with banking preset.
6. **Ready**: Summary card showing all configured items. "Launch Firefly Desk" button calls `POST /api/setup/complete` and redirects to `/`.

### Auto-Redirect Logic

In the app layout (`frontend/src/routes/(app)/+layout.svelte`), check `GET /api/setup/status`. If `setup_completed === false`, redirect to `/setup`. The `/setup` route itself checks the opposite -- if setup is already done, redirect to `/`.

### Step Persistence

Each step POSTs partial config to `POST /api/setup/configure`. The server stores progress in the database. If the user refreshes, `GET /api/setup/wizard-state` returns the current step so the wizard resumes.

### Visual Design

- Full-page dark surface, centered content card (max-w-2xl)
- Left vertical progress rail showing step labels with checkmarks for completed steps
- Active step highlighted with accent color
- Animated slide transitions between steps
- Warm industrial aesthetic consistent with existing theme
- No emojis anywhere

---

## Section 2: `install.sh` -- Rich CLI Installer

### File: `install.sh` (project root)

A POSIX-compatible bash script with rich terminal output.

### Interactive Flow

```
  Firefly Desk Installer v0.1.0
  --

  Detecting environment...
  [ok] macOS 14.5 (arm64)
  [ok] Docker 27.1.1
  [ok] Docker Compose v2.29
  [ok] Port 8000 available
  [ok] Port 3000 available

  ? Installation mode:
    > Docker Compose (recommended)
      Local development

  Pulling images... [=============>   ] 87%

  [ok] All services healthy

  Open http://localhost:3000/setup to complete setup.
```

### Non-Interactive Mode

When piped or when flags are provided:

```bash
curl -fsSL .../install.sh | FLYDESK_MODE=docker bash
curl -fsSL .../install.sh | bash -s -- --mode docker --port 8000
```

### Pre-Flight Checks

1. Detect OS: macOS, Linux, WSL
2. Detect architecture: arm64, x86_64
3. Check required tools: Docker, Docker Compose (for docker mode) OR Python 3.13+, Node 22+, uv (for local mode)
4. Check port availability: 3000, 8000
5. Check disk space (warn if < 2GB free)

### Docker Mode

1. Create project directory (`~/.flydesk` or current directory)
2. Download `docker-compose.yml` and `.env.example`
3. Generate secure `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` via `openssl rand -base64 32`
4. `docker compose pull`
5. `docker compose up -d`
6. Wait for health checks (poll `/api/health` with retries)
7. Open browser

### Local Dev Mode

1. Verify Python >= 3.13, Node >= 22, uv installed
2. Clone repository (or use current directory if already cloned)
3. `uv sync`
4. `cd frontend && npm install`
5. Generate `.env` with SQLite defaults
6. Start backend: `uv run uvicorn flydesk.server:create_app --factory --port 8000 &`
7. Start frontend: `cd frontend && npm run dev -- --open &`
8. Wait for both healthy

### Output Conventions

- `[ok]` for success (green)
- `[!!]` for errors (red)
- `[..]` for warnings (yellow)
- `[>>]` for info (blue)
- Spinner animation for long operations (disabled when not a TTY)
- Progress bars for downloads
- No emojis

---

## Section 3: `flydesk` CLI (Python)

### File: `src/flydesk/cli.py`

Entry point: `flydesk-serve` (already in pyproject.toml). Rename to just `flydesk` for the main CLI.

### Commands

```
flydesk serve [--port PORT] [--reload]    Start the backend server
flydesk status                            Show service health and config
flydesk seed [banking] [--remove]         Manage demo data
flydesk config                            Display current configuration
flydesk version                           Show version info
```

Uses `argparse` (no extra dependency). Colored output via ANSI codes.

---

## Section 4: Backend Changes

### Remove Chat-Driven Setup

- Remove `SetupConversationHandler` class from `setup_handler.py`
- Remove `__setup_init__` handling from `chat.py`
- Remove `setup_handlers` dict from `app.state`
- Keep all setup API endpoints (`/api/setup/*`)

### Add Setup Complete Endpoint

- `POST /api/setup/complete` -- marks setup as finished in database
- `GET /api/setup/status` -- returns `{ setup_completed: bool, current_step: str, dev_mode: bool, llm_configured: bool }`

### Setup Status Storage

Store setup state in the existing `app_settings` table (already used by `SettingsRepository`):
- `setup_completed` = "true"/"false"
- `setup_current_step` = step name
- `setup_llm_provider_id` = provider ID

---

## Section 5: Post-Setup Ember Greeting

After setup completes and the user lands on the chat page for the first time, trigger a welcome message from Ember. This time the LLM IS configured, so the agent can respond.

The `ChatContainer.svelte` checks if `setup_just_completed` flag is set (via URL param or store), and sends a `__welcome__` message to the agent. The agent responds with a greeting using existing widgets:

```
Welcome to Firefly Desk! Everything is configured and ready.

:::widget{type="key-value"}
{"title": "System Configuration", "items": [
  {"key": "LLM Provider", "value": "OpenAI (gpt-4o)"},
  {"key": "Database", "value": "SQLite (development)"},
  {"key": "Demo Data", "value": "Banking catalog (5 systems)"}
]}
:::

Try asking me about your systems, or type "help" to see what I can do.
```

No new widget types needed.

---

## File Inventory

### New Files

| File | Purpose |
|------|---------|
| `install.sh` | Rich CLI installer script |
| `src/flydesk/cli.py` | Python CLI (`flydesk serve`, `flydesk status`, etc.) |
| `frontend/src/routes/setup/+page.svelte` | Setup wizard page |
| `frontend/src/routes/setup/+page.server.ts` | Setup page server loader |
| `frontend/src/lib/components/setup/SetupWizard.svelte` | Step manager component |
| `frontend/src/lib/components/setup/WelcomeStep.svelte` | Welcome step |
| `frontend/src/lib/components/setup/LLMProviderStep.svelte` | LLM config step |
| `frontend/src/lib/components/setup/UserProfileStep.svelte` | Dev user profile step |
| `frontend/src/lib/components/setup/SSOStep.svelte` | SSO/OIDC config step |
| `frontend/src/lib/components/setup/SampleDataStep.svelte` | Demo data step |
| `frontend/src/lib/components/setup/ReadyStep.svelte` | Completion step |

### Modified Files

| File | Change |
|------|--------|
| `src/flydesk/agent/setup_handler.py` | Remove or gut `SetupConversationHandler` |
| `src/flydesk/api/chat.py` | Remove `__setup_init__` handling |
| `src/flydesk/api/setup.py` | Add `POST /api/setup/complete`, enhance `GET /api/setup/status` |
| `src/flydesk/server.py` | Remove `setup_handlers` from app state |
| `frontend/src/lib/services/chat.ts` | Remove `checkFirstRun` / `__setup_init__` flow |
| `frontend/src/lib/components/chat/ChatContainer.svelte` | Remove setup init, add post-setup welcome |
| `frontend/src/routes/(app)/+layout.svelte` | Add setup redirect check |
| `pyproject.toml` | Rename entry point to `flydesk` |

### Removed Code

| What | Why |
|------|-----|
| `SetupConversationHandler` class | Replaced by form-based wizard |
| `__setup_init__` message handling | No longer needed |
| `dev-user-profile` widget references | Never existed as frontend component |
| `llm-provider-setup` widget references | Replaced by dedicated form step |
| `sso-provider-setup` widget references | Replaced by dedicated form step |
