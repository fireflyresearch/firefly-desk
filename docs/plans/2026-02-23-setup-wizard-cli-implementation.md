# Setup Wizard, CLI & Installer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Replace the broken chat-driven setup wizard with a dedicated form-based `/setup` route, create a `flydesk` CLI, and build a `curl | bash` installer script.

**Architecture:** The setup wizard becomes a SvelteKit page at `/setup` with multi-step form UI. No LLM dependency during setup. The backend's existing `/api/setup/configure` endpoint handles persistence. A new `install.sh` script automates environment detection and service startup. A Python CLI (`src/flydesk/cli.py`) provides management commands.

**Tech Stack:** SvelteKit 5 (runes), Tailwind 4, FastAPI, argparse (CLI), bash (installer)

---

## Task 1: Backend -- Add Setup Status Endpoint & Remove Chat Setup

**Files:**
- Modify: `src/flydesk/api/setup.py`
- Modify: `src/flydesk/api/chat.py`
- Modify: `src/flydesk/server.py`

**What to do:**

1. In `src/flydesk/api/setup.py`, enhance the `SetupStatus` model and `get_setup_status()` endpoint:

Add `setup_completed` and `llm_configured` fields to `SetupStatus`:

```python
class SetupStatus(BaseModel):
    """Current deployment status returned by the setup endpoint."""
    dev_mode: bool
    database_configured: bool
    oidc_configured: bool
    has_seed_data: bool
    setup_completed: bool
    llm_configured: bool
    app_title: str
    app_version: str
    agent_name: str
    accent_color: str
```

Update `get_setup_status()` to populate these:

```python
@router.get("/status")
async def get_setup_status(request: Request) -> SetupStatus:
    from flydesk import __version__
    from flydesk.config import get_config

    config = get_config()
    session_factory = getattr(request.app.state, "session_factory", None)

    has_seed = False
    setup_completed = False
    llm_configured = False

    if session_factory:
        from flydesk.catalog.repository import CatalogRepository
        from flydesk.settings.repository import SettingsRepository

        repo = CatalogRepository(session_factory)
        systems = await repo.list_systems()
        has_seed = len(systems) > 0

        settings_repo = SettingsRepository(session_factory)
        completed = await settings_repo.get_app_setting("setup_completed")
        setup_completed = completed == "true"

        from flydesk.llm.repository import LLMProviderRepository
        llm_repo = LLMProviderRepository(session_factory, config.credential_encryption_key)
        providers = await llm_repo.list_providers()
        llm_configured = len(providers) > 0

    return SetupStatus(
        dev_mode=config.dev_mode,
        database_configured="sqlite" not in config.database_url,
        oidc_configured=bool(config.oidc_issuer_url),
        has_seed_data=has_seed,
        setup_completed=setup_completed,
        llm_configured=llm_configured,
        app_title=config.app_title,
        app_version=__version__,
        agent_name=config.agent_name,
        accent_color=config.accent_color,
    )
```

2. Add a `POST /api/setup/complete` endpoint to `setup.py`:

```python
@router.post("/complete")
async def complete_setup(request: Request) -> dict:
    """Mark setup as complete."""
    session_factory = getattr(request.app.state, "session_factory", None)
    if not session_factory:
        return {"success": False, "message": "Database not initialised"}

    from flydesk.settings.repository import SettingsRepository
    settings_repo = SettingsRepository(session_factory)
    now = datetime.now(timezone.utc).isoformat()
    await settings_repo.set_app_setting("setup_completed", "true", category="setup")
    await settings_repo.set_app_setting("setup_completed_at", now, category="setup")
    return {"success": True}
```

3. In `src/flydesk/api/chat.py`, remove the setup handler integration. Delete lines 368-403 (the `is_setup_init` / `has_active_setup` block). The entire setup handler section gets replaced with a simple no-op:

```python
    # Setup init messages are no longer handled here.
    # The /setup route handles first-run configuration.
    if body.message == "__setup_init__":
        async def setup_redirect_stream():
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": "Setup is handled via the setup wizard. Please visit /setup to configure Firefly Desk."},
            ).to_sse()
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={"conversation_id": conversation_id},
            ).to_sse()
        return StreamingResponse(
            setup_redirect_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )
```

4. In `src/flydesk/server.py`, remove `app.state.setup_handlers = {}` from the lifespan (line 291). Remove the `from flydesk.agent.setup_handler import SetupConversationHandler` import from chat.py.

**Run tests:**

```bash
uv run python -m pytest tests/ -q --tb=short
```

All 655 tests should pass (setup handler tests may fail -- update those in the next task).

**Commit:**

```bash
git add src/flydesk/api/setup.py src/flydesk/api/chat.py src/flydesk/server.py
git commit -m "refactor: replace chat-driven setup with form-based wizard backend"
```

---

## Task 2: Update Setup Tests

**Files:**
- Modify: `tests/api/test_setup_api.py` (if it exists, otherwise skip)
- Modify: `tests/agent/test_setup_handler.py`

**What to do:**

