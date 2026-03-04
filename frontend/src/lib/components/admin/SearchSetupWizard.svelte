<!--
  SearchSetupWizard.svelte - 3-step wizard for search provider configuration.

  Walks administrators through: provider selection, API key & config,
  and a test & save step. Follows the SSOWizard modal/step-indicator
  patterns exactly.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		X,
		ChevronLeft,
		ChevronRight,
		Save,
		Loader2,
		Check,
		CheckCircle,
		XCircle,
		Info,
		Globe,
		Zap,
		Eye,
		EyeOff
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface Props {
		open: boolean;
		onClose: () => void;
		onSaved: () => void;
		editProvider?: { provider: string; api_key: string; max_results: number } | null;
	}

	interface ProviderInfo {
		value: string;
		label: string;
		description: string;
		features: string[];
		placeholder: string;
	}

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	let { open, onClose, onSaved, editProvider = null }: Props = $props();

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const STEPS = ['Provider', 'Credentials', 'Test & Save'] as const;

	const PROVIDERS: ProviderInfo[] = [
		{
			value: 'tavily',
			label: 'Tavily',
			description: 'AI-optimized search API. Clean, relevant results with minimal noise.',
			features: [
				'Snippet + full content retrieval',
				'Relevance scoring',
				'Free tier: 1,000 searches/mo'
			],
			placeholder: 'tvly-...'
		},
		{
			value: 'nimbleway',
			label: 'Nimbleway',
			description: 'AI-powered web search and real-time data retrieval platform.',
			features: [
				'Markdown content parsing',
				'Bearer token auth',
				'Flexible result limits'
			],
			placeholder: 'Enter API key'
		},
		{
			value: 'exa',
			label: 'Exa',
			description: 'AI-native search engine with neural and keyword modes.',
			features: [
				'Neural + keyword search',
				'Highlight extraction',
				'Published date filtering'
			],
			placeholder: 'exa-...'
		}
	];

	const PROVIDER_GUIDES: Record<string, { title: string; steps: string[]; tip: string }> = {
		tavily: {
			title: 'Tavily Setup',
			steps: [
				'Visit tavily.com and create a free account',
				'Navigate to the API Keys section in your dashboard',
				'Copy your API key and paste it here',
				'Click "Test Connection" to verify everything works'
			],
			tip: 'The free tier includes 1,000 searches/month. Paid plans offer higher limits and additional features.'
		},
		exa: {
			title: 'Exa Setup',
			steps: [
				'Visit exa.ai and create an account',
				'Navigate to the API Keys section in your dashboard',
				'Generate a new API key and paste it here',
				'Click "Test Connection" to verify everything works'
			],
			tip: 'Exa is an AI-native search engine with neural and keyword modes. Check their pricing page for current plan options.'
		},
		nimbleway: {
			title: 'Nimbleway Setup',
			steps: [
				'Visit nimbleway.com and create an account',
				'Navigate to the API section in your dashboard',
				'Generate a new API key and paste it here',
				'Click "Test Connection" to verify everything works'
			],
			tip: 'Nimbleway provides AI-powered web search and data retrieval. Check their pricing page for current plan options.'
		}
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let currentStep = $state(0);
	let selectedProvider = $state<string | null>(null);
	let apiKey = $state('');
	let showApiKey = $state(false);
	let maxResults = $state(5);
	let saving = $state(false);
	let testing = $state(false);
	let error = $state('');
	let testResult = $state<{ success: boolean; error?: string; result_count?: number } | null>(
		null
	);

	// -----------------------------------------------------------------------
	// Derived
	// -----------------------------------------------------------------------

	const isEditing = $derived(editProvider !== null);

	const currentProviderInfo = $derived(
		PROVIDERS.find((p) => p.value === selectedProvider) ?? null
	);

	const step0Valid = $derived(selectedProvider !== null);

	const step1Valid = $derived(() => {
		if (!selectedProvider) return false;
		if (isEditing) return true; // API key can be blank when editing (keeps existing)
		return apiKey.trim() !== '';
	});

	// -----------------------------------------------------------------------
	// Effects
	// -----------------------------------------------------------------------

	$effect(() => {
		if (open && editProvider) {
			selectedProvider = editProvider.provider;
			apiKey = '';
			maxResults = editProvider.max_results;
			currentStep = 1; // Skip provider selection
			testResult = null;
			error = '';
		}
	});

	$effect(() => {
		if (open && !editProvider) {
			resetWizard();
		}
	});

	// -----------------------------------------------------------------------
	// Validation
	// -----------------------------------------------------------------------

	function isStepValid(step: number): boolean {
		switch (step) {
			case 0:
				return step0Valid;
			case 1:
				return step1Valid();
			case 2:
				return step0Valid && step1Valid();
			default:
				return false;
		}
	}

	function isStepComplete(step: number): boolean {
		return step < currentStep && isStepValid(step);
	}

	// -----------------------------------------------------------------------
	// Navigation
	// -----------------------------------------------------------------------

	function goNext() {
		if (currentStep < STEPS.length - 1 && isStepValid(currentStep)) {
			currentStep += 1;
		}
	}

	function goPrev() {
		if (currentStep > 0) {
			// In edit mode, don't go back to step 0
			if (isEditing && currentStep === 1) return;
			currentStep -= 1;
		}
	}

	function goToStep(step: number) {
		// In edit mode, prevent going back to step 0
		if (isEditing && step === 0) return;
		if (step <= currentStep || (step === currentStep + 1 && isStepValid(currentStep))) {
			currentStep = step;
		}
	}

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function maskApiKey(key: string): string {
		if (!key || key.length < 8) return '********';
		return key.substring(0, 4) + '...' + key.substring(key.length - 4);
	}

	function handleBackdropClick(e: MouseEvent) {
		if (e.target === e.currentTarget) {
			handleClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape' && open) {
			handleClose();
		}
	}

	function handleClose() {
		resetWizard();
		onClose();
	}

	function resetWizard() {
		currentStep = 0;
		selectedProvider = null;
		apiKey = '';
		showApiKey = false;
		maxResults = 5;
		saving = false;
		testing = false;
		error = '';
		testResult = null;
	}

	// -----------------------------------------------------------------------
	// API calls
	// -----------------------------------------------------------------------

	async function testConnection() {
		testing = true;
		testResult = null;
		error = '';

		try {
			testResult = await apiJson<{
				success: boolean;
				error?: string;
				result_count?: number;
			}>('/settings/search/test', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: selectedProvider,
					search_api_key: apiKey || editProvider?.api_key || ''
				})
			});
		} catch (e) {
			testResult = {
				success: false,
				error: e instanceof Error ? e.message : 'Test failed'
			};
		} finally {
			testing = false;
		}
	}

	async function submit() {
		if (!isStepValid(2)) return;

		saving = true;
		error = '';

		try {
			await apiJson('/settings/search', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: selectedProvider,
					search_api_key: apiKey || editProvider?.api_key || '',
					search_max_results: maxResults
				})
			});
			resetWizard();
			onSaved();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save search config';
		} finally {
			saving = false;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if open}
	<!-- Modal backdrop -->
	<!-- svelte-ignore a11y_no_static_element_interactions -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
		role="presentation"
		onclick={handleBackdropClick}
	>
		<!-- Modal content -->
		<div
			class="mx-4 flex max-h-[90vh] w-full max-w-3xl flex-col rounded-xl bg-surface shadow-2xl"
		>
			<!-- Header -->
			<div class="flex items-center justify-between border-b border-border px-6 py-4">
				<h2 class="text-base font-semibold text-text-primary">
					{isEditing ? 'Edit Search Provider' : 'Configure Search Provider'}
				</h2>
				<button
					type="button"
					onclick={handleClose}
					class="rounded-md p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
				>
					<X size={18} />
				</button>
			</div>

			<!-- Step indicators -->
			<div class="flex items-center gap-2 border-b border-border px-6 py-3">
				{#each STEPS as stepLabel, i}
					{@const active = i === currentStep}
					{@const complete = isStepComplete(i)}
					{@const clickable =
						!(isEditing && i === 0) &&
						(i <= currentStep || (i === currentStep + 1 && isStepValid(currentStep)))}

					{#if i > 0}
						<div class="h-px flex-1 {i <= currentStep ? 'bg-accent' : 'bg-border'}"></div>
					{/if}

					<button
						type="button"
						onclick={() => goToStep(i)}
						disabled={!clickable}
						class="flex items-center gap-2 rounded-md px-2 py-1 text-xs font-medium transition-colors
							{active ? 'text-accent' : complete ? 'text-success' : 'text-text-secondary'}
							{clickable ? 'cursor-pointer hover:bg-surface-hover' : 'cursor-default opacity-50'}"
					>
						<span
							class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold
								{active ? 'bg-accent text-white' : complete ? 'bg-success text-white' : 'bg-surface-secondary text-text-secondary'}"
						>
							{#if complete}
								<Check size={12} />
							{:else}
								{i + 1}
							{/if}
						</span>
						<span class="hidden sm:inline">{stepLabel}</span>
					</button>
				{/each}
			</div>

			<!-- Error banner -->
			{#if error}
				<div
					class="mx-6 mt-4 rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger"
				>
					{error}
				</div>
			{/if}

			<!-- Step content -->
			<div class="flex-1 overflow-y-auto px-6 py-5">
				<!-- Step 0: Choose Provider -->
				{#if currentStep === 0}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Select the web search provider you want to use for real-time information
							retrieval.
						</p>

						<div class="grid grid-cols-3 gap-3">
							{#each PROVIDERS as provider}
								{@const selected = selectedProvider === provider.value}
								<button
									type="button"
									onclick={() => (selectedProvider = provider.value)}
									class="flex flex-col items-start gap-2.5 rounded-lg border-2 px-4 py-4 text-left transition-colors
										{selected
										? 'border-accent bg-accent/5 ring-2 ring-accent'
										: 'border-border bg-surface hover:border-accent/50 hover:bg-surface-hover'}"
								>
									<div class="flex items-center gap-2">
										<Globe
											size={20}
											class={selected ? 'text-accent' : 'text-text-secondary'}
										/>
										<span
											class="text-sm font-medium {selected
												? 'text-accent'
												: 'text-text-primary'}"
										>
											{provider.label}
										</span>
									</div>
									<span class="text-xs leading-relaxed text-text-secondary">
										{provider.description}
									</span>
									<ul class="flex flex-col gap-1">
										{#each provider.features as feature}
											<li class="flex items-center gap-1.5 text-xs text-text-secondary">
												<CheckCircle
													size={12}
													class={selected
														? 'shrink-0 text-accent'
														: 'shrink-0 text-text-secondary/50'}
												/>
												{feature}
											</li>
										{/each}
									</ul>
								</button>
							{/each}
						</div>
					</div>

					<!-- Step 1: Credentials & Config -->
				{:else if currentStep === 1}
					<div class="grid grid-cols-[1fr_280px] gap-6">
						<!-- Form fields -->
						<div class="flex flex-col gap-4">
							<p class="text-sm text-text-secondary">
								Enter your API key and configure search settings for
								{currentProviderInfo?.label ?? 'your provider'}.
							</p>

							<!-- API Key -->
							<label class="flex flex-col gap-1">
								<span class="text-xs font-medium text-text-secondary">
									API Key <span class="text-danger">*</span>
									{#if isEditing}
										<span class="text-text-secondary/60"
											>(leave blank to keep existing)</span
										>
									{/if}
								</span>
								<div class="relative">
									<input
										type={showApiKey ? 'text' : 'password'}
										bind:value={apiKey}
										placeholder={isEditing
											? '********'
											: (currentProviderInfo?.placeholder ?? 'Enter API key')}
										required={!isEditing}
										class="w-full rounded-md border border-border bg-surface px-3 py-2 pr-10 text-sm text-text-primary outline-none focus:border-accent"
									/>
									<button
										type="button"
										onclick={() => (showApiKey = !showApiKey)}
										class="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-text-secondary transition-colors hover:text-text-primary"
									>
										{#if showApiKey}
											<EyeOff size={14} />
										{:else}
											<Eye size={14} />
										{/if}
									</button>
								</div>
							</label>

							<!-- Max Results slider -->
							<div>
								<label
									class="mb-1.5 block text-xs font-medium text-text-secondary"
								>
									Max Results per Query: <span
										class="font-semibold text-text-primary">{maxResults}</span
									>
								</label>
								<input
									type="range"
									min="1"
									max="10"
									bind:value={maxResults}
									class="w-full accent-accent"
								/>
								<div
									class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60"
								>
									<span>1</span>
									<span>5</span>
									<span>10</span>
								</div>
							</div>
						</div>

						<!-- Setup guide panel -->
						{#if selectedProvider && PROVIDER_GUIDES[selectedProvider]}
							{@const guide = PROVIDER_GUIDES[selectedProvider]}
							<div
								class="flex flex-col gap-3 rounded-lg border border-border bg-surface-secondary/30 p-4"
							>
								<h4
									class="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-text-secondary"
								>
									<Info size={14} />
									Setup Guide
								</h4>

								<ol
									class="list-inside list-decimal space-y-1.5 text-xs text-text-secondary"
								>
									{#each guide.steps as step}
										<li>{step}</li>
									{/each}
								</ol>

								<div
									class="border-t border-border pt-3"
								>
									<div
										class="flex items-start gap-1.5 rounded-md bg-accent/5 px-2.5 py-1.5"
									>
										<Info
											size={12}
											class="mt-0.5 shrink-0 text-accent/70"
										/>
										<p class="text-[11px] text-accent/80">
											{guide.tip}
										</p>
									</div>
								</div>
							</div>
						{/if}
					</div>

					<!-- Step 2: Test & Save -->
				{:else if currentStep === 2}
					<div class="flex flex-col gap-4">
						<p class="text-sm text-text-secondary">
							Review your configuration and test the connection before saving.
						</p>

						<!-- Configuration summary -->
						<div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
							<h4
								class="mb-2 text-xs font-semibold uppercase tracking-wide text-text-secondary"
							>
								Configuration Summary
							</h4>
							<div
								class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm"
							>
								<span class="text-text-secondary">Provider:</span>
								<span class="font-medium text-text-primary">
									{currentProviderInfo?.label ?? selectedProvider}
								</span>
								<span class="text-text-secondary">API Key:</span>
								<span class="font-mono text-xs text-text-primary">
									{apiKey ? maskApiKey(apiKey) : isEditing ? '(unchanged)' : '—'}
								</span>
								<span class="text-text-secondary">Max Results:</span>
								<span class="text-text-primary">{maxResults}</span>
							</div>
						</div>

						<!-- Test connection -->
						<div class="flex flex-col gap-3">
							<button
								type="button"
								onclick={testConnection}
								disabled={testing}
								class="inline-flex w-fit items-center gap-1.5 rounded-md border border-border bg-surface-elevated px-4 py-2 text-sm font-medium text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
							>
								{#if testing}
									<Loader2 size={14} class="animate-spin" />
									Testing Connection...
								{:else}
									<Zap size={14} />
									Test Connection
								{/if}
							</button>

							<!-- Test result -->
							{#if testResult}
								<div
									class="rounded-lg border p-4 {testResult.success
										? 'border-success/30 bg-success/5'
										: 'border-danger/30 bg-danger/5'}"
								>
									<div class="flex items-start gap-2">
										{#if testResult.success}
											<CheckCircle
												size={16}
												class="mt-0.5 shrink-0 text-success"
											/>
											<div class="flex flex-col gap-1">
												<span class="text-sm font-medium text-success"
													>Connection successful</span
												>
												{#if testResult.result_count !== undefined}
													<span class="text-xs text-text-secondary">
														Test search returned {testResult.result_count}
														result{testResult.result_count === 1
															? ''
															: 's'}
													</span>
												{/if}
											</div>
										{:else}
											<XCircle
												size={16}
												class="mt-0.5 shrink-0 text-danger"
											/>
											<div class="flex flex-col gap-1">
												<span class="text-sm font-medium text-danger"
													>Connection failed</span
												>
												{#if testResult.error}
													<span class="text-xs text-danger/80"
														>{testResult.error}</span
													>
												{/if}
											</div>
										{/if}
									</div>
								</div>
							{/if}
						</div>

						<!-- Info callout -->
						<div
							class="flex items-start gap-2 rounded-md border border-accent/20 bg-accent/5 px-4 py-3"
						>
							<Info size={14} class="mt-0.5 shrink-0 text-accent/70" />
							<p class="text-xs text-accent/80">
								Test your connection before saving to ensure your API key is valid.
							</p>
						</div>
					</div>
				{/if}
			</div>

			<!-- Footer navigation -->
			<div
				class="flex items-center justify-between border-t border-border px-6 py-4"
			>
				<div>
					{#if currentStep > 0 && !(isEditing && currentStep === 1)}
						<button
							type="button"
							onclick={goPrev}
							class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
						>
							<ChevronLeft size={14} />
							Back
						</button>
					{/if}
				</div>

				<div class="flex items-center gap-2">
					<button
						type="button"
						onclick={handleClose}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>

					{#if currentStep < STEPS.length - 1}
						<button
							type="button"
							onclick={goNext}
							disabled={!isStepValid(currentStep)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							Next
							<ChevronRight size={14} />
						</button>
					{:else}
						<button
							type="button"
							onclick={submit}
							disabled={saving || !isStepValid(2)}
							class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
						>
							{#if saving}
								<Loader2 size={14} class="animate-spin" />
							{:else}
								<Save size={14} />
							{/if}
							{isEditing ? 'Update' : 'Save Provider'}
						</button>
					{/if}
				</div>
			</div>
		</div>
	</div>
{/if}
