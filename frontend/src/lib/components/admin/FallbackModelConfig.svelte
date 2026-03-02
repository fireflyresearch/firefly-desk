<!--
  FallbackModelConfig.svelte - Fallback model configuration with setup wizard.

  Shows a wizard when no fallback models are configured (auto-detects providers,
  suggests recommended models) and a management UI once configured.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		ShieldAlert,
		Loader2,
		Save,
		Plus,
		X,
		AlertCircle,
		CheckCircle,
		RotateCcw,
		Sparkles,
		ChevronDown,
		Info
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface LLMProvider {
		id: string;
		name: string;
		provider_type: string;
		default_model: string | null;
		is_default: boolean;
		is_active: boolean;
		models: Array<{ id: string; name: string }>;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const PROVIDER_LABELS: Record<string, string> = {
		openai: 'OpenAI',
		anthropic: 'Anthropic',
		google: 'Google',
		azure_openai: 'Azure OpenAI',
		ollama: 'Ollama'
	};

	const RECOMMENDED_MODELS: Record<string, string> = {
		openai: 'gpt-4o-mini',
		anthropic: 'claude-haiku-4-5-20251001',
		google: 'gemini-2.0-flash'
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');

	let fallbackConfig = $state<Record<string, string[]>>({});
	let providers = $state<LLMProvider[]>([]);
	let originalConfig = $state('');
	let hasChanges = $state(false);

	// Wizard selections: one model per provider type
	let wizardSelections = $state<Record<string, string>>({});

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	/** Active provider types that have at least one configured provider. */
	let configuredTypes = $derived.by(() => {
		const types = new Set<string>();
		for (const p of providers) {
			if (p.is_active) types.add(p.provider_type);
		}
		return [...types];
	});

	/** Models available per provider type (from discovered models). */
	let modelsByType = $derived.by(() => {
		const map: Record<string, Array<{ value: string; label: string; provider: string }>> = {};
		for (const p of providers) {
			if (!p.is_active) continue;
			const pt = p.provider_type;
			if (!map[pt]) map[pt] = [];
			for (const m of p.models) {
				map[pt].push({ value: m.id, label: m.name, provider: p.name });
			}
			// Include default_model if not already in the models list
			if (p.default_model && !p.models.find((m) => m.id === p.default_model)) {
				map[pt].push({ value: p.default_model, label: p.default_model, provider: p.name });
			}
		}
		return map;
	});

	/** True when no fallback models are configured for any active provider type. */
	let isWizardMode = $derived.by(() => {
		if (configuredTypes.length === 0) return false; // no providers → show empty state
		// Wizard shows when no configured type has any fallback models
		return configuredTypes.every((pt) => !fallbackConfig[pt] || fallbackConfig[pt].length === 0);
	});

	/** True when no providers are configured at all. */
	let noProviders = $derived(providers.filter((p) => p.is_active).length === 0);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadAll() {
		loading = true;
		error = '';
		try {
			const [fallbackData, providerData] = await Promise.all([
				apiJson<Record<string, string[]>>('/admin/llm/fallback'),
				apiJson<LLMProvider[]>('/admin/llm-providers')
			]);
			fallbackConfig = fallbackData;
			providers = providerData;
			originalConfig = JSON.stringify(fallbackData);
			hasChanges = false;
			initWizardSelections();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load configuration';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadAll();
	});

	// Track changes in management mode
	$effect(() => {
		if (!loading) {
			hasChanges = JSON.stringify(fallbackConfig) !== originalConfig;
		}
	});

	// -----------------------------------------------------------------------
	// Wizard
	// -----------------------------------------------------------------------

	function initWizardSelections() {
		const selections: Record<string, string> = {};
		for (const pt of configuredTypes) {
			const rec = RECOMMENDED_MODELS[pt];
			const available = modelsByType[pt] || [];
			// Use recommended if it's in the available models, otherwise first available
			if (rec && available.find((m) => m.value === rec)) {
				selections[pt] = rec;
			} else if (rec) {
				// Recommended model not discovered but we still suggest it
				selections[pt] = rec;
			} else if (available.length > 0) {
				selections[pt] = available[0].value;
			} else {
				selections[pt] = '';
			}
		}
		wizardSelections = selections;
	}

	async function acceptWizard() {
		saving = true;
		error = '';
		try {
			const payload: Record<string, string[]> = {};
			for (const [pt, model] of Object.entries(wizardSelections)) {
				if (model) payload[pt] = [model];
			}
			fallbackConfig = await apiJson<Record<string, string[]>>('/admin/llm/fallback', {
				method: 'PUT',
				body: JSON.stringify({ fallback_models: payload })
			});
			originalConfig = JSON.stringify(fallbackConfig);
			hasChanges = false;
			successMsg = 'Fallback models configured!';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save fallback models';
		} finally {
			saving = false;
		}
	}

	// -----------------------------------------------------------------------
	// Management mode actions
	// -----------------------------------------------------------------------

	function addModel(providerType: string) {
		const current = fallbackConfig[providerType] ?? [];
		fallbackConfig = { ...fallbackConfig, [providerType]: [...current, ''] };
	}

	function removeModel(providerType: string, index: number) {
		const current = fallbackConfig[providerType] ?? [];
		fallbackConfig = {
			...fallbackConfig,
			[providerType]: current.filter((_, i) => i !== index)
		};
	}

	function updateModel(providerType: string, index: number, value: string) {
		const current = [...(fallbackConfig[providerType] ?? [])];
		current[index] = value;
		fallbackConfig = { ...fallbackConfig, [providerType]: current };
	}

	function useRecommended(providerType: string) {
		const rec = RECOMMENDED_MODELS[providerType];
		if (rec) {
			fallbackConfig = { ...fallbackConfig, [providerType]: [rec] };
		}
	}

	async function saveConfig() {
		saving = true;
		error = '';
		try {
			fallbackConfig = await apiJson<Record<string, string[]>>('/admin/llm/fallback', {
				method: 'PUT',
				body: JSON.stringify({ fallback_models: fallbackConfig })
			});
			originalConfig = JSON.stringify(fallbackConfig);
			hasChanges = false;
			successMsg = 'Fallback models saved!';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save fallback models';
		} finally {
			saving = false;
		}
	}

	function resetChanges() {
		fallbackConfig = JSON.parse(originalConfig);
		hasChanges = false;
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function providerLabel(type: string): string {
		return PROVIDER_LABELS[type] ?? type;
	}

	function isRecommended(pt: string, model: string): boolean {
		return RECOMMENDED_MODELS[pt] === model;
	}
</script>

<div class="flex h-full flex-col gap-5 overflow-y-auto p-6">
	<!-- Header -->
	<div>
		<div class="flex items-center gap-2.5">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-warning/10">
				<ShieldAlert size={16} class="text-warning" />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Fallback Models</h2>
				<p class="text-xs text-text-secondary">
					When the primary model is overloaded or unavailable, the system falls back to these
					lighter models.
				</p>
			</div>
		</div>
	</div>

	<!-- Messages -->
	{#if error}
		<div
			class="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
		>
			<AlertCircle size={16} class="shrink-0" />
			{error}
		</div>
	{/if}

	{#if successMsg}
		<div
			class="flex items-center gap-2 rounded-xl border border-success/30 bg-success/5 px-4 py-2.5 text-sm text-success"
		>
			<CheckCircle size={16} class="shrink-0" />
			{successMsg}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-16">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if noProviders}
		<!-- Empty state: no providers -->
		<section class="rounded-lg border border-border bg-surface p-8 text-center">
			<div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-surface-secondary">
				<ShieldAlert size={24} class="text-text-secondary/40" />
			</div>
			<h3 class="mb-1 text-sm font-semibold text-text-primary">No providers configured</h3>
			<p class="text-xs text-text-secondary">
				Add at least one LLM provider in the
				<span class="font-medium text-accent">Providers</span> tab before configuring fallback models.
			</p>
		</section>
	{:else if isWizardMode}
		<!-- Wizard mode -->
		<section class="rounded-lg border border-accent/20 bg-accent/5 p-4">
			<div class="mb-3 flex items-center gap-2">
				<Sparkles size={16} class="text-accent" />
				<h3 class="text-sm font-semibold text-text-primary">Quick Setup</h3>
			</div>
			<p class="mb-4 text-xs text-text-secondary">
				We detected your configured providers and pre-selected recommended fallback models.
				Review the selections below and click "Accept All & Save" to get started.
			</p>

			<div class="flex flex-col gap-3">
				{#each configuredTypes as pt}
					{@const models = modelsByType[pt] || []}
					<div class="rounded-lg border border-border bg-surface p-3">
						<div class="mb-2 flex items-center gap-2">
							<span
								class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
							>
								{providerLabel(pt)}
							</span>
							{#if RECOMMENDED_MODELS[pt]}
								<span class="text-[11px] text-text-secondary">
									Recommended: <code class="rounded bg-surface-secondary px-1 font-mono text-[11px]">{RECOMMENDED_MODELS[pt]}</code>
								</span>
							{/if}
						</div>

						<div class="relative">
							<select
								bind:value={wizardSelections[pt]}
								class="w-full appearance-none rounded-md border border-border bg-surface py-1.5 pl-3 pr-8 text-sm text-text-primary outline-none transition-colors focus:border-accent"
							>
								{#if RECOMMENDED_MODELS[pt] && !models.find((m) => m.value === RECOMMENDED_MODELS[pt])}
									<option value={RECOMMENDED_MODELS[pt]}>
										{RECOMMENDED_MODELS[pt]} (recommended)
									</option>
								{/if}
								{#each models as model}
									<option value={model.value}>
										{model.label} ({model.provider}){isRecommended(pt, model.value) ? ' (recommended)' : ''}
									</option>
								{/each}
								{#if models.length === 0 && !RECOMMENDED_MODELS[pt]}
									<option value="" disabled>No models discovered</option>
								{/if}
							</select>
							<ChevronDown
								size={14}
								class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary/50"
							/>
						</div>
					</div>
				{/each}
			</div>

			<div class="mt-4 flex justify-end">
				<button
					type="button"
					onclick={acceptWizard}
					disabled={saving}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
				>
					{#if saving}
						<Loader2 size={14} class="animate-spin" />
						Saving...
					{:else}
						<Sparkles size={14} />
						Accept All & Save
					{/if}
				</button>
			</div>
		</section>
	{:else}
		<!-- Management mode -->
		{#each configuredTypes as pt}
			{@const models = fallbackConfig[pt] ?? []}
			{@const availModels = modelsByType[pt] || []}
			<section class="rounded-lg border border-border bg-surface p-4">
				<div class="mb-3 flex items-center justify-between">
					<div class="flex items-center gap-2">
						<span
							class="inline-block rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
						>
							{providerLabel(pt)}
						</span>
						<span class="text-xs text-text-secondary">
							{models.length} fallback model{models.length !== 1 ? 's' : ''}
						</span>
					</div>
					<button
						type="button"
						onclick={() => addModel(pt)}
						class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
					>
						<Plus size={12} />
						Add
					</button>
				</div>

				{#if models.length === 0}
					<div class="flex items-center justify-between rounded-md border border-dashed border-border bg-surface-secondary/30 px-3 py-3">
						<p class="text-xs text-text-secondary">No fallback models configured.</p>
						{#if RECOMMENDED_MODELS[pt]}
							<button
								type="button"
								onclick={() => useRecommended(pt)}
								class="inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs text-accent transition-colors hover:bg-accent/10"
							>
								<Sparkles size={11} />
								Use recommended
							</button>
						{/if}
					</div>
				{:else}
					<div class="flex flex-col gap-1.5">
						{#each models as model, i}
							<div class="flex items-center gap-2">
								{#if availModels.length > 0}
									<div class="relative flex-1">
										<select
											value={model}
											onchange={(e) =>
												updateModel(pt, i, (e.target as HTMLSelectElement).value)}
											class="w-full appearance-none rounded-md border border-border bg-surface py-1.5 pl-3 pr-8 text-sm text-text-primary outline-none transition-colors focus:border-accent"
										>
											{#if model && !availModels.find((m) => m.value === model)}
												<option value={model}>{model}</option>
											{/if}
											<option value="">Select a model...</option>
											{#each availModels as m}
												<option value={m.value}>
													{m.label} ({m.provider}){isRecommended(pt, m.value) ? ' ★' : ''}
												</option>
											{/each}
										</select>
										<ChevronDown
											size={14}
											class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary/50"
										/>
									</div>
								{:else}
									<input
										type="text"
										value={model}
										oninput={(e) =>
											updateModel(pt, i, (e.target as HTMLInputElement).value)}
										placeholder="e.g. gpt-4o-mini"
										class="flex-1 rounded-md border border-border bg-surface px-2.5 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-accent"
									/>
								{/if}
								<button
									type="button"
									onclick={() => removeModel(pt, i)}
									class="shrink-0 rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
									title="Remove model"
								>
									<X size={14} />
								</button>
							</div>
						{/each}
					</div>
				{/if}
			</section>
		{/each}

		<!-- Hint when providers exist but have no type in config -->
		{#if configuredTypes.length > 0}
			<div class="flex items-start gap-2 rounded-md border border-border/50 bg-surface-secondary/30 px-3 py-2 text-xs text-text-secondary">
				<Info size={13} class="mt-0.5 shrink-0" />
				<span>Fallback models are tried in order when the primary model is unavailable. Only provider types with active providers are shown.</span>
			</div>
		{/if}

		<!-- Sticky save bar -->
		{#if hasChanges}
			<div
				class="sticky bottom-0 -mx-6 -mb-5 flex items-center justify-between border-t border-border bg-surface-secondary/80 px-6 py-3 backdrop-blur-sm"
			>
				<span class="text-xs text-text-secondary">You have unsaved changes</span>
				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={resetChanges}
						class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						<RotateCcw size={14} />
						Discard
					</button>
					<button
						type="button"
						onclick={saveConfig}
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
							Saving...
						{:else}
							<Save size={14} />
							Save Changes
						{/if}
					</button>
				</div>
			</div>
		{/if}
	{/if}
</div>