The existing `test_setup_handler.py` tests the `SetupConversationHandler` class which is being replaced. The tests should be updated to:

1. Remove tests that test the chat-driven handler flow (welcome, LLM provider step, etc.).
2. Keep or add tests for the `/api/setup/status` endpoint (should return `setup_completed` and `llm_configured` fields).
3. Keep or add tests for the `/api/setup/complete` endpoint.
4. Keep or add tests for the `/api/setup/configure` endpoint.

For `test_setup_handler.py`, add a header comment saying the SetupConversationHandler is deprecated and will be removed. Do NOT delete the file yet (it may be referenced elsewhere). Simply mark the test class with `@pytest.mark.skip(reason="SetupConversationHandler replaced by form wizard")`.

**Run tests:**

```bash
uv run python -m pytest tests/ -q --tb=short
```

All tests should pass.

**Commit:**

```bash
git add tests/
git commit -m "test: update setup tests for form-based wizard"
```

---

## Task 3: Frontend -- Create `/setup` Route with Wizard Shell

**Files:**
- Create: `frontend/src/routes/setup/+page.svelte`
- Create: `frontend/src/routes/setup/+page.server.ts`
- Create: `frontend/src/lib/components/setup/SetupWizard.svelte`

**What to do:**

1. Create `frontend/src/routes/setup/+page.server.ts` -- server load function that checks setup status:

```typescript
import type { PageServerLoad } from './$types';
import { redirect } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch }) => {
    try {
        const res = await fetch('/api/setup/status');
        if (res.ok) {
            const status = await res.json();
            if (status.setup_completed) {
                throw redirect(303, '/');
            }
            return { status };
        }
    } catch (e) {
        if (e instanceof Response || (e as any)?.status === 303) throw e;
    }
    return { status: null };
};
```

2. Create `frontend/src/routes/setup/+page.svelte`:

```svelte
<!--
  Setup Wizard page -- guides first-run configuration.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import '../../app.css';
    import SetupWizard from '$lib/components/setup/SetupWizard.svelte';
    import { initTheme, resolvedTheme } from '$lib/stores/theme';
    import favicon from '$lib/assets/favicon.svg';
    import { onMount } from 'svelte';

    let { data } = $props();

    onMount(() => {
        initTheme();
    });

    $effect(() => {
        document.documentElement.dataset.theme = $resolvedTheme;
    });
</script>

<svelte:head>
    <link rel="icon" href={favicon} />
    <title>Setup - Firefly Desk</title>
</svelte:head>

<SetupWizard status={data.status} />
```

3. Create `frontend/src/lib/components/setup/SetupWizard.svelte` -- the main wizard shell:

```svelte
<!--
  SetupWizard.svelte - Multi-step setup wizard with progress rail.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { Check } from 'lucide-svelte';
    import WelcomeStep from './WelcomeStep.svelte';
    import LLMProviderStep from './LLMProviderStep.svelte';
    import UserProfileStep from './UserProfileStep.svelte';
    import SampleDataStep from './SampleDataStep.svelte';
    import ReadyStep from './ReadyStep.svelte';

    interface SetupStatus {
        dev_mode: boolean;
        setup_completed: boolean;
        llm_configured: boolean;
        has_seed_data: boolean;
        app_title: string;
        app_version: string;
        agent_name: string;
    }

    let { status }: { status: SetupStatus | null } = $props();

    // Determine which steps apply
    let steps = $derived.by(() => {
        const base = [
            { id: 'welcome', label: 'Welcome' },
            { id: 'llm', label: 'LLM Provider' },
        ];
        if (status?.dev_mode) {
            base.push({ id: 'profile', label: 'User Profile' });
        }
        base.push({ id: 'data', label: 'Sample Data' });
        base.push({ id: 'ready', label: 'Ready' });
        return base;
    });

    let currentStepIndex = $state(0);
    let completedSteps = $state<Set<string>>(new Set());
    let wizardData = $state<Record<string, unknown>>({});

    let currentStep = $derived(steps[currentStepIndex]);

    function handleNext(stepData?: Record<string, unknown>) {
        if (stepData) {
            wizardData = { ...wizardData, ...stepData };
        }
        completedSteps.add(currentStep.id);
        completedSteps = new Set(completedSteps);
        if (currentStepIndex < steps.length - 1) {
            currentStepIndex++;
        }
    }

    function handleBack() {
        if (currentStepIndex > 0) {
            currentStepIndex--;
        }
    }
</script>

<div class="flex min-h-screen items-center justify-center bg-surface p-4">
    <div class="flex w-full max-w-4xl overflow-hidden rounded-2xl border border-border bg-surface-secondary shadow-xl">
        <!-- Progress rail -->
        <nav class="hidden w-56 shrink-0 border-r border-border bg-surface p-6 sm:block">
            <h2 class="mb-6 text-xs font-bold uppercase tracking-wider text-text-secondary">Setup</h2>
            <ol class="space-y-1">
                {#each steps as step, i}
                    {@const isActive = i === currentStepIndex}
                    {@const isDone = completedSteps.has(step.id)}
                    <li class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm
                        {isActive ? 'bg-accent/10 font-semibold text-accent' : ''}
                        {isDone && !isActive ? 'text-success' : ''}
                        {!isActive && !isDone ? 'text-text-secondary' : ''}
                    ">
                        {#if isDone}
                            <Check class="h-4 w-4 text-success" />
                        {:else}
                            <span class="flex h-4 w-4 items-center justify-center rounded-full border text-[10px]
                                {isActive ? 'border-accent text-accent' : 'border-text-secondary/40 text-text-secondary/60'}
                            ">{i + 1}</span>
                        {/if}
                        <span>{step.label}</span>
                    </li>
                {/each}
            </ol>
        </nav>

        <!-- Step content -->
        <main class="flex-1 p-8">
            {#if currentStep.id === 'welcome'}
                <WelcomeStep {status} onNext={handleNext} />
            {:else if currentStep.id === 'llm'}
                <LLMProviderStep onNext={handleNext} onBack={handleBack} />
            {:else if currentStep.id === 'profile'}
                <UserProfileStep onNext={handleNext} onBack={handleBack} />
            {:else if currentStep.id === 'data'}
                <SampleDataStep onNext={handleNext} onBack={handleBack} />
            {:else if currentStep.id === 'ready'}
                <ReadyStep data={wizardData} {status} onBack={handleBack} />
            {/if}
        </main>
    </div>
</div>
```

