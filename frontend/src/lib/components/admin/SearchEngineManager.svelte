<!--
  SearchEngineManager.svelte - Web search provider configuration.

  Manages the search engine integration (e.g. Tavily) that gives the
  agent internet search capabilities for real-time information.
  Uses table + inline form + guided empty state pattern (matching
  DocumentSourceManager and GitProviderManager).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Plus,
		Pencil,
		Trash2,
		X,
		Save,
		Loader2,
		Zap,
		CheckCircle,
		XCircle,
		Globe,
		BookOpen,
		Info
	} from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';

	// -----------------------------------------------------------------------
	// Props
	// -----------------------------------------------------------------------

	interface Props {
		embedded?: boolean;
	}

	let { embedded = false }: Props = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	interface SearchProvider {
		provider: string;
		api_key: string;
		max_results: number;
	}

	// -----------------------------------------------------------------------
	// Constants
	// -----------------------------------------------------------------------

	const SEARCH_PROVIDERS = [
		{ value: 'tavily', label: 'Tavily', icon: Globe }
	];

	const PROVIDER_GUIDES: Record<string, { title: string; steps: string[]; tip: string }> = {
		tavily: {
			title: 'Tavily Setup',
			steps: [
				'Visit tavily.com and create a free account',
				'Navigate to the API Keys section in your dashboard',
				'Copy your API key and paste it below',
				'Click "Test Connection" to verify everything works',
				'Save your configuration'
			],
			tip: 'The free tier includes 1,000 searches/month. Paid plans offer higher limits and additional features.'
		}
	};

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<SearchProvider[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Form state
	let showForm = $state(false);
	let editing = $state(false);
	let formData = $state({ provider: 'tavily', api_key: '', max_results: 5 });
	let saving = $state(false);

	// Guide
	let showGuide = $state(false);

	// Test connection
	let testing = $state(false);
	let testResult = $state<{ success: boolean; error?: string; result_count?: number } | null>(null);

	// Delete confirmation
	let confirmDelete = $state(false);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadConfig() {
		loading = true;
		error = '';
		try {
			const config = await apiJson<{
				search_provider: string;
				search_api_key: string;
				search_max_results: number;
			}>('/settings/search');
			if (config.search_provider) {
				providers = [{
					provider: config.search_provider,
					api_key: config.search_api_key || '',
					max_results: config.search_max_results || 5
				}];
			} else {
				providers = [];
			}
		} catch {
			providers = [];
		} finally {
			loading = false;
		}
	}

	$effect(() => {
		loadConfig();
	});

	// -----------------------------------------------------------------------
	// Form actions
	// -----------------------------------------------------------------------

	function openAddForm(providerType = 'tavily') {
		editing = false;
		formData = { provider: providerType, api_key: '', max_results: 5 };
		testResult = null;
		showGuide = false;
		showForm = true;
	}

	function openEditForm() {
		if (providers.length === 0) return;
		const p = providers[0];
		editing = true;
		formData = { provider: p.provider, api_key: p.api_key, max_results: p.max_results };
		testResult = null;
		showGuide = false;
		showForm = true;
	}

	function cancelForm() {
		showForm = false;
		editing = false;
		testResult = null;
	}

	async function submitForm() {
		saving = true;
		error = '';
		try {
			await apiJson('/settings/search', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: formData.provider,
					search_api_key: formData.api_key,
					search_max_results: formData.max_results
				})
			});
			showForm = false;
			editing = false;
			await loadConfig();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save search config';
		} finally {
			saving = false;
		}
	}

	async function deleteProvider() {
		error = '';
		try {
			await apiJson('/settings/search', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: '',
					search_api_key: '',
					search_max_results: 5
				})
			});
			confirmDelete = false;
			showForm = false;
			testResult = null;
			await loadConfig();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove search provider';
		}
	}

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
					search_provider: formData.provider,
					search_api_key: formData.api_key
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

	// -----------------------------------------------------------------------
	// Helpers
	// -----------------------------------------------------------------------

	function providerLabel(type: string): string {
		return SEARCH_PROVIDERS.find((p) => p.value === type)?.label ?? type;
	}

	function maskApiKey(key: string): string {
		if (!key || key.length < 8) return '********';
		return key.substring(0, 4) + '...' + key.substring(key.length - 4);
	}
