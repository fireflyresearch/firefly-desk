<!--
  LLMProviderStep.svelte -- Configure an LLM provider during setup.

  Presents provider cards, model selector, API key input, and a "Test
  Connection" button that validates credentials via POST /api/setup/test-llm
  (no auth required). The selected provider + model info is passed to the
  wizard for later submission via POST /api/setup/configure.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Loader2,
		CheckCircle,
		XCircle,
		ArrowLeft,
		ArrowRight,
		Eye,
		EyeOff
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface LLMProviderStepProps {
		status: Record<string, unknown> | null;
		onNext: (data?: Record<string, unknown>) => void;
		onBack: () => void;
	}

	let { status, onNext, onBack }: LLMProviderStepProps = $props();

	// -----------------------------------------------------------------------
	// Provider definitions with available models
	// -----------------------------------------------------------------------

	interface ModelDef {
		id: string;
		name: string;
	}

	interface ProviderDef {
		id: string;
		name: string;
		description: string;
		needsBaseUrl: boolean;
		needsApiKey: boolean;
		baseUrlPlaceholder?: string;
		models: ModelDef[];
		allowCustomModel: boolean;
	}

	const providers: ProviderDef[] = [
		{
			id: 'openai',
			name: 'OpenAI',
			description: 'GPT-4o, o1, and more',
			needsBaseUrl: false,
			needsApiKey: true,
			models: [
				{ id: 'gpt-4o', name: 'GPT-4o' },
				{ id: 'gpt-4o-mini', name: 'GPT-4o Mini' },
				{ id: 'gpt-4.1', name: 'GPT-4.1' },
				{ id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini' },
				{ id: 'o3', name: 'o3' },
				{ id: 'o4-mini', name: 'o4 Mini' }
			],
			allowCustomModel: true
		},
		{
			id: 'anthropic',
			name: 'Anthropic',
			description: 'Claude Opus, Sonnet, Haiku',
			needsBaseUrl: false,
			needsApiKey: true,
			models: [
				{ id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4' },
				{ id: 'claude-opus-4-20250514', name: 'Claude Opus 4' },
				{ id: 'claude-haiku-4-5-20251001', name: 'Claude 4.5 Haiku' }
			],
			allowCustomModel: true
		},
		{
			id: 'google',
			name: 'Google',
			description: 'Gemini 2.5 Pro, Flash',
			needsBaseUrl: false,
			needsApiKey: true,
			models: [
				{ id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro' },
				{ id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash' },
				{ id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash' }
			],
			allowCustomModel: true
		},
		{
			id: 'azure_openai',
			name: 'Azure OpenAI',
			description: 'Your deployed models',
			needsBaseUrl: true,
			needsApiKey: true,
			baseUrlPlaceholder: 'https://your-resource.openai.azure.com',
			models: [],
			allowCustomModel: true
		},
		{
			id: 'ollama',
			name: 'Ollama',
			description: 'Local models',
			needsBaseUrl: true,
			needsApiKey: false,
			baseUrlPlaceholder: 'http://localhost:11434',
			models: [
				{ id: 'llama3.1', name: 'Llama 3.1' },
				{ id: 'mistral', name: 'Mistral' },
				{ id: 'codellama', name: 'Code Llama' },
				{ id: 'mixtral', name: 'Mixtral' }
			],
			allowCustomModel: true
		}
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selectedProvider = $state<string | null>(null);
	let selectedModel = $state<string>('');
	let customModel = $state('');
	let apiKey = $state('');
	let baseUrl = $state('');
	let showKey = $state(false);
	let testing = $state(false);
	let testResult = $state<'success' | 'failure' | null>(null);
	let testMessage = $state('');
	let skipped = $state(false);

	let currentProviderDef = $derived(providers.find((p) => p.id === selectedProvider) ?? null);
	let activeModel = $derived(selectedModel === '__custom__' ? customModel : selectedModel);
	let canTest = $derived(
		selectedProvider !== null &&
			activeModel.length > 0 &&
			(!currentProviderDef?.needsApiKey || apiKey.length > 0)
	);
	let canContinue = $derived(testResult === 'success' || skipped);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function selectProvider(id: string) {
		selectedProvider = id;
		const def = providers.find((p) => p.id === id);
		selectedModel = def?.models[0]?.id ?? '';
		customModel = '';
		apiKey = '';
		baseUrl = '';
		showKey = false;
		testResult = null;
		testMessage = '';
		skipped = false;
	}

	async function testConnection() {
		if (!selectedProvider || !activeModel) return;
		testing = true;
		testResult = null;
		testMessage = '';

		try {
			const body: Record<string, string | null> = {
				provider_type: selectedProvider,
				api_key: apiKey || null
			};
			if (currentProviderDef?.needsBaseUrl && baseUrl) {
				body.base_url = baseUrl;
			}

			const result = await apiJson<{
				reachable: boolean;
				latency_ms?: number;
				error?: string;
			}>('/setup/test-llm', {
				method: 'POST',
				body: JSON.stringify(body)
			});

			if (result.reachable) {
				testResult = 'success';
				const latency = result.latency_ms ? ` (${Math.round(result.latency_ms)}ms)` : '';
				testMessage = `Connection successful${latency}`;
			} else {
				testResult = 'failure';
				testMessage = result.error ?? 'Connection test failed.';
			}
		} catch (e) {
			testResult = 'failure';
			testMessage = e instanceof Error ? e.message : 'An unexpected error occurred.';
		} finally {
			testing = false;
		}
	}

	function handleSkip() {
		skipped = true;
		testResult = null;
	}

	function handleContinue() {
		onNext({
			llm_provider: skipped
				? null
				: {
						provider_type: selectedProvider,
						name: currentProviderDef?.name ?? selectedProvider,
						api_key: apiKey || null,
						base_url: (currentProviderDef?.needsBaseUrl && baseUrl) || null,
						model_id: activeModel,
						model_name:
							currentProviderDef?.models.find((m) => m.id === activeModel)?.name ??
							activeModel
					}
		});
	}
</script>

<div class="flex h-full flex-col">
	<h2 class="text-xl font-bold text-text-primary">LLM Provider</h2>
	<p class="mt-1 text-sm text-text-secondary">
		Connect a language model provider to power Ember's intelligence.
	</p>

	<!-- Provider cards -->
	<div class="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-3">
		{#each providers as provider}
			<button
				type="button"
				onclick={() => selectProvider(provider.id)}
				class="rounded-lg border px-3 py-3 text-left transition-all
					{selectedProvider === provider.id
					? 'border-ember bg-ember/5 shadow-sm'
					: 'border-border hover:border-text-secondary/40 hover:bg-surface-hover'}"
			>
				<span
					class="block text-sm font-medium {selectedProvider === provider.id
						? 'text-ember'
						: 'text-text-primary'}">{provider.name}</span
				>
				<span class="mt-0.5 block text-[11px] text-text-secondary">{provider.description}</span>
			</button>
		{/each}
	</div>

	<!-- Configuration form (shown when a provider is selected) -->
	{#if selectedProvider && currentProviderDef}
		<div class="mt-6 space-y-4">
			<!-- Model selection -->
			<div>
				<label for="model-select" class="mb-1.5 block text-xs font-medium text-text-secondary">
					Model
				</label>
				{#if currentProviderDef.models.length > 0}
					<select
						id="model-select"
						bind:value={selectedModel}
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary transition-colors focus:border-ember focus:outline-none"
					>
						{#each currentProviderDef.models as model}
							<option value={model.id}>{model.name}</option>
						{/each}
						{#if currentProviderDef.allowCustomModel}
							<option value="__custom__">Custom model...</option>
						{/if}
					</select>
				{:else}
					<!-- No preset models (e.g., Azure) -- always show custom input -->
					<input
						id="model-select"
						type="text"
						bind:value={customModel}
						placeholder="Enter your deployed model name"
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
					/>
				{/if}

				{#if selectedModel === '__custom__'}
					<input
						type="text"
						bind:value={customModel}
						placeholder="e.g., gpt-4o-2024-05-13"
						class="mt-2 w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
					/>
				{/if}
			</div>

			<!-- API Key -->
			{#if currentProviderDef.needsApiKey}
				<div>
					<label for="api-key" class="mb-1.5 block text-xs font-medium text-text-secondary">
						API Key
					</label>
					<div class="relative">
						<input
							id="api-key"
							type={showKey ? 'text' : 'password'}
							bind:value={apiKey}
							placeholder="sk-..."
							autocomplete="off"
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
						/>
						<button
							type="button"
							onclick={() => (showKey = !showKey)}
							class="absolute top-1/2 right-2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
							aria-label={showKey ? 'Hide API key' : 'Show API key'}
						>
							{#if showKey}
								<EyeOff size={16} />
							{:else}
								<Eye size={16} />
							{/if}
						</button>
					</div>
				</div>
			{/if}

			<!-- Base URL (Azure / Ollama) -->
			{#if currentProviderDef.needsBaseUrl}
				<div>
					<label for="base-url" class="mb-1.5 block text-xs font-medium text-text-secondary">
						Base URL
					</label>
					<input
						id="base-url"
						type="url"
						bind:value={baseUrl}
						placeholder={currentProviderDef.baseUrlPlaceholder ?? 'https://...'}
						class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary placeholder-text-secondary/50 transition-colors focus:border-ember focus:outline-none"
					/>
				</div>
			{/if}

			<!-- Test Connection button -->
			<button
				type="button"
				onclick={testConnection}
				disabled={testing || !canTest}
				class="btn-hover inline-flex items-center gap-2 rounded-lg bg-ember px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
			>
				{#if testing}
					<Loader2 size={16} class="animate-spin" />
					Testing...
				{:else}
					Test Connection
				{/if}
			</button>

			<!-- Test result -->
			{#if testResult === 'success'}
				<div
					class="flex items-start gap-2 rounded-lg border border-success/30 bg-success/5 px-4 py-3 text-sm text-success"
				>
					<CheckCircle size={18} class="mt-0.5 shrink-0" />
					<span>{testMessage}</span>
				</div>
			{:else if testResult === 'failure'}
				<div
					class="flex items-start gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger"
				>
					<XCircle size={18} class="mt-0.5 shrink-0" />
					<span>{testMessage}</span>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Skip option -->
	{#if !canContinue}
		<div class="mt-4">
			<button
				type="button"
				onclick={handleSkip}
				class="text-sm text-text-secondary underline decoration-dotted underline-offset-4 hover:text-text-primary"
			>
				Skip for now
			</button>
		</div>
	{/if}

	{#if skipped && !testResult}
		<p class="mt-2 text-xs text-text-secondary">
			You can configure an LLM provider later in Admin &gt; LLM Providers.
		</p>
	{/if}

	<!-- Spacer -->
	<div class="flex-1"></div>

	<!-- Navigation -->
	<div class="mt-8 flex items-center justify-between border-t border-border pt-4">
		<button
			type="button"
			onclick={onBack}
			class="inline-flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
		>
			<ArrowLeft size={16} />
			Back
		</button>
		<button
			type="button"
			onclick={handleContinue}
			disabled={!canContinue}
			class="btn-hover inline-flex items-center gap-1.5 rounded-lg bg-ember px-5 py-2 text-sm font-semibold text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
		>
			Continue
			<ArrowRight size={16} />
		</button>
	</div>
</div>