**Build:**

```bash
cd frontend && npm run build
```

Should build without errors (step components don't exist yet, so build will fail. That's expected -- they come in the next tasks).

**Commit:**

```bash
git add frontend/src/routes/setup/ frontend/src/lib/components/setup/SetupWizard.svelte
git commit -m "feat: add setup wizard route and shell component"
```

---

## Task 4: Frontend -- WelcomeStep Component

**Files:**
- Create: `frontend/src/lib/components/setup/WelcomeStep.svelte`

**What to do:**

Create the welcome step component. Shows:
- Firefly Desk logo/title
- Environment detection summary (dev mode, database type)
- Brief explanation of what the wizard will configure
- "Get Started" button

```svelte
<!--
  WelcomeStep.svelte - First step: environment overview.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { Flame, Database, Shield, Monitor } from 'lucide-svelte';
    import EmberAvatar from '../chat/EmberAvatar.svelte';

    interface SetupStatus {
        dev_mode: boolean;
        app_title: string;
        app_version: string;
        agent_name: string;
        database_configured: boolean;
    }

    let { status, onNext }: {
        status: SetupStatus | null;
        onNext: () => void;
    } = $props();
</script>

<div class="flex flex-col items-center text-center">
    <EmberAvatar size={56} />

    <h1 class="mt-6 text-2xl font-bold text-text-primary">Welcome to {status?.app_title ?? 'Firefly Desk'}</h1>
    <p class="mt-2 text-text-secondary">
        Let's configure your instance. This takes about 2 minutes.
    </p>

    <div class="mt-8 w-full max-w-sm space-y-3 text-left">
        <div class="flex items-center gap-3 rounded-lg border border-border p-3">
            <Monitor class="h-5 w-5 text-accent" />
            <div>
                <p class="text-sm font-medium text-text-primary">Mode</p>
                <p class="text-xs text-text-secondary">{status?.dev_mode ? 'Development' : 'Production'}</p>
            </div>
        </div>
        <div class="flex items-center gap-3 rounded-lg border border-border p-3">
            <Database class="h-5 w-5 text-accent" />
            <div>
                <p class="text-sm font-medium text-text-primary">Database</p>
                <p class="text-xs text-text-secondary">{status?.database_configured ? 'PostgreSQL' : 'SQLite (local)'}</p>
            </div>
        </div>
        <div class="flex items-center gap-3 rounded-lg border border-border p-3">
            <Flame class="h-5 w-5 text-ember" />
            <div>
                <p class="text-sm font-medium text-text-primary">Agent</p>
                <p class="text-xs text-text-secondary">{status?.agent_name ?? 'Ember'} v{status?.app_version ?? '0.1.0'}</p>
            </div>
        </div>
    </div>

    <button
        class="mt-8 rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-white transition-all hover:bg-accent-hover hover:-translate-y-0.5"
        onclick={onNext}
    >
        Get Started
    </button>
</div>
```

**Build:**

```bash
cd frontend && npx svelte-check
```

**Commit:**

```bash
git add frontend/src/lib/components/setup/WelcomeStep.svelte
git commit -m "feat: add setup wizard welcome step"
```

---

## Task 5: Frontend -- LLMProviderStep Component

**Files:**
- Create: `frontend/src/lib/components/setup/LLMProviderStep.svelte`

**What to do:**

This is the most important step. It:
1. Shows provider cards (OpenAI, Anthropic, Google, Azure OpenAI, Ollama)
2. When a provider is selected, shows the API key input (and base_url for Ollama/Azure)
3. Has a "Test Connection" button that creates the provider via the admin API and tests it
4. Shows success/failure status

