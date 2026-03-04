<!--
  SearchEngineManager.svelte - Web search provider configuration.

  Manages the search engine integration (e.g. Tavily) that gives the
  agent internet search capabilities for real-time information.
  Uses table + modal wizard + guided empty state pattern (matching
  SSOManager and EmailSettings).

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import { Pencil, Trash2, Loader2, Globe } from 'lucide-svelte';
	import { apiJson } from '$lib/services/api.js';
	import SearchSetupWizard from './SearchSetupWizard.svelte';

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
		{ value: 'tavily', label: 'Tavily' },
		{ value: 'nimbleway', label: 'Nimbleway' },
		{ value: 'exa', label: 'Exa' }
	];

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let providers = $state<SearchProvider[]>([]);
	let loading = $state(true);
	let error = $state('');

	// Wizard
	let wizardOpen = $state(false);
	let editProvider = $state<{ provider: string; api_key: string; max_results: number } | null>(
		null
	);

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
				providers = [
					{
						provider: config.search_provider,
						api_key: config.search_api_key || '',
						max_results: config.search_max_results || 5
					}
				];
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
	// Wizard
	// -----------------------------------------------------------------------

	function openWizard(existing?: { provider: string; api_key: string; max_results: number }) {
		editProvider = existing ?? null;
		wizardOpen = true;
	}

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

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
			await loadConfig();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to remove search provider';
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

<div class="flex h-full flex-col gap-4 overflow-y-auto" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div>
			<h1 class="text-lg font-semibold text-text-primary">Search Engine</h1>
			<p class="text-sm text-text-secondary">
				Configure a web search provider so the agent can look up real-time information
			</p>
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="rounded-xl border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
			{error}
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if providers.length === 0}
		<!-- Empty state -->
		<div class="rounded-lg border border-border bg-surface px-6 py-12">
			<div class="mx-auto max-w-sm text-center">
				<Globe size={36} class="mx-auto mb-3 text-text-secondary/40" />
				<h3 class="text-sm font-semibold text-text-primary">Enable web search</h3>
				<p class="mb-5 text-xs text-text-secondary">
					Give the agent the ability to search the internet for current information,
					news, and documentation.
				</p>
				<button
					type="button"
					onclick={() => openWizard()}
					class="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover"
				>
					<Globe size={16} />
					Set Up Search Provider
				</button>
			</div>
		</div>
	{:else}
		<!-- Configured provider table -->
		<div class="rounded-lg border border-border bg-surface">
			<div class="overflow-x-auto">
				<table class="w-full text-left text-sm">
					<thead>
						<tr class="border-b border-border bg-surface-secondary">
							<th class="px-4 py-2 text-xs font-medium text-text-secondary"
								>Provider</th
							>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary"
								>API Key</th
							>
							<th class="px-4 py-2 text-xs font-medium text-text-secondary"
								>Max Results</th
							>
							<th class="w-24 px-4 py-2 text-xs font-medium text-text-secondary"
								>Actions</th
							>
						</tr>
					</thead>
					<tbody>
						{#each providers as provider}
							<tr class="border-b border-border last:border-b-0">
								<td class="px-4 py-2">
									<span
										class="inline-flex items-center gap-1.5 rounded-full bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent"
									>
										<Globe size={12} />
										{providerLabel(provider.provider)}
									</span>
								</td>
								<td class="px-4 py-2">
									<span class="font-mono text-xs text-text-secondary"
										>{maskApiKey(provider.api_key)}</span
									>
								</td>
								<td class="px-4 py-2">
									<span class="text-sm text-text-primary"
										>{provider.max_results}</span
									>
								</td>
								<td class="px-4 py-2">
									<div class="flex items-center gap-1">
										<button
											type="button"
											onclick={() =>
												openWizard({
													provider: provider.provider,
													api_key: provider.api_key,
													max_results: provider.max_results
												})}
											class="rounded p-1 text-text-secondary transition-colors hover:bg-surface-hover hover:text-text-primary"
											title="Edit"
										>
											<Pencil size={14} />
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
						{/each}
					</tbody>
				</table>
			</div>
		</div>
	{/if}
</div>

<!-- Search Setup Wizard -->
<SearchSetupWizard
	open={wizardOpen}
	onClose={() => (wizardOpen = false)}
	onSaved={() => {
		wizardOpen = false;
		loadConfig();
	}}
	{editProvider}
/>
