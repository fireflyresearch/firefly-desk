<!--
  ModelRoutingConfig.svelte - Smart model routing configuration.

  Allows admins to enable/disable the smart model router, pick a classifier
  model, and map complexity tiers (fast / balanced / powerful) to specific
  LLM models from the configured providers.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Route,
		Loader2,
		Save,
		Zap,
		AlertCircle,
		CheckCircle,
		RotateCcw,
		Info,
		ChevronDown,
		Gauge,
		Sparkles,
		Brain
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface RoutingConfig {
		enabled: boolean;
		classifier_model: string | null;
		default_tier: string;
		tier_mappings: Record<string, string>;
		updated_at: string | null;
	}

	interface LLMProvider {
		id: string;
		name: string;
		provider_type: string;
		default_model: string | null;
		is_default: boolean;
		is_active: boolean;
		models: Array<{ id: string; name: string }>;
	}

	interface ModelOption {
		value: string;
		label: string;
		provider: string;
	}

	// -----------------------------------------------------------------------
	// Tier metadata
	// -----------------------------------------------------------------------

	const TIERS = [
		{
			key: 'fast',
			label: 'Fast',
			icon: Zap,
			color: 'text-success',
			bgColor: 'bg-success/10',
			borderColor: 'border-success/20',
			description: 'Greetings, simple lookups, status checks'
		},
		{
			key: 'balanced',
			label: 'Balanced',
			icon: Gauge,
			color: 'text-accent',
			bgColor: 'bg-accent/10',
			borderColor: 'border-accent/20',
			description: 'Standard conversations, 1-3 tool calls'
		},
		{
			key: 'powerful',
			label: 'Powerful',
			icon: Brain,
			color: 'text-warning',
			bgColor: 'bg-warning/10',
			borderColor: 'border-warning/20',
			description: 'Complex reasoning, 4+ tools, multi-step'
		}
	] as const;

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let loading = $state(true);
	let saving = $state(false);
	let error = $state('');
	let successMsg = $state('');

	let config = $state<RoutingConfig>({
		enabled: false,
		classifier_model: null,
		default_tier: 'balanced',
		tier_mappings: {},
		updated_at: null
	});

	let providers = $state<LLMProvider[]>([]);
	let hasChanges = $state(false);
	let originalConfig = $state('');

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	let availableModels = $derived.by(() => {
		const models: ModelOption[] = [];
		for (const p of providers) {
			if (!p.is_active) continue;
			for (const m of p.models) {
				models.push({ value: m.id, label: m.name, provider: p.name });
			}
			if (p.default_model && !p.models.find((m) => m.id === p.default_model)) {
				models.push({ value: p.default_model, label: p.default_model, provider: p.name });
			}
		}
		return models;
	});

	let cheapModels = $derived.by(() => {
		// Classifier model suggestions — prefer small/cheap models
		const cheapPatterns = [
			'gpt-4o-mini',
			'gpt-3.5',
			'claude-3-haiku',
			'claude-3.5-haiku',
			'claude-haiku',
			'gemini-flash',
			'gemini-2.0-flash',
			'llama',
			'mistral',
			'phi'
		];
		const cheap = availableModels.filter((m) =>
			cheapPatterns.some((p) => m.value.toLowerCase().includes(p))
		);
		return cheap.length > 0 ? cheap : availableModels;
	});

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadAll() {
		loading = true;
		error = '';
		try {
			const [routingData, providerData] = await Promise.all([
				apiJson<RoutingConfig>('/admin/model-routing'),
				apiJson<LLMProvider[]>('/admin/llm-providers')
			]);
			config = routingData;
			providers = providerData;
			originalConfig = JSON.stringify(routingData);
			hasChanges = false;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load configuration';
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadAll();
	});

	// Track changes
	$effect(() => {
		if (!loading) {
			hasChanges = JSON.stringify(config) !== originalConfig;
		}
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function saveConfig() {
		saving = true;
		error = '';
		try {
			const updated = await apiJson<RoutingConfig>('/admin/model-routing', {
				method: 'PUT',
				body: JSON.stringify(config)
			});
			config = updated;
			originalConfig = JSON.stringify(updated);
			hasChanges = false;
			successMsg = 'Routing configuration saved successfully!';
			setTimeout(() => (successMsg = ''), 4000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save configuration';
		} finally {
			saving = false;
		}
	}

	function resetChanges() {
		config = JSON.parse(originalConfig);
		hasChanges = false;
	}

	function setTierModel(tier: string, model: string) {
		config.tier_mappings = { ...config.tier_mappings, [tier]: model };
	}

	function clearTierModel(tier: string) {
		const next = { ...config.tier_mappings };
		delete next[tier];
		config.tier_mappings = next;
	}
</script>

<div class="flex h-full flex-col gap-5 overflow-y-auto p-6">
	<!-- Header -->
	<div>
		<div class="flex items-center gap-2.5">
			<div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/10">
				<Route size={16} class="text-accent" />
			</div>
			<div>
				<h2 class="text-sm font-semibold text-text-primary">Smart Model Routing</h2>
				<p class="text-xs text-text-secondary">
					Automatically route messages to cost-appropriate models based on complexity.
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
	{:else}
		<!-- Enable / Disable Toggle -->
		<section class="rounded-lg border border-border bg-surface p-4">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<Sparkles size={16} class={config.enabled ? 'text-accent' : 'text-text-secondary/40'} />
					<div>
						<span class="block text-sm font-medium text-text-primary">Enable Smart Routing</span>
						<span class="block text-xs text-text-secondary">
							{config.enabled
								? 'Messages are classified and routed to optimal models'
								: 'All messages use the default model'}
						</span>
					</div>
				</div>
				<button
					type="button"
					role="switch"
					aria-checked={config.enabled}
					aria-label="Enable smart routing"
					onclick={() => (config.enabled = !config.enabled)}
					class="relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors
						{config.enabled ? 'bg-accent' : 'bg-border'}"
				>
					<span
						class="pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow ring-0 transition-transform
							{config.enabled ? 'translate-x-5' : 'translate-x-0'}"
					></span>
				</button>
			</div>
		</section>

		{#if config.enabled}
			<!-- Classifier Model -->
			<section class="rounded-lg border border-border bg-surface p-4">
				<h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-text-primary">
					Classifier Model
				</h3>
				<p class="mb-3 text-xs text-text-secondary">
					The cheap/fast model used to classify message complexity before routing. Pick the
					smallest model available for lowest cost.
				</p>

				<div class="flex flex-col gap-2">
					<div class="relative">
						<select
							bind:value={config.classifier_model}
							class="w-full appearance-none rounded-md border border-border bg-surface py-2 pl-3 pr-8 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						>
							<option value={null}>Select a classifier model...</option>
							{#each cheapModels as model}
								<option value={model.value}>{model.label} ({model.provider})</option>
							{/each}
							{#if cheapModels.length !== availableModels.length}
								<optgroup label="All models">
									{#each availableModels as model}
										<option value={model.value}>{model.label} ({model.provider})</option>
									{/each}
								</optgroup>
							{/if}
						</select>
						<ChevronDown
							size={14}
							class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary/50"
						/>
					</div>

					{#if !config.classifier_model}
						<div
							class="flex items-start gap-2 rounded-md border border-warning/20 bg-warning/5 px-3 py-2 text-xs text-warning"
						>
							<Info size={13} class="mt-0.5 shrink-0" />
							<span>A classifier model is required for routing to work. Choose a small, fast model to minimize classification cost.</span>
						</div>
					{/if}
				</div>
			</section>

			<!-- Default Tier -->
			<section class="rounded-lg border border-border bg-surface p-4">
				<h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-text-primary">
					Default Tier
				</h3>
				<p class="mb-3 text-xs text-text-secondary">
					Fallback tier when classification confidence is below threshold or classification fails.
				</p>

				<div class="flex gap-2">
					{#each TIERS as tier}
						<button
							type="button"
							onclick={() => (config.default_tier = tier.key)}
							class="flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-sm font-medium transition-all
								{config.default_tier === tier.key
								? `${tier.borderColor} ${tier.bgColor} ${tier.color}`
								: 'border-border text-text-secondary hover:border-border hover:bg-surface-hover/50'}"
						>
							<tier.icon size={14} />
							{tier.label}
						</button>
					{/each}
				</div>
			</section>

			<!-- Tier → Model Mappings -->
			<section class="rounded-lg border border-border bg-surface p-4">
				<h3 class="mb-1 flex items-center gap-2 text-sm font-semibold text-text-primary">
					Tier Model Mappings
				</h3>
				<p class="mb-4 text-xs text-text-secondary">
					Assign a specific model to each complexity tier. Unmapped tiers will use the provider's
					default model.
				</p>

				<div class="flex flex-col gap-3">
					{#each TIERS as tier}
						{@const currentModel = config.tier_mappings[tier.key] || ''}
						<div class="rounded-lg border {tier.borderColor} {tier.bgColor} p-3">
							<div class="mb-2 flex items-center gap-2">
								<tier.icon size={14} class={tier.color} />
								<span class="text-xs font-semibold {tier.color}">{tier.label}</span>
								<span class="text-[11px] text-text-secondary">{tier.description}</span>
							</div>

							<div class="flex items-center gap-2">
								<div class="relative flex-1">
									<select
										value={currentModel}
										onchange={(e) => {
											const target = e.target as HTMLSelectElement;
											if (target.value) {
												setTierModel(tier.key, target.value);
											} else {
												clearTierModel(tier.key);
											}
										}}
										class="w-full appearance-none rounded-md border border-border bg-surface py-1.5 pl-3 pr-8 text-sm text-text-primary outline-none transition-colors focus:border-accent"
									>
										<option value="">Use provider default</option>
										{#each availableModels as model}
											<option value={model.value}>{model.label} ({model.provider})</option>
										{/each}
									</select>
									<ChevronDown
										size={14}
										class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-text-secondary/50"
									/>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Action bar -->
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

		<!-- Last updated -->
		{#if config.updated_at}
			<p class="text-[11px] text-text-secondary/50">
				Last updated: {new Date(config.updated_at).toLocaleString()}
			</p>
		{/if}
	{/if}
</div>