```svelte
<!--
  LLMProviderStep.svelte - Configure the LLM provider.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { Loader2, CheckCircle, XCircle, ArrowLeft, ArrowRight, Eye, EyeOff } from 'lucide-svelte';
    import { apiJson, apiFetch } from '$lib/services/api.js';

    let { onNext, onBack }: {
        onNext: (data: Record<string, unknown>) => void;
        onBack: () => void;
    } = $props();

    const PROVIDERS = [
        { type: 'openai', name: 'OpenAI', description: 'GPT-4o, GPT-4, GPT-3.5', needsKey: true },
        { type: 'anthropic', name: 'Anthropic', description: 'Claude 4, Claude 3.5', needsKey: true },
        { type: 'google', name: 'Google', description: 'Gemini Pro, Gemini Flash', needsKey: true },
        { type: 'azure_openai', name: 'Azure OpenAI', description: 'Azure-hosted OpenAI models', needsKey: true, needsUrl: true },
        { type: 'ollama', name: 'Ollama', description: 'Local models (Llama, Mistral)', needsKey: false, needsUrl: true },
    ] as const;

    let selectedProvider = $state<string | null>(null);
    let apiKey = $state('');
    let baseUrl = $state('');
    let showKey = $state(false);
    let testing = $state(false);
    let testResult = $state<{ success: boolean; message: string; latency?: number } | null>(null);
    let createdProviderId = $state<string | null>(null);

    let providerConfig = $derived(PROVIDERS.find(p => p.type === selectedProvider));

    async function testConnection() {
        if (!selectedProvider) return;
        testing = true;
        testResult = null;

        try {
            // Create provider via admin API
            const id = createdProviderId ?? crypto.randomUUID();
            const payload = {
                id,
                name: providerConfig!.name,
                provider_type: selectedProvider,
                api_key: apiKey || null,
                base_url: baseUrl || null,
                is_default: true,
                is_active: true,
            };

            if (createdProviderId) {
                await apiFetch(`/admin/llm-providers/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                });
            } else {
                await apiFetch('/admin/llm-providers', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
                createdProviderId = id;
            }

            // Test connectivity
            const health = await apiJson<{
                reachable: boolean;
                latency_ms: number | null;
                error: string | null;
            }>(`/admin/llm-providers/${id}/test`, { method: 'POST' });

            if (health.reachable) {
                testResult = {
                    success: true,
                    message: `Connected successfully (${Math.round(health.latency_ms ?? 0)}ms)`,
                    latency: health.latency_ms ?? undefined,
                };
            } else {
                testResult = {
                    success: false,
                    message: health.error ?? 'Connection failed',
                };
            }
        } catch (error) {
            testResult = {
                success: false,
                message: error instanceof Error ? error.message : 'Unknown error',
            };
        } finally {
            testing = false;
        }
    }

    function handleNext() {
        onNext({
            llm_provider: selectedProvider,
            llm_provider_name: providerConfig?.name,
            llm_provider_id: createdProviderId,
            llm_connected: testResult?.success ?? false,
        });
    }

    function handleSkip() {
        onNext({ llm_provider: null, llm_skipped: true });
    }
</script>

