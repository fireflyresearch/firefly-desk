<!--
  SearchEngineManager.svelte - Web search provider configuration.

  Manages the search engine integration (e.g. Tavily) that gives the
  agent internet search capabilities for real-time information.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
	import {
		Globe,
		Loader2,
		CheckCircle,
		XCircle,
		Save,
		TestTube,
		BookOpen,
		Info,
		Trash2
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
	// State
	// -----------------------------------------------------------------------

	let searchProvider = $state('');
	let searchApiKey = $state('');
	let searchMaxResults = $state(5);
	let loading = $state(true);
	let saving = $state(false);
	let testing = $state(false);
	let saved = $state(false);
	let error = $state('');
	let testResult = $state<{
		success: boolean;
		error?: string;
		result_count?: number;
	} | null>(null);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------

	async function loadConfig() {
		loading = true;
		try {
			const config = await apiJson<{
				search_provider: string;
				search_api_key: string;
				search_max_results: number;
			}>('/settings/search');
			searchProvider = config.search_provider || '';
			searchApiKey = config.search_api_key || '';
			searchMaxResults = config.search_max_results || 5;
		} catch {
			// Defaults are fine
		} finally {
			loading = false;
		}
	}

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	async function saveConfig() {
		saving = true;
		saved = false;
		error = '';
		try {
			await apiJson('/settings/search', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					search_provider: searchProvider,
					search_api_key: searchApiKey,
					search_max_results: searchMaxResults
				})
			});
			saved = true;
			setTimeout(() => (saved = false), 3000);
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to save search config';
		} finally {
			saving = false;
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
			}>('/settings/search/test', { method: 'POST' });
		} catch (e) {
			testResult = {
				success: false,
				error: e instanceof Error ? e.message : 'Test failed'
			};
		} finally {
			testing = false;
		}
	}

	async function disableSearch() {
		searchProvider = '';
		searchApiKey = '';
		searchMaxResults = 5;
		testResult = null;
		await saveConfig();
	}

	// -----------------------------------------------------------------------
	// Init
	// -----------------------------------------------------------------------

	$effect(() => {
		loadConfig();
	});
</script>

<div class="flex h-full flex-col gap-6" class:p-6={!embedded}>
	<!-- Header -->
	{#if !embedded}
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-lg font-semibold text-text-primary">Search Engine</h1>
				<p class="text-sm text-text-secondary">
					Configure a web search provider so the agent can look up real-time information
				</p>
			</div>
			{#if searchProvider}
				<button
					type="button"
					onclick={disableSearch}
					class="inline-flex items-center gap-1.5 rounded-md border border-danger/30 px-3 py-1.5 text-sm text-danger transition-colors hover:bg-danger/5"
				>
					<Trash2 size={14} />
					Disable Search
				</button>
			{/if}
		</div>
	{/if}

	<!-- Error banner -->
	{#if error}
		<div class="flex items-center gap-2 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
			<XCircle size={16} />
			{error}
			<button onclick={() => (error = '')} class="ml-auto text-danger/60 hover:text-danger">
				Dismiss
			</button>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-12">
			<Loader2 size={24} class="animate-spin text-text-secondary" />
		</div>
	{:else if !searchProvider}
		<!-- Getting started / empty state -->
		<div class="mx-auto max-w-lg rounded-xl border border-border bg-surface p-8 text-center">
			<Globe size={40} class="mx-auto mb-3 text-text-secondary/40" />
			<h2 class="text-base font-semibold text-text-primary">Enable Web Search</h2>
			<p class="mt-1 mb-5 text-sm text-text-secondary">
				Give the agent the ability to search the internet for current information, news, and documentation.
			</p>

			<button
				type="button"
				onclick={() => (searchProvider = 'tavily')}
				class="inline-flex items-center gap-2 rounded-lg border border-border px-5 py-3 text-sm font-medium text-text-primary transition-all hover:border-accent/40 hover:bg-accent/5 hover:text-accent"
			>
				<Globe size={18} />
				Set up Tavily
			</button>

			<p class="mt-4 text-xs text-text-secondary/70">
				Tavily is an AI-optimised search API. The free tier includes 1,000 searches per month.
			</p>
		</div>
	{:else}
		<!-- Configuration -->
		<div class="mx-auto w-full max-w-2xl space-y-5">
			<!-- Setup guide -->
			<div class="rounded-lg border border-accent/20 bg-accent/5 p-4">
				<div class="mb-2 flex items-center gap-2">
					<BookOpen size={14} class="text-accent" />
					<span class="text-xs font-semibold text-accent">Tavily Setup Guide</span>
				</div>
				<ol class="mb-2 list-inside list-decimal space-y-1 text-xs text-text-secondary">
					<li>Visit <span class="font-mono text-accent">tavily.com</span> and create a free account</li>
					<li>Navigate to the API Keys section in your dashboard</li>
					<li>Copy your API key and paste it below</li>
					<li>Click "Test Connection" to verify everything works</li>
					<li>Save your configuration</li>
				</ol>
				<div class="flex items-start gap-1.5 rounded-md bg-accent/5 px-2.5 py-1.5">
					<Info size={12} class="mt-0.5 shrink-0 text-accent/70" />
					<p class="text-[11px] text-accent/80">
						The free tier includes 1,000 searches/month. Paid plans offer higher limits and additional features.
					</p>
				</div>
			</div>

			<!-- Provider -->
			<div class="rounded-xl border border-border bg-surface p-5">
				<h3 class="mb-4 text-sm font-semibold text-text-primary">Provider Configuration</h3>

				<div class="space-y-4">
					<!-- Provider selector -->
					<div>
						<label class="mb-1.5 block text-xs font-medium text-text-secondary">Provider</label>
						<select
							bind:value={searchProvider}
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						>
							<option value="tavily">Tavily</option>
						</select>
					</div>

					<!-- API Key -->
					<div>
						<label class="mb-1.5 block text-xs font-medium text-text-secondary">API Key</label>
						<input
							type="password"
							bind:value={searchApiKey}
							placeholder="tvly-..."
							class="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none transition-colors focus:border-accent"
						/>
					</div>

					<!-- Max Results -->
					<div>
						<label class="mb-1.5 block text-xs font-medium text-text-secondary">
							Max Results per Query: <span class="font-semibold text-text-primary">{searchMaxResults}</span>
						</label>
						<input
							type="range"
							min="1"
							max="10"
							bind:value={searchMaxResults}
							class="w-full accent-accent"
						/>
						<div class="mt-0.5 flex justify-between text-[10px] text-text-secondary/60">
							<span>1</span>
							<span>5</span>
							<span>10</span>
						</div>
					</div>

					<!-- Actions -->
					<div class="flex items-center gap-2 pt-1">
						<button
							type="button"
							onclick={saveConfig}
							disabled={saving}
							class="flex items-center gap-1.5 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50"
						>
							<Save size={14} />
							{saving ? 'Saving...' : 'Save'}
						</button>

						<button
							type="button"
							onclick={testConnection}
							disabled={testing}
							class="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm text-text-primary transition-colors hover:bg-surface-hover disabled:opacity-50"
						>
							<TestTube size={14} />
							{testing ? 'Testing...' : 'Test Connection'}
						</button>

						{#if saved}
							<span class="flex items-center gap-1 text-xs text-success">
								<CheckCircle size={14} />
								Saved
							</span>
						{/if}
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
				</div>
			</div>
		</div>
	{/if}
</div>
