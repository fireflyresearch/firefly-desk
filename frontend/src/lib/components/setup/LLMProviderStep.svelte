<!--
  LLMProviderStep.svelte -- Configure an LLM provider during setup.

  Presents provider selection cards. On selection, shows API key input and
  optional base URL (for Azure / Ollama). A "Test Connection" button creates
  the provider via the admin API and runs a connectivity test. The user can
  also choose to skip this step.

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
	import { apiJson, apiFetch } from '$lib/services/api.js';

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
	// Provider definitions
	// -----------------------------------------------------------------------

	interface ProviderDef {
		id: string;
		name: string;
		needsBaseUrl: boolean;
		baseUrlPlaceholder?: string;
	}

	const providers: ProviderDef[] = [
		{ id: 'openai', name: 'OpenAI', needsBaseUrl: false },
		{ id: 'anthropic', name: 'Anthropic', needsBaseUrl: false },
		{ id: 'google', name: 'Google', needsBaseUrl: false },
		{
			id: 'azure_openai',
			name: 'Azure OpenAI',
			needsBaseUrl: true,
			baseUrlPlaceholder: 'https://your-resource.openai.azure.com'
		},
		{
			id: 'ollama',
			name: 'Ollama',
			needsBaseUrl: true,
			baseUrlPlaceholder: 'http://localhost:11434'
		}
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let selectedProvider = $state<string | null>(null);
	let apiKey = $state('');
	let baseUrl = $state('');
	let showKey = $state(false);
	let testing = $state(false);
	let testResult = $state<'success' | 'failure' | null>(null);
	let testMessage = $state('');
	let skipped = $state(false);
	let createdProviderId = $state<string | null>(null);

	let currentProviderDef = $derived(providers.find((p) => p.id === selectedProvider) ?? null);
	let canContinue = $derived(testResult === 'success' || skipped);

	// -----------------------------------------------------------------------
	// Handlers
	// -----------------------------------------------------------------------

	function selectProvider(id: string) {
		selectedProvider = id;
		apiKey = '';
		baseUrl = '';
		showKey = false;
		testResult = null;
		testMessage = '';
		skipped = false;
		createdProviderId = null;
	}

	async function testConnection() {
		if (!selectedProvider) return;
		testing = true;
		testResult = null;
		testMessage = '';

		try {
			// Step 1: Create the provider
			const body: Record<string, string> = {
				provider_type: selectedProvider,
				name: currentProviderDef?.name ?? selectedProvider,
				api_key: apiKey
			};
			if (currentProviderDef?.needsBaseUrl && baseUrl) {
				body.base_url = baseUrl;
			}

			const created = await apiJson<{ id: string }>('/admin/llm-providers', {
				method: 'POST',
				body: JSON.stringify(body)
			});
			createdProviderId = created.id;

			// Step 2: Test the provider
			const result = await apiJson<{ success: boolean; message?: string }>(
				`/admin/llm-providers/${created.id}/test`,
				{ method: 'POST' }
			);

			if (result.success) {
				testResult = 'success';
				testMessage = result.message ?? 'Connection successful.';
			} else {
				testResult = 'failure';
				testMessage = result.message ?? 'Connection test failed.';
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
						provider_id: createdProviderId,
						name: currentProviderDef?.name
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
				class="rounded-lg border px-3 py-3 text-left text-sm font-medium transition-all
					{selectedProvider === provider.id
					? 'border-ember bg-ember/5 text-ember shadow-sm'
					: 'border-border text-text-primary hover:border-text-secondary/40 hover:bg-surface-hover'}"
			>
				{provider.name}
			</button>
		{/each}
	</div>

	<!-- Configuration form (shown when a provider is selected) -->
	{#if selectedProvider && currentProviderDef}
		<div class="mt-6 space-y-4">
			<!-- API Key -->
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

			<!-- Base URL (Azure / Ollama) -->
			{#if currentProviderDef.needsBaseUrl}
				<div>
					<label
						for="base-url"
						class="mb-1.5 block text-xs font-medium text-text-secondary"
					>
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
				disabled={testing || !apiKey}
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