</script>

<div class="flex h-full flex-col gap-4" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Search Engine</h1>
				<p class="text-sm text-text-secondary">
					Configure a web search provider so the agent can look up real-time information
				</p>
			</div>
			<button
				type="button"
				onclick={() => openAddForm()}
				disabled={providers.length > 0}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
			>
				<Plus size={16} />
				Add Provider
			</button>
		</div>
	{:else}
		<div class="flex justify-end">
			<button
				type="button"
				onclick={() => openAddForm()}
				disabled={providers.length > 0}
				class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
			>
				<Plus size={16} />
				Add Provider
			</button>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	<!-- Inline form -->
	{#if showForm}
		<div class="rounded-lg border border-border bg-surface p-4">
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-sm font-semibold text-text-primary">
					{editing ? 'Edit Search Provider' : 'New Search Provider'}
				</h3>
				<button
					type="button"
					onclick={cancelForm}
					class="text-text-secondary hover:text-text-primary"
				>
					<X size={16} />
				</button>
			</div>

			<!-- Setup guide (collapsible) -->
			{#if !editing && PROVIDER_GUIDES[formData.provider]}
				{@const guide = PROVIDER_GUIDES[formData.provider]}
				<button
					type="button"
					onclick={() => (showGuide = !showGuide)}
					class="mb-2 flex w-full items-center gap-2 rounded-lg border border-accent/20 bg-accent/5 px-3 py-2 text-left text-xs font-semibold text-accent transition-colors hover:bg-accent/10"
				>
					<BookOpen size={14} />
					{guide.title}
					<span class="ml-auto text-[10px] font-normal text-accent/60">{showGuide ? 'Hide' : 'Show'}</span>
				</button>
				{#if showGuide}
					<div class="mb-4 rounded-lg border border-accent/20 bg-accent/5 p-4">
						<ol class="mb-2 list-inside list-decimal space-y-1 text-xs text-text-secondary">
							{#each guide.steps as step}
								<li>{step}</li>
							{/each}
						</ol>
						<div class="flex items-start gap-1.5 rounded-md bg-accent/5 px-2.5 py-1.5">
							<Info size={12} class="mt-0.5 shrink-0 text-accent/70" />
							<p class="text-[11px] text-accent/80">{guide.tip}</p>
						</div>
					</div>
				{/if}
			{/if}

			<form
				onsubmit={(e) => {
					e.preventDefault();
					submitForm();
				}}
				class="flex flex-col gap-3"
			>
				<div class="grid grid-cols-2 gap-3">
					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">Provider</span>
						<select
							bind:value={formData.provider}
							disabled={editing}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent disabled:opacity-50"
						>
							{#each SEARCH_PROVIDERS as sp}
								<option value={sp.value}>{sp.label}</option>
							{/each}
						</select>
					</label>

					<label class="flex flex-col gap-1">
						<span class="text-xs font-medium text-text-secondary">
							API Key
							{#if editing}
								<span class="text-text-secondary/60">(leave blank to keep existing)</span>
							{/if}
						</span>
						<input
							type="password"
							bind:value={formData.api_key}
							placeholder={editing ? '********' : 'tvly-...'}
							required={!editing}
							class="rounded-md border border-border bg-surface px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent"
						/>
					</label>
				</div>

				<!-- Max Results slider -->
				<div>
					<label class="mb-1.5 block text-xs font-medium text-text-secondary">
						Max Results per Query: <span class="font-semibold text-text-primary">{formData.max_results}</span>
					</label>
					<input
						type="range"
						min="1"
						max="10"
						bind:value={formData.max_results}
						class="w-full accent-accent"
					/>
					<div class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60">
						<span>1</span>
						<span>5</span>
						<span>10</span>
					</div>
				</div>

				<!-- Test result -->
				{#if testResult}
					<div
						class="flex items-center gap-2 rounded-lg border px-4 py-2.5 text-xs {testResult.success
							? 'border-success/30 bg-success/5 text-success'
							: 'border-danger/30 bg-danger/5 text-danger'}"
					>
						{#if testResult.success}
							<CheckCircle size={14} />
							Search working — {testResult.result_count} results returned
						{:else}
							<XCircle size={14} />
							Search test failed: {testResult.error}
						{/if}
					</div>
				{/if}

				<div class="flex justify-end gap-2 pt-1">
					<button
						type="button"
						onclick={testConnection}
						disabled={testing || !formData.api_key}
						class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
					>
						{#if testing}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Zap size={14} />
						{/if}
						{testing ? 'Testing...' : 'Test Connection'}
					</button>
					<button
						type="button"
						onclick={cancelForm}
						class="rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover"
					>
						Cancel
					</button>
					<button
						type="submit"
						disabled={saving}
						class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
					>
						{#if saving}
							<Loader2 size={14} class="animate-spin" />
						{:else}
							<Save size={14} />
						{/if}
						{editing ? 'Update' : 'Save'}
					</button>
				</div>
			</form>
		</div>
	{/if}

	<!-- Table -->
	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else}
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Provider</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">API Key</th>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary">Max Results</th>
							<th class="w-40 px-4 py-2 text-xs font-medium text-text-secondary">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each providers as provider}
							<tr class="border-b border-border last:border-b-0">
								<td class="px-4 py-2">
									<span class="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
										<Globe size={12} />
										{providerLabel(provider.provider)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span class="font-mono text-xs text-text-secondary">{maskApiKey(provider.api_key)}</span>
								</td>
								<td class="px-4 py-2">
									<span class="text-sm text-text-primary">{provider.max_results}</span>
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={openEditForm}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
										</button>
										<button
											type="button"
											onclick={() => {
												openEditForm();
												testConnection();
											}}
											disabled={testing}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-accent/10 hover:text-accent disabled:opacity-50"
											title="Test Connection"
										>
											{#if testing}
												<Loader2 size={14} class="animate-spin" />
											{:else}
												<Zap size={14} />
											{/if}
										</button>
										{#if confirmDelete}
											<span class="ml-1 flex items-center gap-1 text-xs">
												<button
													type="button"
													onclick={deleteProvider}
													class="rounded bg-danger px-1.5 py-0.5 text-white hover:bg-danger/80"
												>
													Confirm
												</button>
												<button
													type="button"
													onclick={() => (confirmDelete = false)}
													class="rounded border border-border px-1.5 py-0.5 text-text-secondary hover:bg-surface-hover"
												>
													Cancel
												</button>
											</span>
										{:else}
											<button
												type="button"
												onclick={() => (confirmDelete = true)}
												class="rounded p-1 text-text-secondary transition-colors hover:bg-danger/10 hover:text-danger"
												title="Delete"
											>
												<Trash2 size={14} />
											</button>
										{/if}
									</div>
								</td>
							</tr>
						{:else}
							<tr>
								<td colspan="4" class="px-4 py-6">
									<div class="mx-auto max-w-2xl text-center">
										<Globe size={32} class="mx-auto mb-2 text-text-secondary/40" />
										<h3 class="text-sm font-semibold text-text-primary">
											Enable web search
										</h3>
										<p class="mb-4 text-xs text-text-secondary">
											Give the agent the ability to search the internet for current information, news, and documentation.
										</p>
										<div class="grid grid-cols-3 gap-2">
											{#each SEARCH_PROVIDERS as sp}
												<button
													type="button"
													onclick={() => openAddForm(sp.value)}
													class="flex flex-col items-center gap-1.5 rounded-lg border border-border p-3 text-text-secondary transition-all hover:border-accent/40 hover:bg-accent/5 hover:text-accent"
												>
													<Globe size={20} />
													<span class="text-xs font-medium">{sp.label}</span>
												</button>
											{/each}
										</div>
										<p class="mt-3 text-[11px] text-text-secondary/60">
											Tavily is an AI-optimised search API. The free tier includes 1,000 searches per month.
										</p>
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>