<div>
    <h2 class="text-xl font-bold text-text-primary">LLM Provider</h2>
    <p class="mt-1 text-sm text-text-secondary">Connect an AI model provider to power Ember's intelligence.</p>

    <!-- Provider cards -->
    <div class="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {#each PROVIDERS as provider}
            <button
                class="rounded-xl border p-4 text-left transition-all
                    {selectedProvider === provider.type
                        ? 'border-accent bg-accent/5 ring-1 ring-accent/30'
                        : 'border-border hover:border-accent/40 hover:bg-surface-hover'}"
                onclick={() => { selectedProvider = provider.type; testResult = null; }}
            >
                <p class="text-sm font-semibold text-text-primary">{provider.name}</p>
                <p class="mt-0.5 text-xs text-text-secondary">{provider.description}</p>
            </button>
        {/each}
    </div>

    <!-- Configuration form -->
    {#if selectedProvider && providerConfig}
        <div class="mt-6 space-y-4">
            {#if providerConfig.needsKey}
                <div>
                    <label for="api-key" class="block text-sm font-medium text-text-primary">API Key</label>
                    <div class="relative mt-1">
                        <input
                            id="api-key"
                            type={showKey ? 'text' : 'password'}
                            bind:value={apiKey}
                            placeholder="Enter your API key"
                            class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                        />
                        <button
                            class="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
                            onclick={() => showKey = !showKey}
                            type="button"
                        >
                            {#if showKey}<EyeOff class="h-4 w-4" />{:else}<Eye class="h-4 w-4" />{/if}
                        </button>
                    </div>
                </div>
            {/if}

            {#if providerConfig.needsUrl}
                <div>
                    <label for="base-url" class="block text-sm font-medium text-text-primary">Base URL</label>
                    <input
                        id="base-url"
                        type="url"
                        bind:value={baseUrl}
                        placeholder={selectedProvider === 'ollama' ? 'http://localhost:11434' : 'https://your-resource.openai.azure.com'}
                        class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder:text-text-secondary/50 focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                    />
                </div>
            {/if}

            <!-- Test button -->
            <button
                class="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
                onclick={testConnection}
                disabled={testing || (providerConfig.needsKey && !apiKey)}
            >
                {#if testing}
                    <Loader2 class="mr-2 inline h-4 w-4 animate-spin" />
                    Testing...
                {:else}
                    Test Connection
                {/if}
            </button>

            <!-- Test result -->
            {#if testResult}
                <div class="flex items-center gap-2 rounded-lg border p-3 text-sm
                    {testResult.success ? 'border-success/30 bg-success/5 text-success' : 'border-danger/30 bg-danger/5 text-danger'}">
                    {#if testResult.success}
                        <CheckCircle class="h-4 w-4" />
                    {:else}
                        <XCircle class="h-4 w-4" />
                    {/if}
                    <span>{testResult.message}</span>
                </div>
            {/if}
        </div>
    {/if}

    <!-- Navigation -->
    <div class="mt-8 flex items-center justify-between">
        <button class="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary" onclick={onBack}>
            <ArrowLeft class="h-4 w-4" /> Back
        </button>
        <div class="flex gap-3">
            <button class="text-sm text-text-secondary hover:text-text-primary" onclick={handleSkip}>
                Skip for now
            </button>
            <button
                class="flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
                onclick={handleNext}
                disabled={!testResult?.success && selectedProvider !== null}
            >
                Continue <ArrowRight class="h-4 w-4" />
            </button>
        </div>
    </div>
</div>
```

**Build:**

```bash
cd frontend && npx svelte-check
```

**Commit:**

```bash
git add frontend/src/lib/components/setup/LLMProviderStep.svelte
git commit -m "feat: add LLM provider setup step with connection testing"
```

---

## Task 6: Frontend -- UserProfileStep, SampleDataStep, ReadyStep

**Files:**
- Create: `frontend/src/lib/components/setup/UserProfileStep.svelte`
- Create: `frontend/src/lib/components/setup/SampleDataStep.svelte`
- Create: `frontend/src/lib/components/setup/ReadyStep.svelte`

**What to do:**

### UserProfileStep.svelte

Dev-mode only. Lets the user set their display name and role. Uses `FLYDESK_DEV_USER_*` env vars on the backend, but for the frontend wizard we just display current values and explain how to change them.

```svelte
<!--
  UserProfileStep.svelte - Dev mode user profile configuration.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { ArrowLeft, ArrowRight, User } from 'lucide-svelte';

    let { onNext, onBack }: {
        onNext: (data: Record<string, unknown>) => void;
        onBack: () => void;
    } = $props();

    let displayName = $state('Dev Admin');
    let role = $state('admin');
</script>

<div>
    <h2 class="text-xl font-bold text-text-primary">User Profile</h2>
    <p class="mt-1 text-sm text-text-secondary">
        In development mode, a synthetic user is injected automatically.
        Configure it via environment variables:
    </p>

    <div class="mt-6 space-y-4">
        <div>
            <label for="display-name" class="block text-sm font-medium text-text-primary">Display Name</label>
            <input
                id="display-name"
                type="text"
                bind:value={displayName}
                class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <p class="mt-1 text-xs text-text-secondary">Set via FLYDESK_DEV_USER_NAME</p>
        </div>

        <div>
            <label for="role" class="block text-sm font-medium text-text-primary">Role</label>
            <select
                id="role"
                bind:value={role}
                class="mt-1 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            >
                <option value="admin">Admin</option>
                <option value="operator">Operator</option>
                <option value="viewer">Viewer</option>
            </select>
            <p class="mt-1 text-xs text-text-secondary">Set via FLYDESK_DEV_USER_ROLES</p>
        </div>
    </div>

    <div class="mt-8 flex items-center justify-between">
        <button class="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary" onclick={onBack}>
            <ArrowLeft class="h-4 w-4" /> Back
        </button>
        <button
            class="flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-accent-hover"
            onclick={() => onNext({ dev_user_name: displayName, dev_user_role: role })}
        >
            Continue <ArrowRight class="h-4 w-4" />
        </button>
    </div>
</div>
```

### SampleDataStep.svelte

Toggle to load banking demo data.

```svelte
<!--
  SampleDataStep.svelte - Optional demo data loading.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { ArrowLeft, ArrowRight, Loader2, Database, CheckCircle } from 'lucide-svelte';
    import { apiFetch } from '$lib/services/api.js';

    let { onNext, onBack }: {
        onNext: (data: Record<string, unknown>) => void;
        onBack: () => void;
    } = $props();

    let loadSampleData = $state(true);
    let loading = $state(false);
    let loaded = $state(false);

    async function handleNext() {
        if (loadSampleData && !loaded) {
            loading = true;
            try {
                await apiFetch('/setup/seed', {
                    method: 'POST',
                    body: JSON.stringify({ domain: 'banking', remove: false }),
                });
                loaded = true;
            } catch (error) {
                console.error('[Setup] Failed to seed data:', error);
            } finally {
                loading = false;
            }
        }
        onNext({ seed_data: loadSampleData });
    }
</script>

<div>
    <h2 class="text-xl font-bold text-text-primary">Sample Data</h2>
    <p class="mt-1 text-sm text-text-secondary">
        Optionally load demo data to explore Firefly Desk's capabilities.
    </p>

    <div class="mt-6">
        <label class="flex cursor-pointer items-center gap-4 rounded-xl border border-border p-4 transition-all hover:bg-surface-hover
            {loadSampleData ? 'border-accent/30 bg-accent/5' : ''}">
            <input
                type="checkbox"
                bind:checked={loadSampleData}
                class="h-4 w-4 rounded border-border text-accent focus:ring-accent"
            />
            <div class="flex-1">
                <div class="flex items-center gap-2">
                    <Database class="h-4 w-4 text-accent" />
                    <p class="text-sm font-semibold text-text-primary">Banking Demo Catalog</p>
                </div>
                <p class="mt-1 text-xs text-text-secondary">
                    5 banking systems with endpoints, credentials, and knowledge documents.
                    Ideal for exploring the service catalog, knowledge base, and agent capabilities.
                </p>
            </div>
            {#if loaded}
                <CheckCircle class="h-5 w-5 text-success" />
            {/if}
        </label>
    </div>

    <div class="mt-8 flex items-center justify-between">
        <button class="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary" onclick={onBack}>
            <ArrowLeft class="h-4 w-4" /> Back
        </button>
        <button
            class="flex items-center gap-1 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white transition-all hover:bg-accent-hover disabled:opacity-50"
            onclick={handleNext}
            disabled={loading}
        >
            {#if loading}
                <Loader2 class="mr-1 h-4 w-4 animate-spin" /> Loading...
            {:else}
                Continue <ArrowRight class="h-4 w-4" />
            {/if}
        </button>
    </div>
</div>
```

### ReadyStep.svelte

Summary and launch button. Calls `POST /api/setup/complete` and redirects to `/`.

```svelte
<!--
  ReadyStep.svelte - Setup complete summary and launch.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { ArrowLeft, CheckCircle, Loader2, Flame, ExternalLink } from 'lucide-svelte';
    import { apiFetch } from '$lib/services/api.js';

    let { data, status, onBack }: {
        data: Record<string, unknown>;
        status: { agent_name: string; app_title: string } | null;
        onBack: () => void;
    } = $props();

    let launching = $state(false);

    let summaryItems = $derived.by(() => {
        const items: Array<{ label: string; value: string; ok: boolean }> = [];

        if (data.llm_provider) {
            items.push({
                label: 'LLM Provider',
                value: data.llm_provider_name as string,
                ok: data.llm_connected as boolean,
            });
        } else {
            items.push({ label: 'LLM Provider', value: 'Skipped', ok: false });
        }

        if (data.dev_user_name) {
            items.push({
                label: 'Dev User',
                value: `${data.dev_user_name} (${data.dev_user_role})`,
                ok: true,
            });
        }

        items.push({
            label: 'Sample Data',
            value: data.seed_data ? 'Banking demo loaded' : 'None',
            ok: !!data.seed_data,
        });

        return items;
    });

    async function launch() {
        launching = true;
        try {
            await apiFetch('/setup/complete', { method: 'POST' });
            window.location.href = '/';
        } catch (error) {
            console.error('[Setup] Failed to complete setup:', error);
            launching = false;
        }
    }
</script>

<div class="flex flex-col items-center text-center">
    <div class="flex h-14 w-14 items-center justify-center rounded-full bg-success/10">
        <Flame class="h-7 w-7 text-ember" />
    </div>

    <h2 class="mt-4 text-xl font-bold text-text-primary">Ready to Launch</h2>
    <p class="mt-1 text-sm text-text-secondary">
        {status?.agent_name ?? 'Ember'} is configured and ready to assist you.
    </p>

    <!-- Summary -->
    <div class="mt-6 w-full max-w-sm space-y-2 text-left">
        {#each summaryItems as item}
            <div class="flex items-center justify-between rounded-lg border border-border px-4 py-2.5">
                <span class="text-sm text-text-secondary">{item.label}</span>
                <span class="flex items-center gap-1.5 text-sm font-medium {item.ok ? 'text-success' : 'text-text-secondary'}">
                    {#if item.ok}<CheckCircle class="h-3.5 w-3.5" />{/if}
                    {item.value}
                </span>
            </div>
        {/each}
    </div>

    <!-- Launch -->
    <div class="mt-8 flex items-center gap-4">
        <button class="flex items-center gap-1 text-sm text-text-secondary hover:text-text-primary" onclick={onBack}>
            <ArrowLeft class="h-4 w-4" /> Back
        </button>
        <button
            class="rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-white transition-all hover:bg-accent-hover hover:-translate-y-0.5 disabled:opacity-50"
            onclick={launch}
            disabled={launching}
        >
            {#if launching}
                <Loader2 class="mr-2 inline h-4 w-4 animate-spin" /> Launching...
            {:else}
                Launch {status?.app_title ?? 'Firefly Desk'}
            {/if}
        </button>
    </div>
</div>
```

**Build:**

```bash
cd frontend && npm run build
```

Should build successfully now that all step components exist.

**Commit:**

```bash
git add frontend/src/lib/components/setup/
git commit -m "feat: add user profile, sample data, and ready steps for setup wizard"
```

---

## Task 7: Frontend -- Remove Chat-Driven Setup from ChatContainer

**Files:**
- Modify: `frontend/src/lib/components/chat/ChatContainer.svelte`
- Modify: `frontend/src/lib/services/chat.ts`
- Modify: `frontend/src/routes/(app)/+layout.svelte`

**What to do:**

1. In `ChatContainer.svelte`, remove the entire `$effect` block (lines 41-64) that calls `checkFirstRun()` and sends `__setup_init__`. Remove the `checkingFirstRun` state variable. Remove the `checkFirstRun` import.

2. In `chat.ts`, remove the `checkFirstRun()` function (lines 114-124).

3. In `frontend/src/routes/(app)/+layout.svelte`, add a setup redirect check. Before rendering the AppShell, check if setup is completed:

```svelte
<script lang="ts">
    import AppShell from '$lib/components/layout/AppShell.svelte';
    import PanelContainer from '$lib/components/panels/PanelContainer.svelte';
    import { panelVisible } from '$lib/stores/panel.js';
    import { initCurrentUser } from '$lib/stores/user.js';
    import { onMount } from 'svelte';

    let { children } = $props();
    let setupChecked = $state(false);

    $effect(() => {
        initCurrentUser();
    });

    onMount(async () => {
        try {
            const res = await fetch('/api/setup/status');
            if (res.ok) {
                const status = await res.json();
                if (!status.setup_completed) {
                    window.location.href = '/setup';
                    return;
                }
            }
        } catch {
            // If we can't check, proceed normally
        }
        setupChecked = true;
    });
</script>

{#if setupChecked}
    <AppShell panelVisible={$panelVisible}>
        {#snippet panel()}
            <PanelContainer />
        {/snippet}
        {@render children()}
    </AppShell>
{/if}
```

**Build:**

```bash
cd frontend && npm run build
```

**Run backend tests:**

```bash
uv run python -m pytest tests/ -q --tb=short
```

**Commit:**

```bash
git add frontend/src/lib/components/chat/ChatContainer.svelte frontend/src/lib/services/chat.ts frontend/src/routes/\(app\)/+layout.svelte
git commit -m "refactor: remove chat-driven setup, add /setup redirect in app layout"
```

---

## Task 8: Create `flydesk` CLI

**Files:**
- Create: `src/flydesk/cli.py`
- Modify: `pyproject.toml`

**What to do:**

1. Create `src/flydesk/cli.py`:

```python
# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Firefly Desk CLI -- management commands."""

from __future__ import annotations

import argparse
import sys


def serve(args: argparse.Namespace | None = None) -> None:
    """Start the Firefly Desk backend server."""
    import uvicorn

    port = getattr(args, "port", None) or 8000
    reload = getattr(args, "reload", False)

    uvicorn.run(
        "flydesk.server:create_app",
        factory=True,
        host="0.0.0.0",
        port=port,
        reload=reload,
    )


def status(args: argparse.Namespace | None = None) -> None:
    """Show current configuration and service status."""
    try:
        from flydesk import __version__
        from flydesk.config import get_config

        config = get_config()
        print(f"Firefly Desk v{__version__}")
        print(f"  Mode:     {'development' if config.dev_mode else 'production'}")
        print(f"  Database: {config.database_url.split('@')[-1] if '@' in config.database_url else config.database_url}")
        print(f"  Agent:    {config.agent_name}")
        print(f"  Title:    {config.app_title}")
    except Exception as exc:
        print(f"[!!] Failed to load config: {exc}", file=sys.stderr)
        sys.exit(1)


def version(args: argparse.Namespace | None = None) -> None:
    """Print version and exit."""
    from flydesk import __version__
    print(f"flydesk {__version__}")


def main() -> None:
    """Entry point for the flydesk CLI."""
    parser = argparse.ArgumentParser(
        prog="flydesk",
        description="Firefly Desk -- Backoffice as Agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the backend server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.set_defaults(func=serve)

    # status
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.set_defaults(func=status)

    # version
    version_parser = subparsers.add_parser("version", help="Print version")
    version_parser.set_defaults(func=version)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
```

2. Update `pyproject.toml` scripts section to replace both entry points:

```toml
[project.scripts]
flydesk = "flydesk.cli:main"
flydesk-seed = "flydesk.seeds.cli:main"
```

This replaces the old `flydesk-serve = "flydesk.cli:serve"` with the unified `flydesk` CLI.

3. Reinstall the package:

```bash
uv pip install -e .
```

4. Test the CLI:

```bash
uv run flydesk version
uv run flydesk status
uv run flydesk serve --help
```

**Run tests:**

```bash
uv run python -m pytest tests/ -q --tb=short
```

**Commit:**

```bash
git add src/flydesk/cli.py pyproject.toml
git commit -m "feat: add flydesk CLI with serve, status, and version commands"
```

---

## Task 9: Create `install.sh`

**Files:**
- Create: `install.sh`

**What to do:**

Create a rich interactive bash installer script. Key features:
- Detects OS, architecture, Docker, Node, Python
- Two modes: Docker Compose or Local Development
- Colored output with `[ok]`, `[!!]`, `[..]`, `[>>]` status indicators
- No emojis
- Animated spinner for long operations
- TTY detection for interactive vs piped mode
- Generates secure encryption key
- Opens browser at the end

The script should be approximately 300-400 lines. Focus on:
- POSIX-compatible where possible (bash required for select menus)
- Clean error handling with descriptive messages
- Idempotent (safe to run multiple times)
- Supports `--mode docker|local`, `--port N` flags for non-interactive use
- Supports `FLYDESK_MODE` env var for piped usage

Key functions:
- `detect_os()` -- returns darwin/linux
- `detect_arch()` -- returns arm64/x86_64
- `check_command()` -- verifies a command exists
- `check_port()` -- verifies a port is available
- `print_ok()`, `print_err()`, `print_warn()`, `print_info()` -- colored output
- `spin()` -- animated spinner for background commands
- `generate_key()` -- generates encryption key via openssl
- `install_docker()` -- Docker Compose installation path
- `install_local()` -- Local development installation path

The script header:

```bash
#!/usr/bin/env bash
# Copyright 2026 Firefly Software Solutions Inc
# Licensed under the Apache License, Version 2.0
#
# Firefly Desk Installer
# Usage:
#   Interactive:     bash <(curl -fsSL https://get.flydesk.dev/install.sh)
#   Non-interactive: curl -fsSL ... | FLYDESK_MODE=docker bash
#   With flags:      curl -fsSL ... | bash -s -- --mode local --port 8000

set -euo pipefail
```

Make the script executable:

```bash
chmod +x install.sh
```

**Test locally:**

```bash
bash install.sh --help
```

**Commit:**

```bash
git add install.sh
git commit -m "feat: add install.sh rich CLI installer script"
```

---

## Task 10: End-to-End Verification

**What to do:**

1. Run the full test suite:

```bash
uv run python -m pytest tests/ -q --tb=short
```

All tests should pass.

2. Build the frontend:

```bash
cd frontend && npm run build
```

Should build without errors.

3. Run svelte-check:

```bash
cd frontend && npx svelte-check
```

Should have no errors.

4. Manual verification:
   - Delete the dev database: `rm -f flydesk_dev.db`
   - Start the backend: `uv run flydesk serve --port 8000 --reload`
   - Start the frontend: `cd frontend && npm run dev -- --open`
   - Browser should open. The app layout should redirect to `/setup`.
   - Walk through the setup wizard:
     - Welcome step shows environment info
     - LLM Provider step shows provider cards
     - Sample Data step offers banking demo
     - Ready step shows summary and "Launch" button
   - Click Launch -- should redirect to `/` with the chat interface
   - The old chat-driven setup should NOT appear

5. Verify the CLI:

```bash
uv run flydesk version
uv run flydesk status
```

6. Verify install.sh syntax:

```bash
bash -n install.sh
```

**Commit (if any fixes needed):**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes for setup wizard"
```

---

## File Inventory

### New Files (12)

| File | Task |
|------|------|
| `frontend/src/routes/setup/+page.svelte` | 3 |
| `frontend/src/routes/setup/+page.server.ts` | 3 |
| `frontend/src/lib/components/setup/SetupWizard.svelte` | 3 |
| `frontend/src/lib/components/setup/WelcomeStep.svelte` | 4 |
| `frontend/src/lib/components/setup/LLMProviderStep.svelte` | 5 |
| `frontend/src/lib/components/setup/UserProfileStep.svelte` | 6 |
| `frontend/src/lib/components/setup/SampleDataStep.svelte` | 6 |
| `frontend/src/lib/components/setup/ReadyStep.svelte` | 6 |
| `src/flydesk/cli.py` | 8 |
| `install.sh` | 9 |

### Modified Files (7)

| File | Task |
|------|------|
| `src/flydesk/api/setup.py` | 1 |
| `src/flydesk/api/chat.py` | 1 |
| `src/flydesk/server.py` | 1 |
| `tests/agent/test_setup_handler.py` | 2 |
| `frontend/src/lib/components/chat/ChatContainer.svelte` | 7 |
| `frontend/src/lib/services/chat.ts` | 7 |
| `frontend/src/routes/(app)/+layout.svelte` | 7 |
| `pyproject.toml` | 8 |
